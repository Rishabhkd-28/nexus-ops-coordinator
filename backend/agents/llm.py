import httpx
import os
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL = os.getenv("MODEL", "meta-llama/llama-3.1-8b-instruct:free")

async def call_llm(system_prompt: str, user_message: str) -> str:
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY not set")

    combined = f"{system_prompt}\n\n{user_message}"
    if len(combined) > 8000:
        combined = combined[:8000]

    logger.info(f"Calling OpenRouter model: {MODEL}")

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://nexus-ops.vercel.app",
                "X-Title": "Nexus",
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": combined}],
                "temperature": 0.3,
                "max_tokens": 1500,
            },
        )
        logger.info(f"OpenRouter response status: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"OpenRouter error: {response.text[:500]}")
            raise Exception(f"OpenRouter {response.status_code}: {response.text[:200]}")
        data = response.json()
        if "error" in data:
            logger.error(f"OpenRouter API error: {data['error']}")
            raise Exception(f"OpenRouter error: {data['error'].get('message','Unknown')}")
        return data["choices"][0]["message"]["content"]

async def call_llm_json(system_prompt: str, user_message: str) -> dict:
    raw = await call_llm(system_prompt, user_message)
    cleaned = raw.strip()
    if "```" in cleaned:
        lines = cleaned.split("\n")
        inner = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(inner).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start >= 0 and end > start:
        cleaned = cleaned[start:end]
    try:
        return json.loads(cleaned)
    except:
        return {"decisions":[],"requirements":[],"constraints":[],"flags":[],"tasks":[],"approved":False,"summary":raw[:200],"corrections":[],"unresolved":[],"user_edits":[]}
