# Email AI Agent — LangGraph + Gmail

A full-stack email management platform powered by a LangGraph ReAct AI agent. Includes a **Next.js dashboard** with inbox, compose, and AI chat, backed by a **FastAPI** server and the **Gmail API**.

## Architecture

```
Browser (Next.js :3001)          FastAPI (:8001)           External
┌─────────────────────┐    REST  ┌──────────────────┐     ┌──────────┐
│  Inbox              │───────→  │  /api/emails     │────→│ Gmail API│
│  Compose            │───────→  │  /api/emails/send│────→│          │
│  Email Detail       │───────→  │  /api/labels     │────→│          │
│                     │    SSE   │                  │     └──────────┘
│  AI Agent Chat      │◀━━━━━━━  │  /api/chat (SSE) │────→┌──────────┐
└─────────────────────┘          │                  │     │ LLM      │
                                 │  LangGraph Agent │────→│(Claude/  │
                                 │  + MemorySaver   │     │ OpenAI)  │
                                 └──────────────────┘     └──────────┘
```

**Key design decisions:**
- Email CRUD operations call the Gmail API directly (no LLM cost)
- Only the AI chat routes through the LangGraph agent
- SSE streaming delivers real-time agent responses to the browser
- Demo mode activates automatically when `credentials.json` is absent

## Features

### Dashboard (Next.js)
- **Inbox** — email list with search, unread indicators, avatars, and detail view
- **Compose** — modal form for sending emails and saving drafts
- **AI Agent Chat** — SSE-streamed conversation with tool call badges
- **Responsive** — 3-column desktop layout; bottom tab nav on mobile

### Backend (FastAPI)
- `GET  /api/emails` — list emails (Gmail search query support)
- `GET  /api/emails/{id}` — read a single email
- `POST /api/emails/send` — send an email
- `POST /api/emails/draft` — save a draft
- `GET  /api/labels` — list Gmail labels
- `POST /api/emails/{id}/labels` — add/remove labels
- `GET  /api/chat` — SSE stream for AI agent conversation

### CLI Agent
- Interactive terminal interface via `main.py`
- Same LangGraph agent and Gmail tools as the web version

### AI Agent Tools

| Tool | Description |
|------|-------------|
| `search_emails` | Search Gmail using native query syntax (`from:`, `is:unread`, `after:`, etc.) |
| `read_email` | Read full email content by message ID |
| `draft_email` | Create a draft (saved for review, not sent) |
| `send_email` | Send an email directly |
| `label_email` | Add/remove labels to classify emails |

### Security Hardening
- Email address validation with regex + header injection prevention
- Text field sanitization (rejects `\r`, `\0`, enforces max length)
- OAuth token file permissions set to `600`
- Gmail service client caching (singleton)
- MemorySaver checkpointing for agent conversation memory

## Quick Start

### Demo Mode (no Gmail credentials needed)

```bash
# 1. Install backend dependencies
cd email-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Start the FastAPI backend
uvicorn server:app --reload --port 8001

# 3. In another terminal, install and start the dashboard
cd email-agent/dashboard
npm install
npm run dev -- --port 3001

# 4. Open http://localhost:3001
```

Demo mode serves sample emails and a simulated AI agent chat. No API keys or Gmail setup required.

### Production Mode (with Gmail)

#### 1. Google Cloud Project & OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable the **Gmail API**: APIs & Services > Library > search "Gmail API" > Enable
4. Create OAuth credentials:
   - APIs & Services > Credentials > Create Credentials > OAuth 2.0 Client ID
   - Application type: **Desktop app**
   - Download the JSON file and save as `credentials.json` in the `email-agent/` directory
5. Configure OAuth consent screen:
   - Add your email as a test user (required while app is in "Testing" status)

#### 2. Configure Environment

```bash
cd email-agent
cp .env.example .env
# Edit .env with your LLM API key:
#   ANTHROPIC_API_KEY=sk-ant-...   (for Claude)
#   OPENAI_API_KEY=sk-...          (for GPT)
```

#### 3. Run

```bash
# Backend
uvicorn server:app --reload --port 8001

# Dashboard (separate terminal)
cd dashboard && npm run dev -- --port 3001

# Or CLI only
python main.py
```

On first run, a browser window opens for Gmail OAuth consent. After authorizing, a `token.json` is cached locally for future runs.

## Project Structure

```
email-agent/
├── server.py               # FastAPI backend — REST + SSE endpoints
├── agent.py                # LangGraph ReAct agent definition + system prompt
├── main.py                 # Interactive CLI entry point
├── tools/
│   ├── __init__.py
│   ├── gmail_auth.py       # OAuth2 auth, token caching, service singleton
│   └── gmail_tools.py      # LangChain tools (search, read, draft, send, label)
├── dashboard/              # Next.js 14 frontend
│   ├── src/
│   │   ├── app/            # App Router pages (inbox, chat, compose)
│   │   ├── components/     # UI components (layout, inbox, chat, compose, ui)
│   │   ├── hooks/          # React hooks (useEmails, useEmail, useChat, useLabels)
│   │   ├── lib/            # API client, SSE client, utilities
│   │   └── types/          # TypeScript interfaces
│   ├── package.json
│   └── tailwind.config.ts
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── credentials.json        # (you provide) Google OAuth client credentials
└── token.json              # (auto-generated) Cached OAuth token
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For Claude | Anthropic API key |
| `OPENAI_API_KEY` | For GPT | OpenAI API key |
| `NEXT_PUBLIC_API_URL` | No | Backend URL (defaults to `http://localhost:8000`) |

## Extending the Agent

**Add a new tool:**
1. Define a new `@tool`-decorated function in `tools/gmail_tools.py`
2. Add it to the `gmail_tools` list at the bottom of that file
3. The agent automatically picks it up — both CLI and web chat use it

**Ideas for extensions:**
- `create_label` — create custom labels for auto-classification
- `search_contacts` — integrate Google Contacts API
- `summarize_thread` — read all messages in a thread and summarize
- `schedule_send` — use Gmail's scheduled send feature
- Replace `MemorySaver` with `SqliteSaver` for persistent conversation memory across restarts
