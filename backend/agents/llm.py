import httpx
import os
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

MODELS = [
    "google/gemma-3-4b-it:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "microsoft/phi-3-mini-128k-instruct:free",
    "qwen/qwen-2-7b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
]

async def call_llm(system_prompt: str, user_message: str) -> str:
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY not set")
    combined = f"{system_prompt}\n\n{user_message}"
    if len(combined) > 6000:
        combined = combined[:6000]
    last_error = None
    for model in MODELS:
        logger.info(f"Trying model: {model}")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}","Content-Type": "application/json","HTTP-Referer": "https://nexus-ops.vercel.app","X-Title": "Nexus"},
                    json={"model": model,"messages": [{"role": "user", "content": combined}],"temperature": 0.3,"max_tokens": 1500},
                )
                if response.status_code == 200:
                    data = response.json()
                    if "error" not in data:
                        logger.info(f"Success with model: {model}")
                        return data["choices"][0]["message"]["content"]
                    last_error = data["error"].get("message", "Unknown")
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:100]}"
                logger.warning(f"Model {model} failed: {last_error}")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Model {model} exception: {last_error}")
    raise Exception(f"All models failed. Last error: {last_error}")

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
