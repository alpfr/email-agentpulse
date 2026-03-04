"""
skeleton.gmail_tools — Gmail tools adapted for the skeleton agent framework.

Wraps the existing synchronous Gmail tools (tools/gmail_tools.py) as async
@agent_tool functions, ready for use with ToolRegistry and AgentRunner.

The existing tools use the Gmail API client (synchronous I/O).  We use
asyncio.to_thread() to run them off the event loop, keeping the agent
fully non-blocking.

Usage:
    from skeleton.gmail_tools import gmail_registry

    # Merge into your agent's combined registry
    combined = ToolRegistry()
    for tool_info in gmail_registry.list_tools():
        original = gmail_registry.get(tool_info.name)
        combined.register(original.fn, name=original.name, ...)

    runner = AgentRunner(registry=combined, ...)

Tools provided:
    • search_emails  — Search Gmail with Gmail search syntax
    • read_email     — Read full content of a specific email
    • draft_email    — Create a draft email (does NOT send)
    • send_email     — Send an email directly
    • label_email    — Add/remove labels on an email
"""

from __future__ import annotations

import asyncio
import logging
import sys
import os

from .tools import ToolRegistry, agent_tool

logger = logging.getLogger(__name__)

# ── Ensure project root is on sys.path so we can import tools.* ──
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ── Import the existing sync Gmail functions ──
# These are the raw functions from tools/gmail_tools.py.
# We import them by their underlying callable (the .func attribute
# of LangChain's @tool wrapper, or the function itself).
from tools.gmail_tools import (
    search_emails as _lc_search_emails,
    read_email as _lc_read_email,
    draft_email as _lc_draft_email,
    send_email as _lc_send_email,
    label_email as _lc_label_email,
)

# LangChain @tool wraps functions — get the original callable
# The @tool decorator returns a BaseTool with .func pointing to the original
_search_emails_sync = getattr(_lc_search_emails, "func", _lc_search_emails)
_read_email_sync = getattr(_lc_read_email, "func", _lc_read_email)
_draft_email_sync = getattr(_lc_draft_email, "func", _lc_draft_email)
_send_email_sync = getattr(_lc_send_email, "func", _lc_send_email)
_label_email_sync = getattr(_lc_label_email, "func", _lc_label_email)


# ──────────────────────────────────────────────────────────────────────
# Gmail Tool Registry
# ──────────────────────────────────────────────────────────────────────

gmail_registry = ToolRegistry()


# ──────────────────────────────────────────────────────────────────────
# Tool 1: Search Emails
# ──────────────────────────────────────────────────────────────────────

@agent_tool(
    name="search_emails",
    description=(
        "Search Gmail using Gmail search syntax. "
        "Examples: 'from:boss@company.com subject:urgent', "
        "'is:unread after:2024/01/01', 'label:inbox has:attachment'. "
        "Returns a list of matching emails with ID, subject, from, date, and snippet."
    ),
    timeout_seconds=30,
    max_retries=2,
    idempotent=True,
    registry=gmail_registry,
)
async def search_emails(query: str, max_results: int = 10) -> str:
    """Search Gmail using Gmail search syntax."""
    return await asyncio.to_thread(_search_emails_sync, query, max_results)


# ──────────────────────────────────────────────────────────────────────
# Tool 2: Read Email
# ──────────────────────────────────────────────────────────────────────

@agent_tool(
    name="read_email",
    description=(
        "Read the full content of a specific email by its Gmail message ID. "
        "Use search_emails first to find the message ID. "
        "Returns the full email including headers (subject, from, to, date) and body text."
    ),
    timeout_seconds=15,
    max_retries=2,
    idempotent=True,
    registry=gmail_registry,
)
async def read_email(message_id: str) -> str:
    """Read a specific email by message ID."""
    return await asyncio.to_thread(_read_email_sync, message_id)


# ──────────────────────────────────────────────────────────────────────
# Tool 3: Draft Email
# ──────────────────────────────────────────────────────────────────────

@agent_tool(
    name="draft_email",
    description=(
        "Create a draft email in Gmail (does NOT send it). "
        "Use this to compose replies or new emails for the user to review. "
        "Optionally thread as a reply by providing reply_to_message_id."
    ),
    timeout_seconds=15,
    max_retries=1,
    idempotent=False,  # Creating a draft is not idempotent
    registry=gmail_registry,
)
async def draft_email(
    to: str,
    subject: str,
    body: str,
    reply_to_message_id: str = "",
) -> str:
    """Create a draft email in Gmail."""
    kwargs: dict = {"to": to, "subject": subject, "body": body}
    if reply_to_message_id:
        kwargs["reply_to_message_id"] = reply_to_message_id
    return await asyncio.to_thread(_draft_email_sync, **kwargs)


# ──────────────────────────────────────────────────────────────────────
# Tool 4: Send Email
# ──────────────────────────────────────────────────────────────────────

@agent_tool(
    name="send_email",
    description=(
        "Send an email directly via Gmail. "
        "WARNING: This sends the email immediately — use draft_email if the user "
        "should review first. Optionally thread as a reply with reply_to_message_id."
    ),
    timeout_seconds=20,
    max_retries=1,
    idempotent=False,  # Sending an email is definitely not idempotent
    registry=gmail_registry,
)
async def send_email(
    to: str,
    subject: str,
    body: str,
    reply_to_message_id: str = "",
) -> str:
    """Send an email via Gmail."""
    kwargs: dict = {"to": to, "subject": subject, "body": body}
    if reply_to_message_id:
        kwargs["reply_to_message_id"] = reply_to_message_id
    return await asyncio.to_thread(_send_email_sync, **kwargs)


# ──────────────────────────────────────────────────────────────────────
# Tool 5: Label Email
# ──────────────────────────────────────────────────────────────────────

@agent_tool(
    name="label_email",
    description=(
        "Add or remove labels on a Gmail email to classify/organize it. "
        "Common labels: IMPORTANT, STARRED, UNREAD, INBOX, SPAM, TRASH. "
        "Provide at least one of add_labels or remove_labels."
    ),
    timeout_seconds=10,
    max_retries=2,
    idempotent=True,  # Label operations are idempotent
    registry=gmail_registry,
)
async def label_email(
    message_id: str,
    add_labels: str = "",
    remove_labels: str = "",
) -> str:
    """Add or remove labels on an email.

    Labels are comma-separated strings (e.g., 'IMPORTANT,STARRED').
    The LLM sends strings; we parse them into lists for the Gmail API.
    """
    # Parse comma-separated label strings into lists
    add_list = [l.strip() for l in add_labels.split(",") if l.strip()] if add_labels else []
    remove_list = [l.strip() for l in remove_labels.split(",") if l.strip()] if remove_labels else []

    return await asyncio.to_thread(
        _label_email_sync,
        message_id=message_id,
        add_labels=add_list or None,
        remove_labels=remove_list or None,
    )
