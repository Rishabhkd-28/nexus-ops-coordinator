from agents.llm import call_llm_json

SYSTEM_PROMPT = """Extract information from this meeting transcript. Return JSON only.

Rules:
- Only extract what is EXPLICITLY stated
- Never invent owners or deadlines  
- Use null for missing owners/deadlines
- source_ref must be exact words from transcript

Return this exact JSON structure:
{
  "decisions": [{"id":"d1","text":"decision made","source_ref":"exact words used","owner":"person or null","deadline":"date or null"}],
  "requirements": [{"id":"r1","text":"what is required","source_ref":"exact words used"}],
  "constraints": [{"id":"c1","text":"limitation or rule","source_ref":"exact words used"}],
  "flags": [{"type":"MISSING","description":"what info is missing","related_ids":["d1"]}],
  "user_edits": []
}"""

async def run_intake(transcript: str, rules: str) -> dict:
    prompt = f"""TRANSCRIPT:
{transcript}

COMPANY RULES (for reference only - do not apply):
{rules}

Extract all decisions, requirements, constraints and flags from the transcript above. Use exact quotes."""

    result = await call_llm_json(SYSTEM_PROMPT, prompt)
    result.setdefault("decisions", [])
    result.setdefault("requirements", [])
    result.setdefault("constraints", [])
    result.setdefault("flags", [])
    result.setdefault("user_edits", [])
    return result
