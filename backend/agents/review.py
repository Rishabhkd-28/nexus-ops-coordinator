from agents.llm import call_llm_json
import json

SYSTEM_PROMPT = """You are a Review Agent. Check the plan against the transcript and rules.
Return ONLY valid JSON:
{
  "approved": false,
  "summary": "...",
  "corrections": [{"task_id":"t1","issue":"...","rule_or_ref":"...","suggested_fix":"..."}],
  "unresolved": []
}
If approved, set approved:true and corrections:[]"""

async def run_review(transcript: str, rules: str, plan: dict) -> dict:
    result = await call_llm_json(SYSTEM_PROMPT,
        f"TRANSCRIPT:\n{transcript}\n\nRULES:\n{rules}\n\nPLAN:\n{json.dumps(plan)}")
    result.setdefault("approved", False)
    result.setdefault("summary", "")
    result.setdefault("corrections", [])
    result.setdefault("unresolved", [])
    return result
