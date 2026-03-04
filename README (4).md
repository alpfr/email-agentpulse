# 📧 Email AI Agent — LangGraph + Gmail

A ReAct-style AI agent that manages your Gmail using natural language. Built with **LangGraph** for agentic workflows and the **Gmail API** for full email access.

## Architecture

```
User Input
    │
    ▼
┌──────────────────────────────────────┐
│         LangGraph ReAct Agent        │
│  (Claude / GPT decides what to do)   │
│                                      │
│  ┌──────────┐  ┌──────────────────┐  │
│  │ Reason   │→ │ Pick & Call Tool  │  │
│  └──────────┘  └──────────────────┘  │
│       ▲              │               │
│       └──────────────┘  (loop)       │
└──────────────┬───────────────────────┘
               │
    ┌──────────┼──────────────┐
    ▼          ▼              ▼
┌────────┐ ┌────────┐ ┌───────────┐
│ Search │ │  Read  │ │Draft/Send │
│ Emails │ │ Email  │ │  Email    │
└────────┘ └────────┘ └───────────┘
    │          │              │
    └──────────┴──────────────┘
               │
          Gmail API
```

## Tools

| Tool | Description |
|------|-------------|
| `search_emails` | Search Gmail using native query syntax (`from:`, `is:unread`, `after:`, etc.) |
| `read_email` | Read full email content by message ID |
| `draft_email` | Create a draft (saved for review, not sent) |
| `send_email` | Send an email directly |
| `label_email` | Add/remove labels to classify emails |

## Setup

### 1. Google Cloud Project & OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable the **Gmail API**: APIs & Services → Library → search "Gmail API" → Enable
4. Create OAuth credentials:
   - APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
   - Application type: **Desktop app**
   - Download the JSON file → save as `credentials.json` in this project root
5. Configure OAuth consent screen:
   - Add your email as a test user (required while app is in "Testing" status)

### 2. Install Dependencies

```bash
cd email-agent
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API key (Anthropic or OpenAI)
```

### 4. Run

```bash
python main.py
```

On first run, a browser window opens for Gmail OAuth consent. After authorizing, a `token.json` is cached locally for future runs.

## Example Prompts

```
You: Show me unread emails from today
You: Find emails from john@example.com about the project proposal
You: Read the latest email from my boss
You: Summarize my last 5 emails
You: Draft a reply to message ID abc123 thanking them for the update
You: Label all emails from newsletters@example.com as "Newsletters"
You: Find emails with attachments from last week
```

## Project Structure

```
email-agent/
├── main.py              # Interactive CLI entry point
├── agent.py             # LangGraph agent definition + system prompt
├── tools/
│   ├── __init__.py
│   ├── gmail_auth.py    # OAuth2 authentication helper
│   └── gmail_tools.py   # LangChain tool definitions (search, read, draft, send, label)
├── credentials.json     # (you provide) Google OAuth client credentials
├── token.json           # (auto-generated) Cached OAuth token
├── .env.example         # Environment variable template
├── .env                 # (you create) Your API keys
└── requirements.txt
```

## Extending the Agent

**Add a new tool:**
1. Define a new `@tool`-decorated function in `tools/gmail_tools.py`
2. Add it to the `gmail_tools` list at the bottom of that file
3. The agent automatically picks it up

**Ideas for extensions:**
- `list_labels` — show all available Gmail labels
- `create_label` — create custom labels for auto-classification
- `search_contacts` — integrate Google Contacts API
- `summarize_thread` — read all messages in a thread and summarize
- `schedule_send` — use Gmail's scheduled send feature
- Add **LangGraph checkpointing** with `SqliteSaver` for persistent conversation memory
- Add a **FastAPI wrapper** to serve the agent as an API
