"""
Email AI Agent — LangGraph Implementation
-------------------------------------------
A ReAct-style agent that can search, read, draft, send, and classify Gmail emails.
Uses LangGraph's prebuilt agent with tool-calling for structured multi-step workflows.
"""

import os
from dotenv import load_dotenv
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage

from tools import gmail_tools

load_dotenv()

# ---------------------------------------------------------------------------
# LLM Configuration
# ---------------------------------------------------------------------------
def _build_llm():
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    model = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=0)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=0)
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}. Use 'anthropic' or 'openai'.")


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an intelligent email assistant with access to the user's Gmail account.

## Capabilities
- **Search** emails using Gmail query syntax (from:, to:, subject:, is:unread, after:, before:, label:, has:attachment, etc.)
- **Read** full email content by message ID
- **Draft** emails (saved as drafts for user review)
- **Send** emails directly
- **Classify** emails by adding/removing labels

## Guidelines
1. **Always search first** before answering questions about emails.
2. **Summarize concisely** — don't dump raw email content unless the user asks for the full text.
3. **Ask for confirmation** before sending emails. Prefer drafting first.
4. **Preserve threading** — when replying, always use `reply_to_message_id` so the reply appears in the correct thread.
5. **Be privacy-aware** — don't share email content unless the user explicitly requests it.
6. **For classification tasks**, read the emails first, then apply labels or provide a summary with categories.

## Example Workflows
- "Find unread emails from my manager" → search_emails → summarize results
- "Reply to the latest email from Alice" → search → read → draft_email (with reply_to_message_id) → confirm → send
- "Summarize my emails from today" → search → read each → provide summary
- "Label all newsletters as 'Newsletters'" → search → label_email for each
"""

# ---------------------------------------------------------------------------
# Build the Agent Graph
# ---------------------------------------------------------------------------
def build_agent():
    """Create and return the LangGraph email agent."""
    llm = _build_llm()

    agent = create_react_agent(
        model=llm,
        tools=gmail_tools,
        prompt=SystemMessage(content=SYSTEM_PROMPT),
        checkpointer=MemorySaver(),
    )

    return agent


def get_agent():
    """Singleton-style accessor for the agent."""
    if not hasattr(get_agent, "_instance"):
        get_agent._instance = build_agent()
    return get_agent._instance
