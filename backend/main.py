from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import uuid, time, os

from agents.intake import run_intake
from agents.planning import run_planning
from agents.review import run_review

app = FastAPI(title="Nexus Operations Coordinator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory sessions — keyed by run_id. Isolated per session.
sessions: dict = {}


# ── Models ───────────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    transcript: str
    rules: str

class EditFactRequest(BaseModel):
    description: str   # plain-English description of what changed

class SimulateFailureRequest(BaseModel):
    agent: str         # "intake" | "planning" | "review"


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_session(run_id: str) -> dict:
    if run_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[run_id]

def validate_intake_output(output: dict) -> tuple[bool, str]:
    """Validate intake agent output schema before handoff."""
    required = ["decisions", "requirements", "constraints", "flags"]
    for key in required:
        if key not in output:
            return False, f"Missing required field: {key}"
        if not isinstance(output[key], list):
            return False, f"Field '{key}' must be a list"
    return True, "ok"

def validate_planning_output(output: dict) -> tuple[bool, str]:
    """Validate planning agent output schema before handoff."""
    if "tasks" not in output or not isinstance(output["tasks"], list):
        return False, "Missing or invalid 'tasks' field"
    for t in output["tasks"]:
        if "id" not in t or "title" not in t or "label" not in t:
            return False, f"Task missing required fields: {t}"
    return True, "ok"

def new_session(run_id: str, transcript: str, rules: str) -> dict:
    return {
        "run_id": run_id,
        "transcript": transcript,
        "rules": rules,
        "created_at": time.time(),
        # Context versions — bump on every write
        "context_versions": {"intake": 0, "planning": 0, "review": 0},
        # Handoff log — records what each agent passed to the next
        "handoff_log": [],
        "intake": {
            "status": "waiting", "output": None, "error": None,
            "schema_valid": None, "user_edits": []
        },
        "planning": {
            "status": "waiting", "output": None, "error": None,
            "corrections": None, "schema_valid": None
        },
        "review": {
            "status": "waiting", "output": None, "error": None,
            "corrections": None, "attempts": 0
        },
        "final_plan": None,
        "simulate_failure": None,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/run/start")
async def start_run(body: StartRequest):
    run_id = str(uuid.uuid4())[:8]
    sessions[run_id] = new_session(run_id, body.transcript, body.rules)
    return {"run_id": run_id}


@app.post("/run/{run_id}/intake")
async def trigger_intake(run_id: str):
    s = get_session(run_id)
    s["intake"]["status"] = "running"
    s["intake"]["error"] = None
    s["intake"]["schema_valid"] = None

    try:
        if s.get("simulate_failure") == "intake":
            raise Exception("[SIMULATED FAULT] Intake agent returned 503. No output written.")

        result = await run_intake(s["transcript"], s["rules"])

        # Validate schema before accepting output
        valid, msg = validate_intake_output(result)
        s["intake"]["schema_valid"] = {"ok": valid, "message": msg}
        if not valid:
            raise Exception(f"Handoff validation failed: {msg}")

        # Apply any user edits to the output
        if s["intake"]["user_edits"]:
            result["user_edits"] = s["intake"]["user_edits"]

        s["context_versions"]["intake"] += 1
        s["intake"]["status"] = "done"
        s["intake"]["output"] = result

        # Log handoff
        s["handoff_log"].append({
            "from": "intake", "to": "planning",
            "at": time.time(),
            "context_version": s["context_versions"]["intake"],
            "summary": {
                "decisions": len(result.get("decisions", [])),
                "requirements": len(result.get("requirements", [])),
                "constraints": len(result.get("constraints", [])),
                "flags": len(result.get("flags", [])),
            }
        })

        # Mark downstream stale
        s["planning"]["status"] = "waiting"
        s["review"]["status"] = "waiting"
        s["final_plan"] = None

    except Exception as e:
        s["intake"]["status"] = "failed"
        s["intake"]["error"] = str(e)

    return s["intake"]


@app.post("/run/{run_id}/planning")
async def trigger_planning(run_id: str):
    s = get_session(run_id)
    if s["intake"]["status"] != "done":
        raise HTTPException(400, "Intake must complete before Planning")

    s["planning"]["status"] = "running"
    s["planning"]["error"] = None
    s["planning"]["schema_valid"] = None

    try:
        if s.get("simulate_failure") == "planning":
            raise Exception("[SIMULATED FAULT] Planning agent timed out. Intake output preserved — retry will not duplicate intake.")

        result = await run_planning(
            s["intake"]["output"],
            s["rules"],
            s["planning"].get("corrections")
        )

        # Validate schema
        valid, msg = validate_planning_output(result)
        s["planning"]["schema_valid"] = {"ok": valid, "message": msg}
        if not valid:
            raise Exception(f"Handoff validation failed: {msg}")

        s["context_versions"]["planning"] += 1
        s["planning"]["status"] = "done"
        s["planning"]["output"] = result

        # Log handoff
        s["handoff_log"].append({
            "from": "planning", "to": "review",
            "at": time.time(),
            "context_version": s["context_versions"]["planning"],
            "summary": {
                "tasks": len(result.get("tasks", [])),
                "supported": len([t for t in result.get("tasks", []) if t.get("label") == "[SUPPORTED]"]),
                "unresolved": len([t for t in result.get("tasks", []) if t.get("label") == "[UNRESOLVED]"]),
            }
        })

        s["review"]["status"] = "waiting"
        s["final_plan"] = None

    except Exception as e:
        s["planning"]["status"] = "failed"
        s["planning"]["error"] = str(e)

    return s["planning"]


@app.post("/run/{run_id}/review")
async def trigger_review(run_id: str):
    s = get_session(run_id)
    if s["planning"]["status"] != "done":
        raise HTTPException(400, "Planning must complete before Review")

    # Hard cap at 2 rounds
    if s["review"]["attempts"] >= 2:
        s["review"]["status"] = "done"
        s["review"]["output"] = {
            "approved": False,
            "summary": "Max revision rounds (2) reached. Surfacing unresolved issues.",
            "corrections": [],
            "unresolved": ["Maximum review rounds reached — manual resolution required"]
        }
        s["final_plan"] = s["planning"]["output"]
        return s["review"]

    s["review"]["status"] = "running"
    s["review"]["error"] = None

    try:
        if s.get("simulate_failure") == "review":
            raise Exception("[SIMULATED FAULT] Review agent returned malformed JSON. Plan preserved — retry will re-audit without rerunning Planning.")

        result = await run_review(
            s["transcript"],
            s["rules"],
            s["planning"]["output"]
        )

        s["review"]["attempts"] += 1
        s["context_versions"]["review"] += 1
        s["review"]["output"] = result

        if result.get("approved"):
            s["review"]["status"] = "done"
            s["final_plan"] = s["planning"]["output"]

            s["handoff_log"].append({
                "from": "review", "to": "final",
                "at": time.time(),
                "context_version": s["context_versions"]["review"],
                "summary": {"approved": True, "attempts": s["review"]["attempts"]}
            })
        else:
            # Send corrections back to planning
            corrections = result.get("corrections", [])
            s["review"]["status"] = "needs_revision"
            s["review"]["corrections"] = corrections
            s["planning"]["status"] = "waiting"
            s["planning"]["corrections"] = corrections

            s["handoff_log"].append({
                "from": "review", "to": "planning",
                "at": time.time(),
                "context_version": s["context_versions"]["review"],
                "summary": {
                    "approved": False,
                    "corrections": len(corrections),
                    "attempt": s["review"]["attempts"]
                }
            })

    except Exception as e:
        s["review"]["status"] = "failed"
        s["review"]["error"] = str(e)

    return s["review"]


@app.get("/run/{run_id}/status")
async def get_status(run_id: str):
    return get_session(run_id)


@app.post("/run/{run_id}/edit-fact")
async def edit_fact(run_id: str, body: EditFactRequest):
    s = get_session(run_id)
    edit = {"description": body.description, "applied_at": time.time()}
    s["intake"]["user_edits"].append(edit)

    if s["intake"]["output"]:
        s["intake"]["output"]["user_edits"] = s["intake"]["user_edits"]

    # Bump intake context version — signals stale downstream
    s["context_versions"]["intake"] += 1

    # Mark planning + review stale (keep intake output)
    s["planning"]["status"] = "waiting"
    s["planning"]["output"] = None
    s["planning"]["corrections"] = None
    s["review"]["status"] = "waiting"
    s["review"]["output"] = None
    s["review"]["attempts"] = 0
    s["final_plan"] = None

    return {
        "ok": True,
        "intake_context_version": s["context_versions"]["intake"],
        "message": "Fact recorded — rerun Planning and Review to propagate"
    }


@app.post("/run/{run_id}/simulate-failure")
async def simulate_failure(run_id: str, body: SimulateFailureRequest):
    s = get_session(run_id)
    s["simulate_failure"] = body.agent
    return {"ok": True}


@app.post("/run/{run_id}/clear-failure")
async def clear_failure(run_id: str):
    s = get_session(run_id)
    s["simulate_failure"] = None
    return {"ok": True}


@app.post("/run/{run_id}/reset")
async def reset_run(run_id: str):
    if run_id in sessions:
        del sessions[run_id]
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok", "sessions": len(sessions)}
