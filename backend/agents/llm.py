import httpx, os, json, logging, asyncio, random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_KEY_2 = os.getenv("OPENROUTER_API_KEY_2", "")
OPENROUTER_KEYS = [k for k in [OPENROUTER_API_KEY, OPENROUTER_API_KEY_2] if k]
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama3-8b-8192",
    "gemma2-9b-it",
]

OPENROUTER_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "google/gemma-4-31b-it:free",
    "liquid/lfm-3-1.7b:free",
]

# Track failures to avoid hammering a provider
_provider_failures = {"groq": 0, "openrouter": 0}
_provider_last_fail = {"groq": 0.0, "openrouter": 0.0}
COOLDOWN_SECONDS = 30


async def _call_groq(model: str, prompt: str) -> str | None:
    if not GROQ_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
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
                    logger.info(f"Groq success: {model}")
                    _provider_failures["groq"] = 0
                    return content
                logger.warning(f"Groq null content: {model}")
            elif response.status_code == 429:
                logger.warning(f"Groq 429: {model}")
                _provider_failures["groq"] += 1
            else:
                logger.warning(f"Groq {response.status_code}: {model}")
    except Exception as e:
        logger.warning(f"Groq exception: {e}")
    return None


async def _call_openrouter(model: str, prompt: str) -> str | None:
    if not OPENROUTER_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
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
                        _provider_failures["openrouter"] = 0
                        return content
                    logger.warning(f"OpenRouter null content: {model}")
            elif response.status_code == 429:
                logger.warning(f"OpenRouter 429: {model}")
                _provider_failures["openrouter"] += 1
            else:
                logger.warning(f"OpenRouter {response.status_code}: {model}")
    except Exception as e:
        logger.warning(f"OpenRouter exception: {e}")
    return None


async def call_llm(system_prompt: str, user_message: str) -> str:
    import time
    combined = f"{system_prompt}\n\n{user_message}"
    if len(combined) > 6000:
        combined = combined[:6000]

    now = time.time()

    # Decide provider order based on recent failures + cooldown
    groq_cooling = (
        _provider_failures["groq"] >= 2
        and (now - _provider_last_fail["groq"]) < COOLDOWN_SECONDS
    )
    or_cooling = (
        _provider_failures["openrouter"] >= 2
        and (now - _provider_last_fail["openrouter"]) < COOLDOWN_SECONDS
    )

    # Build attempt queue: groq models first, then openrouter, with jitter
    attempts = []

    if not groq_cooling and GROQ_API_KEY:
        for model in GROQ_MODELS:
            attempts.append(("groq", model))

    if not or_cooling and OPENROUTER_API_KEY:
        for model in OPENROUTER_MODELS:
            attempts.append(("openrouter", model))

    # If both cooling, try both anyway (last resort)
    if not attempts:
        logger.warning("Both providers in cooldown — trying anyway")
        for model in GROQ_MODELS:
            attempts.append(("groq", model))
        for model in OPENROUTER_MODELS:
            attempts.append(("openrouter", model))

    for provider, model in attempts:
        # Small jitter to avoid thundering herd
        await asyncio.sleep(random.uniform(0.1, 0.4))

        if provider == "groq":
            result = await _call_groq(model, combined)
        else:
            result = await _call_openrouter(model, combined)

        if result:
            return result

        # Track last failure time
        import time as t
        _provider_last_fail[provider] = t.time()

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
