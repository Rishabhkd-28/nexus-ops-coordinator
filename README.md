# Nexus — Operations Coordinator (Assignment 2)

Three distinct LLM-powered agents that turn a meeting transcript and company rules into a reviewed action plan.

## Architecture

```
Frontend (React + Vite)  →  Backend (FastAPI)  →  OpenRouter API
     Vercel (free)              Render (free)       free-tier models
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

## Deploy (free)

### Backend → Render.com
1. Push `backend/` to GitHub
2. New Web Service → connect repo
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add env var: `OPENROUTER_API_KEY`

### Frontend → Vercel
1. Push `frontend/` to GitHub
2. New Project → connect repo
3. Add env var: `VITE_API_URL=https://your-render-app.onrender.com`
4. Deploy

## Environment variables

| Variable | Where | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | backend `.env` | From openrouter.ai — free account works |
| `MODEL` | backend `.env` | Default: `google/gemma-3-27b-it:free` |
| `VITE_API_URL` | frontend `.env.local` | Backend URL |

## Demo cases

| Case | How to trigger |
|---|---|
| Full 3-agent run | Load sample → Run pipeline |
| Rule violation corrected | Run pipeline — Review automatically sends corrections to Planning (round 1) |
| Fact correction propagates | After run: Controls tab → Correct a fact → Apply and rerun |
| Simulated failure + retry | Controls tab → Simulate failure → Run pipeline → Retry button on failed node |
| Two sessions isolated | Open two browser tabs, run in both — sessions never share context |

## Known limitations

- Sessions live in memory — restarting the server clears all sessions (by design for a demo; add Redis for persistence)
- Free Render tier sleeps after 15 min inactivity — first request after sleep takes ~30s to wake
- OpenRouter free models have rate limits — if you hit them, switch to a different free model in Config tab
- File upload supports text extraction only — PDFs are read as raw text (no OCR)

## Approximate model cost per run

| Model | Cost per run (3 agents) |
|---|---|
| `google/gemma-3-27b-it:free` | $0.00 (free tier) |
| `meta-llama/llama-3.1-8b-instruct:free` | $0.00 (free tier) |
| Any paid model (e.g. claude-sonnet) | ~$0.01–0.03 |

## AI tools used

- Claude (Anthropic) — architecture design, all code generation, UI design
- All code reviewed and understood before submission
