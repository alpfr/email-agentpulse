# Email AgentPulse

Full-stack email management platform powered by a LangGraph ReAct AI agent. See [email-agent/README.md](email-agent/README.md) for full documentation.

## Quick Start (Demo Mode)

```bash
# Backend
cd email-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --port 8001

# Frontend (separate terminal)
cd email-agent/dashboard
npm install
npm run dev -- --port 3001
```

Open **http://localhost:3001** — runs with sample data, no Gmail credentials needed.

## Stack

- **Frontend**: Next.js 14 (App Router) + Tailwind CSS
- **Backend**: FastAPI + SSE streaming
- **AI Agent**: LangGraph ReAct agent (Claude / GPT)
- **Email**: Gmail API with OAuth2
