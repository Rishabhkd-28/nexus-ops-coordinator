from agents.llm import call_llm_json

SYSTEM_PROMPT = """You are an Intake Agent. Extract from the transcript only what is EXPLICITLY stated.
Never invent owners or deadlines. Return ONLY valid JSON:
{
  "decisions": [{"id":"d1","text":"...","source_ref":"exact quote","owner":null,"deadline":null}],
  "requirements": [{"id":"r1","text":"...","source_ref":"exact quote"}],
  "constraints": [{"id":"c1","text":"...","source_ref":"exact quote"}],
  "flags": [{"type":"MISSING","description":"...","related_ids":["d1"]}],
  "user_edits": []
}"""

async def run_intake(transcript: str, rules: str) -> dict:
    result = await call_llm_json(SYSTEM_PROMPT,
        f"TRANSCRIPT:\n{transcript}\n\nRULES (context only):\n{rules}")
    result.setdefault("decisions", [])
    result.setdefault("requirements", [])
    result.setdefault("constraints", [])
    result.setdefault("flags", [])
    result.setdefault("user_edits", [])
    return result
