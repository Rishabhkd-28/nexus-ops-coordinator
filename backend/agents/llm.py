import httpx
import os
import json

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL = os.getenv("MODEL", "meta-llama/llama-3.1-8b-instruct:free")

async def call_llm(system_prompt: str, user_message: str) -> str:
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY not set in environment variables")

    # Truncate inputs to avoid token limit issues
    max_chars = 6000
    if len(user_message) > max_chars:
        user_message = user_message[:max_chars] + "\n\n[truncated for length]"

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://nexus-ops.vercel.app",
                "X-Title": "Nexus Operations Coordinator",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "user", "content": f"{system_prompt}\n\n{user_message}"},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
        )
        if response.status_code != 200:
            detail = response.text[:300]
            raise Exception(f"OpenRouter API error {response.status_code}: {detail}")
        data = response.json()
        if "error" in data:
            raise Exception(f"OpenRouter error: {data['error'].get('message','Unknown error')}")
        return data["choices"][0]["message"]["content"]

async def call_llm_json(system_prompt: str, user_message: str) -> dict:
    raw = await call_llm(system_prompt, user_message)
    cleaned = raw.strip()
    # Strip markdown fences
    if "```" in cleaned:
        lines = cleaned.split("\n")
        inner = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(inner).strip()
    # Find JSON object in response
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start >= 0 and end > start:
        cleaned = cleaned[start:end]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Return minimal valid structure
        return {"raw": cleaned, "parse_error": True}
