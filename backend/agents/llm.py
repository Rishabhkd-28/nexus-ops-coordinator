from __future__ import annotations
import httpx, os, json, logging, asyncio, random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _load_keys() -> list[str]:
    """Collect every OpenRouter key (sk-or-...) from any *API_KEY* env var, deduped, in name order."""
    keys: list[str] = []
    for name in sorted(os.environ):
        if "API_KEY" in name:
            val = os.environ[name].strip()
            if val.startswith("sk-or-") and val not in keys:
                keys.append(val)
    return keys

OPENROUTER_KEYS = _load_keys()
logger.info(f"Loaded {len(OPENROUTER_KEYS)} OpenRouter key(s)")

OPENROUTER_MODELS = [
    "particle-ai/particle-1:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
]

_key_index = 0

async def _call_openrouter(model: str, prompt: str) -> str | None:
    global _key_index
    if not OPENROUTER_KEYS:
        return None
    for i in range(len(OPENROUTER_KEYS)):
        key = OPENROUTER_KEYS[(_key_index + i) % len(OPENROUTER_KEYS)]
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
                        "max_tokens": 3000,
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    if "error" not in data:
                        content = data["choices"][0]["message"]["content"]
                        if content:
                            logger.info(f"OpenRouter success: {model} (key {(_key_index+i)%len(OPENROUTER_KEYS)+1})")
                            _key_index = (_key_index + i + 1) % len(OPENROUTER_KEYS)
                            return content
                        logger.warning(f"OpenRouter null content: {model} key {i+1}")
                elif response.status_code == 429:
                    logger.warning(f"OpenRouter 429: {model} key {i+1}")
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                elif response.status_code == 401:
                    logger.warning(f"OpenRouter 401: key {i+1}")
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
        await asyncio.sleep(random.uniform(0.1, 0.3))
        result = await _call_openrouter(model, combined)
        if result:
            return result
    raise Exception("All models and keys failed")

def _parse_json(raw: str):
    cleaned = raw.strip()
    if "```" in cleaned:
        cleaned = "\n".join(l for l in cleaned.split("\n") if not l.strip().startswith("```")).strip()
    start = cleaned.find("{"); end = cleaned.rfind("}") + 1
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(cleaned[start:end])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None

async def call_llm_json(system_prompt: str, user_message: str) -> dict:
    """Call the LLM and return parsed JSON. Retries on unparseable output, then raises
    (so the pipeline shows a real error instead of silently continuing with empty data)."""
    last_raw = ""
    for attempt in range(3):
        last_raw = await call_llm(system_prompt, user_message)
        obj = _parse_json(last_raw)
        if obj is not None:
            return obj
        logger.warning(f"Unparseable JSON from LLM (attempt {attempt+1}): {last_raw[:120]!r}")
    raise Exception(f"LLM returned invalid JSON after 3 attempts: {last_raw[:150]!r}")
