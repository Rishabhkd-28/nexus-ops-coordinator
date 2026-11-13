from agents.llm import call_llm_json
import json

SYSTEM_PROMPT = """You are a Planning Agent for an operations coordinator system.

Your job is to create a structured action plan using ONLY:
1. The structured output from the Intake Agent
2. The company rules provided

STRICT RULES:
- Label every task clearly as one of: [SUPPORTED] (backed by transcript), [RECOMMENDED] (from rules, not transcript), or [UNRESOLVED] (needs clarification)
- Never invent owners not mentioned in the transcript or rules
- Never invent deadlines not stated — use null and mark [UNRESOLVED]
- If review corrections are provided, address each one explicitly

Return ONLY valid JSON in this exact shape (no extra text, no markdown fences):
{
  "tasks": [
    {
      "id": "t1",
      "title": "short task title",
      "description": "what needs to be done",
      "owner": "person name or null",
      "deadline": "deadline or null",
      "depends_on": ["t2"],
      "label": "[SUPPORTED]" or "[RECOMMENDED]" or "[UNRESOLVED]",
      "source": "which decision/requirement this comes from (e.g. d1, r2)"
    }
  ],
  "unresolved_questions": [
    "question that must be answered before this plan can be finalized"
  ],
  "corrections_addressed": [
    "how each review correction was handled (empty list if no corrections)"
  ]
}"""


async def run_planning(intake_output: dict, rules: str, corrections: list = None) -> dict:
    corrections_block = ""
    if corrections:
        corrections_block = f"""
REVIEW CORRECTIONS TO ADDRESS:
{json.dumps(corrections, indent=2)}

You MUST address each correction above. List how you handled each one in corrections_addressed.
"""

    user_message = f"""INTAKE AGENT OUTPUT:
{json.dumps(intake_output, indent=2)}

COMPANY RULES:
{rules}
{corrections_block}
Create a task plan. Label every task. Do not invent facts not present in the intake output or rules."""

    result = await call_llm_json(SYSTEM_PROMPT, user_message)

    result.setdefault("tasks", [])
    result.setdefault("unresolved_questions", [])
    result.setdefault("corrections_addressed", [])

    return result
