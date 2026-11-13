import httpx, os, json, logging, asyncio, random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_KEY_2 = os.getenv("OPENROUTER_API_KEY_2", "")
OPENROUTER_KEYS = [k for k in [OPENROUTER_API_KEY, OPENROUTER_API_KEY_2] if k]

OPENROUTER_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
]

_last_key_index = 0


async def _call_openrouter(model: str, prompt: str) -> str | None:
    global _last_key_index
    if not OPENROUTER_KEYS:
        return None
    # Round-robin between keys
    key = OPENROUTER_KEYS[_last_key_index % len(OPENROUTER_KEYS)]
    _last_key_index += 1
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://nexus-ops.vercel.app",
                    "X-Title": "Nexus",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1500,
                },
            )
            if response.status_code == 200:
                data = response.json()
                if "error" not in data:
                    content = data["choices"][0]["message"]["content"]
                    if content:
                        logger.info(f"OpenRouter success: {model}")
                        return content
                    logger.warning(f"OpenRouter null content: {model}")
            elif response.status_code == 429:
                logger.warning(f"OpenRouter 429: {model} (key {_last_key_index % len(OPENROUTER_KEYS)})")
            else:
                logger.warning(f"OpenRouter {response.status_code}: {model}")
    except Exception as e:
        logger.warning(f"OpenRouter exception: {e}")
    return None


async def call_llm(system_prompt: str, user_message: str) -> str:
    combined = f"{system_prompt}\n\n{user_message}"
    if len(combined) > 10000:
        combined = combined[:10000]

    for model in OPENROUTER_MODELS:
        await asyncio.sleep(random.uniform(0.1, 0.4))
        result = await _call_openrouter(model, combined)
        if result:
            return result

    raise Exception("All models failed")


async def call_llm_json(system_prompt: str, user_message: str) -> dict:
    raw = await call_llm(system_prompt, user_message)
    if not raw:
        return {"decisions":[],"requirements":[],"constraints":[],"flags":[],"tasks":[],"approved":False,"summary":"","corrections":[],"unresolved":[],"user_edits":[]}
    cleaned = raw.strip()
    if "```" in cleaned:
        cleaned = "\n".join(l for l in cleaned.split("\n") if not l.strip().startswith("```")).strip()
    start = cleaned.find("{"); end = cleaned.rfind("}") + 1
    if start >= 0 and end > start:
        cleaned = cleaned[start:end]
    try:
        return json.loads(cleaned)
    except:
        return {"decisions":[],"requirements":[],"constraints":[],"flags":[],"tasks":[],"approved":False,"summary":raw[:200],"corrections":[],"unresolved":[],"user_edits":[]}
