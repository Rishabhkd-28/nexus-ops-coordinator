from agents.llm import call_llm_json
import json

SYSTEM_PROMPT = """You are a Review Agent for an operations coordinator system.

Your job is to audit the proposed plan against the original transcript and company rules.

STRICT RULES:
- Check every task: does it have a basis in the transcript or rules?
- Flag any invented owner, invented deadline, or rule violation with the EXACT rule or transcript line it violates
- If the plan is clean and grounded, approve it
- Be specific — vague corrections like "needs improvement" are not allowed
- Max 2 review rounds total (tracked externally)

Return ONLY valid JSON in this exact shape (no extra text, no markdown fences):
{
  "approved": true or false,
  "summary": "one sentence overall verdict",
  "corrections": [
    {
      "task_id": "t1",
      "issue": "what is wrong",
      "rule_or_ref": "the exact rule line or transcript quote being violated",
      "suggested_fix": "specific fix"
    }
  ],
  "unresolved": [
    "issue that could not be resolved after review"
  ]
}

If approved is true, corrections must be an empty list."""


async def run_review(transcript: str, rules: str, plan: dict) -> dict:
    user_message = f"""ORIGINAL TRANSCRIPT:
{transcript}

COMPANY RULES:
{rules}

PROPOSED PLAN TO REVIEW:
{json.dumps(plan, indent=2)}

Audit every task in the plan. Check for invented facts, rule violations, and missing grounding. 
If everything is properly labeled and grounded, set approved to true."""

    result = await call_llm_json(SYSTEM_PROMPT, user_message)

    result.setdefault("approved", False)
    result.setdefault("summary", "")
    result.setdefault("corrections", [])
    result.setdefault("unresolved", [])

    return result
