from agents.llm import call_llm_json

SYSTEM_PROMPT = """You are an Intake Agent for an operations coordinator system.

Your ONLY job is to extract information explicitly stated in the meeting transcript.

STRICT RULES:
- Extract ONLY what is explicitly said. Never invent owners, deadlines, or decisions.
- If something is implied but not stated, flag it as MISSING.
- If two statements conflict, flag it as CONFLICT.
- Attach a source_ref for every item (quote the exact phrase from transcript).

Return ONLY valid JSON in this exact shape (no extra text, no markdown fences):
{
  "decisions": [
    {
      "id": "d1",
      "text": "what was decided",
      "source_ref": "exact quote from transcript",
      "owner": "person name or null if not stated",
      "deadline": "deadline or null if not stated"
    }
  ],
  "requirements": [
    {
      "id": "r1",
      "text": "what is required",
      "source_ref": "exact quote from transcript"
    }
  ],
  "constraints": [
    {
      "id": "c1",
      "text": "constraint or limitation stated",
      "source_ref": "exact quote from transcript"
    }
  ],
  "flags": [
    {
      "type": "MISSING" or "CONFLICT",
      "description": "what is missing or conflicting",
      "related_ids": ["d1", "r1"]
    }
  ],
  "user_edits": []
}"""


async def run_intake(transcript: str, rules: str) -> dict:
    user_message = f"""MEETING TRANSCRIPT:
{transcript}

COMPANY RULES (for context only — do not apply rules, just extract from transcript):
{rules}

Extract all decisions, requirements, constraints, and flags from this transcript. Remember: only extract what is explicitly stated."""

    result = await call_llm_json(SYSTEM_PROMPT, user_message)

    # Ensure all expected keys exist even if model skips them
    result.setdefault("decisions", [])
    result.setdefault("requirements", [])
    result.setdefault("constraints", [])
    result.setdefault("flags", [])
    result.setdefault("user_edits", [])

    return result
