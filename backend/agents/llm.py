import httpx, os, json, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODELS = ["openrouter/auto"]

async def call_llm(system_prompt: str, user_message: str) -> str:
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY not set")
    combined = f"{system_prompt}\n\n{user_message}"
    if len(combined) > 6000:
        combined = combined[:6000]
    for model in MODELS:
        logger.info(f"Trying model: {model}")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}","Content-Type":"application/json","HTTP-Referer":"https://nexus-ops.vercel.app","X-Title":"Nexus"},
                    json={"model":model,"messages":[{"role":"user","content":combined}],"temperature":0.3,"max_tokens":1500},
                )
                if response.status_code == 200:
                    data = response.json()
                    if "error" not in data:
                        logger.info(f"Success with model: {model}")
                        content = data["choices"][0]["message"]["content"]
                        if content is not None:
                            logger.info(f"Success with model: {model}")
                            return content
                        logger.warning(f"Model {model} returned null content")
                logger.warning(f"Model {model} failed: {response.text[:100]}")
        except Exception as e:
            logger.warning(f"Model {model} exception: {e}")
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
