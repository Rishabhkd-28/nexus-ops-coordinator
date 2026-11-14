# Nexus — Operations Coordinator (Assignment 2)

Three distinct LLM-powered agents that turn a meeting transcript and company rules into a reviewed action plan.

## Architecture

```
Frontend (single HTML page)  →  Backend (FastAPI)  →  OpenRouter API
     Vercel (free)                   Railway             free-tier models (keys rotated)
```

### Agents

| Agent | Route | Role |
|---|---|---|
| Intake | `POST /run/{id}/intake` | Extracts decisions, requirements, constraints. Attaches source refs. Flags missing/conflicting info. Never invents. |
| Planning | `POST /run/{id}/planning` | Builds task plan from intake output + rules. Labels every task [SUPPORTED], [RECOMMENDED], or [UNRESOLVED]. |
| Review | `POST /run/{id}/review` | Audits plan against transcript and rules. Returns corrections to Planning. Max 2 rounds. Approves or surfaces unresolved. |

### Session isolation
Every run gets a UUID run ID. Sessions are stored in a Python dict keyed by run ID — `sessions["abc"]` and `sessions["xyz"]` never touch.

### Context versioning
Each agent tracks a context version (`intake_v1`, `planning_v2`, etc.) that bumps on every write or user edit — visible in the UI.

### Handoff validation
Before accepting agent output, the backend validates the JSON schema. If validation fails, the agent is marked `failed` and the handoff is blocked.

## Setup

### Backend
```bash
cd backend
cp .env.example .env
# Fill in OPENROUTER_API_KEY from openrouter.ai (free account)
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
cp .env.example .env.local
# Set VITE_API_URL=http://localhost:8000 for local dev
npm install
npm run dev
```

## Deploy
- **Backend → Railway**: root `backend/`, start `uvicorn main:app --host 0.0.0.0 --port $PORT`. Set env vars `OPENROUTER_API_KEY`, `OPENROUTER_API_KEY_2`, ... (any `*API_KEY*` var starting `sk-or-` is loaded).
- **Frontend → Vercel**: static page `frontend/public/index.html`; the API URL is editable in the UI (Config tab).

## Tests
```bash
pip install httpx
API_URL=https://nexus-ops-coordinator-production.up.railway.app python3 tests/e2e_live.py   # 2 transcripts, full pipeline + correction loop
npm i puppeteer-core && node tests/ui_smoke.mjs                                              # headless Chrome UI smoke test
```
Both hit the live LLM (free-tier quota applies).

## Known limitations
- Sessions are in memory: a backend restart/redeploy clears them.
- OpenRouter free tier: 50 requests/day/account; models sometimes return null/truncated output (handled by retry + JSON repair).
- The Review agent often reaches the 2-round cap; the plan is then delivered with unresolved issues flagged.
- Owners are sometimes left "Unassigned" by the model even when stated. UI is desktop-first.
