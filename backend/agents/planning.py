from agents.llm import call_llm_json
import json

SYSTEM_PROMPT = """You are a Planning Agent. Use the intake output and rules to propose tasks.
Label each task [SUPPORTED], [RECOMMENDED], or [UNRESOLVED]. Never invent facts.
Be concise: at most 8 tasks, each description under 20 words, at most 4 unresolved_questions.
Return ONLY valid JSON:
{
  "tasks": [{"id":"t1","title":"...","description":"...","owner":null,"deadline":null,"depends_on":[],"label":"[SUPPORTED]"}],
  "unresolved_questions": ["..."],
  "corrections_addressed": []
}"""

async def run_planning(intake_output: dict, rules: str, corrections=None) -> dict:
    corr = f"\nCORRECTIONS TO FIX:\n{json.dumps(corrections)}" if corrections else ""
    result = await call_llm_json(SYSTEM_PROMPT,
        f"INTAKE:\n{json.dumps(intake_output)}\n\nRULES:\n{rules}{corr}")
    result.setdefault("tasks", [])
    if not result["tasks"]:
        raise Exception("Planning returned no tasks")
    result.setdefault("unresolved_questions", [])
    result.setdefault("corrections_addressed", [])
    return result
