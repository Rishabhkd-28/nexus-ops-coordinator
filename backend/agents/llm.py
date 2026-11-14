import httpx, os, json, logging, asyncio, random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GROQ_KEYS = [k for k in [
    os.getenv("GROQ_API_KEY", ""),
    os.getenv("GROQ_API_KEY_2", ""),
    os.getenv("GROQ_API_KEY_3", ""),
] if k]

OPENROUTER_KEYS = [k for k in [
    os.getenv("OPENROUTER_API_KEY", ""),
    os.getenv("OPENROUTER_API_KEY_2", ""),
] if k]

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
]

OPENROUTER_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
]

_groq_index = 0
_openrouter_index = 0


async def _call_groq(model: str, prompt: str) -> str | None:
    global _groq_index
    if not GROQ_KEYS:
        return None
    key = GROQ_KEYS[_groq_index % len(GROQ_KEYS)]
    _groq_index += 1
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
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
                content = data["choices"][0]["message"]["content"]
                if content:
                    logger.info(f"Groq success: {model} (key {(_groq_index-1) % len(GROQ_KEYS) + 1})")
                    return content
                logger.warning(f"Groq null content: {model}")
            elif response.status_code == 429:
                logger.warning(f"Groq 429 rate limit: {model} — trying next key")
                # Try remaining keys
                for i, fallback_key in enumerate(GROQ_KEYS):
                    if fallback_key == key:
                        continue
                    retry = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {fallback_key}", "Content-Type": "application/json"},
                        json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 1500},
                    )
                    if retry.status_code == 200:
                        content = retry.json()["choices"][0]["message"]["content"]
                        if content:
                            logger.info(f"Groq success (fallback key {i+1}): {model}")
                            return content
            else:
                logger.warning(f"Groq {response.status_code}: {model}")
    except Exception as e:
        logger.warning(f"Groq exception: {e}")
    return None


async def _call_openrouter(model: str, prompt: str) -> str | None:
    global _openrouter_index
    if not OPENROUTER_KEYS:
        return None
    key = OPENROUTER_KEYS[_openrouter_index % len(OPENROUTER_KEYS)]
    _openrouter_index += 1
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
                logger.warning(f"OpenRouter 429: {model}")
                # Try other key
                other_keys = [k for k in OPENROUTER_KEYS if k != key]
                if other_keys:
                    retry = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {other_keys[0]}", "Content-Type": "application/json", "HTTP-Referer": "https://nexus-ops.vercel.app", "X-Title": "Nexus"},
                        json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 1500},
                    )
                    if retry.status_code == 200:
                        content = retry.json()["choices"][0]["message"]["content"]
                        if content:
                            logger.info(f"OpenRouter success (fallback key): {model}")
                            return content
            elif response.status_code == 401:
                logger.warning(f"OpenRouter 401 bad key — trying other key")
                other_keys = [k for k in OPENROUTER_KEYS if k != key]
                if other_keys:
                    retry = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {other_keys[0]}", "Content-Type": "application/json", "HTTP-Referer": "https://nexus-ops.vercel.app", "X-Title": "Nexus"},
                        json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 1500},
                    )
                    if retry.status_code == 200:
                        content = retry.json()["choices"][0]["message"]["content"]
                        if content:
                            logger.info(f"OpenRouter success (fallback key): {model}")
                            return content
            else:
                logger.warning(f"OpenRouter {response.status_code}: {model}")
    except Exception as e:
        logger.warning(f"OpenRouter exception: {e}")
    return None


async def call_llm(system_prompt: str, user_message: str) -> str:
    combined = f"{system_prompt}\n\n{user_message}"
    if len(combined) > 10000:
        combined = combined[:10000]

    # Try Groq first (all models, round-robin keys)
    for model in GROQ_MODELS:
        await asyncio.sleep(random.uniform(0.1, 0.3))
        result = await _call_groq(model, combined)
        if result:
            return result

    logger.warning("All Groq models failed — falling back to OpenRouter")

    # Fall back to OpenRouter (all models, round-robin keys)
    for model in OPENROUTER_MODELS:
        await asyncio.sleep(random.uniform(0.1, 0.3))
        result = await _call_openrouter(model, combined)
        if result:
            return result

    raise Exception("All providers and models failed")


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
