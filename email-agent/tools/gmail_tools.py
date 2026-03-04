"""
Gmail Tools for LangGraph Agent
---------------------------------
LangChain-compatible tools for searching, reading, drafting, and sending emails.
"""

import base64
import re
from email.mime.text import MIMEText
from typing import Optional

from langchain_core.tools import tool

from tools.gmail_auth import get_gmail_service

# ---------------------------------------------------------------------------
# Input Validation Helpers
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def _validate_email_address(addr: str) -> str:
    """Validate and sanitize an email address to prevent header injection."""
    addr = addr.strip()
    if '\n' in addr or '\r' in addr or '\0' in addr:
        raise ValueError(f"Invalid email address (contains illegal characters): {addr!r}")
    if not _EMAIL_RE.match(addr):
        raise ValueError(f"Invalid email address format: {addr!r}")
    return addr


def _validate_text_field(value: str, field_name: str, max_length: int = 10000) -> str:
    """Validate a text field to prevent header injection and enforce limits."""
    if '\r' in value or '\0' in value:
        raise ValueError(f"{field_name} contains illegal characters")
    if len(value) > max_length:
        raise ValueError(f"{field_name} exceeds maximum length of {max_length} characters")
    return value


def _decode_body(payload: dict) -> str:
    """Recursively extract plain-text body from Gmail message payload."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        text = _decode_body(part)
        if text:
            return text
    return ""


def _clean_text(text: str) -> str:
    """Strip excessive whitespace and clean up email body text."""
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _get_header(headers: list, name: str) -> str:
    """Extract a specific header value from Gmail message headers."""
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


# ---------------------------------------------------------------------------
# Tool 1: Search Emails
# ---------------------------------------------------------------------------
@tool
def search_emails(query: str, max_results: int = 10) -> str:
    """Search Gmail using Gmail search syntax.

    Args:
        query: Gmail search query (e.g., 'from:boss@company.com subject:urgent',
               'is:unread after:2024/01/01', 'label:inbox has:attachment').
        max_results: Maximum number of results to return (default 10, max 50).

    Returns:
        A formatted string listing matching emails with ID, subject, from, date, and snippet.
    """
    service = get_gmail_service()
    max_results = min(max_results, 50)

    results = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )

    messages = results.get("messages", [])
    if not messages:
        return f"No emails found for query: '{query}'"

    # Batch-fetch metadata for all messages in a single HTTP request
    fetched = {}

    def _on_response(req_id, response, exception):
        if exception is None:
            fetched[req_id] = response

    batch = service.new_batch_http_request(callback=_on_response)
    for msg_meta in messages:
        batch.add(
            service.users().messages().get(
                userId="me", id=msg_meta["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ),
            request_id=msg_meta["id"],
        )
    batch.execute()

    output_lines = [f"Found {len(messages)} email(s) for query: '{query}'\n"]

    for msg_meta in messages:
        msg = fetched.get(msg_meta["id"])
        if not msg:
            continue
        headers = msg.get("payload", {}).get("headers", [])
        output_lines.append(
            f"- ID: {msg['id']}\n"
            f"  Subject: {_get_header(headers, 'Subject')}\n"
            f"  From: {_get_header(headers, 'From')}\n"
            f"  Date: {_get_header(headers, 'Date')}\n"
            f"  Snippet: {msg.get('snippet', '')[:120]}\n"
        )

    return "\n".join(output_lines)


# ---------------------------------------------------------------------------
# Tool 2: Read Email
# ---------------------------------------------------------------------------
@tool
def read_email(message_id: str) -> str:
    """Read the full content of a specific email by its message ID.

    Args:
        message_id: The Gmail message ID (obtained from search_emails results).

    Returns:
        The full email including headers and body text.
    """
    service = get_gmail_service()

    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )

    headers = msg.get("payload", {}).get("headers", [])
    body = _clean_text(_decode_body(msg["payload"]))

    # Truncate very long emails to keep context window manageable
    if len(body) > 4000:
        body = body[:4000] + "\n\n... [truncated — email too long]"

    labels = ", ".join(msg.get("labelIds", []))

    return (
        f"Subject: {_get_header(headers, 'Subject')}\n"
        f"From: {_get_header(headers, 'From')}\n"
        f"To: {_get_header(headers, 'To')}\n"
        f"Date: {_get_header(headers, 'Date')}\n"
        f"Labels: {labels}\n"
        f"{'=' * 50}\n"
        f"{body}"
    )


# ---------------------------------------------------------------------------
# Tool 3: Draft Email
# ---------------------------------------------------------------------------
@tool
def draft_email(
    to: str,
    subject: str,
    body: str,
    reply_to_message_id: Optional[str] = None,
) -> str:
    """Create a draft email in Gmail (does NOT send it).

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body text (plain text).
        reply_to_message_id: Optional message ID to make this a reply thread.

    Returns:
        Confirmation with the draft ID.
    """
    to = _validate_email_address(to)
    subject = _validate_text_field(subject, "Subject", max_length=998)
    body = _validate_text_field(body, "Body", max_length=50000)

    service = get_gmail_service()

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    draft_body = {"message": {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}}

    # If replying, thread it
    if reply_to_message_id:
        original = (
            service.users()
            .messages()
            .get(userId="me", id=reply_to_message_id, format="metadata",
                 metadataHeaders=["Message-ID"])
            .execute()
        )
        orig_msg_id_header = _get_header(
            original.get("payload", {}).get("headers", []), "Message-ID"
        )
        if orig_msg_id_header:
            message["In-Reply-To"] = orig_msg_id_header
            message["References"] = orig_msg_id_header
        draft_body["message"]["threadId"] = original.get("threadId")
        # Re-encode after adding headers
        draft_body["message"]["raw"] = base64.urlsafe_b64encode(message.as_bytes()).decode()

    draft = service.users().drafts().create(userId="me", body=draft_body).execute()

    return (
        f"Draft created successfully!\n"
        f"  Draft ID: {draft['id']}\n"
        f"  To: {to}\n"
        f"  Subject: {subject}\n"
        f"  Body preview: {body[:200]}..."
    )


# ---------------------------------------------------------------------------
# Tool 4: Send Email
# ---------------------------------------------------------------------------
@tool
def send_email(
    to: str,
    subject: str,
    body: str,
    reply_to_message_id: Optional[str] = None,
) -> str:
    """Send an email directly via Gmail.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body text (plain text).
        reply_to_message_id: Optional message ID to thread this as a reply.

    Returns:
        Confirmation with the sent message ID.
    """
    to = _validate_email_address(to)
    subject = _validate_text_field(subject, "Subject", max_length=998)
    body = _validate_text_field(body, "Body", max_length=50000)

    service = get_gmail_service()

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    send_body = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}

    if reply_to_message_id:
        original = (
            service.users()
            .messages()
            .get(userId="me", id=reply_to_message_id, format="metadata",
                 metadataHeaders=["Message-ID"])
            .execute()
        )
        orig_msg_id_header = _get_header(
            original.get("payload", {}).get("headers", []), "Message-ID"
        )
        if orig_msg_id_header:
            message["In-Reply-To"] = orig_msg_id_header
            message["References"] = orig_msg_id_header
        send_body["threadId"] = original.get("threadId")
        send_body["raw"] = base64.urlsafe_b64encode(message.as_bytes()).decode()

    sent = service.users().messages().send(userId="me", body=send_body).execute()

    return (
        f"Email sent successfully!\n"
        f"  Message ID: {sent['id']}\n"
        f"  To: {to}\n"
        f"  Subject: {subject}"
    )


# ---------------------------------------------------------------------------
# Tool 5: Label / Classify Email
# ---------------------------------------------------------------------------
@tool
def label_email(message_id: str, add_labels: list[str] | None = None, remove_labels: list[str] | None = None) -> str:
    """Add or remove labels on an email to classify/organize it.

    Args:
        message_id: The Gmail message ID.
        add_labels: List of label names to add (e.g., ['IMPORTANT', 'STARRED']).
        remove_labels: List of label names to remove (e.g., ['UNREAD', 'INBOX']).

    Returns:
        Confirmation of label changes.
    """
    add_labels = add_labels or []
    remove_labels = remove_labels or []

    if not add_labels and not remove_labels:
        return "Error: must specify at least one label to add or remove."

    service = get_gmail_service()

    # Resolve label names to IDs
    all_labels = service.users().labels().list(userId="me").execute().get("labels", [])
    label_map = {lbl["name"].upper(): lbl["id"] for lbl in all_labels}

    add_ids = [label_map.get(l.upper(), l) for l in add_labels]
    remove_ids = [label_map.get(l.upper(), l) for l in remove_labels]

    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": add_ids, "removeLabelIds": remove_ids},
    ).execute()

    return (
        f"Labels updated for message {message_id}:\n"
        f"  Added: {add_labels or 'none'}\n"
        f"  Removed: {remove_labels or 'none'}"
    )


# ---------------------------------------------------------------------------
# Export all tools as a list for the agent
# ---------------------------------------------------------------------------
gmail_tools = [search_emails, read_email, draft_email, send_email, label_email]
