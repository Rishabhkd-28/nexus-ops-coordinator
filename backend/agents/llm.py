import httpx
import os
import json

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL = os.getenv("MODEL", "google/gemma-3-27b-it:free")


async def call_llm(system_prompt: str, user_message: str) -> str:
    """Call OpenRouter and return the response text."""
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY is not set")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://assignment2-demo.vercel.app",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.3,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def call_llm_json(system_prompt: str, user_message: str) -> dict:
    """Call LLM and parse JSON response. Strips markdown fences if present."""
    raw = await call_llm(system_prompt, user_message)
    # Strip ```json ... ``` fences if model wraps output
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last fence lines
        inner = lines[1:] if lines[0].startswith("```") else lines
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        cleaned = "\n".join(inner).strip()
    return json.loads(cleaned)
