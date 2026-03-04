"""
Email Agent API — FastAPI Server
----------------------------------
REST + SSE endpoints wrapping the LangGraph email agent and Gmail API.

Usage:
    uvicorn server:app --reload --port 8000
"""

import base64
import json
import uuid

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from langchain_core.messages import HumanMessage

from agent import get_agent
from tools.gmail_auth import get_gmail_service
from tools.gmail_tools import (
    _validate_email_address,
    _validate_text_field,
    _decode_body,
    _clean_text,
)

app = FastAPI(title="Email Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_header_value(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class ComposeRequest(BaseModel):
    to: str
    subject: str
    body: str
    reply_to_message_id: str | None = None


class LabelRequest(BaseModel):
    add_labels: list[str] = []
    remove_labels: list[str] = []


# ---------------------------------------------------------------------------
# Email Endpoints (Direct Gmail API — no LLM)
# ---------------------------------------------------------------------------
@app.get("/api/emails")
async def list_emails(q: str = "in:inbox", max_results: int = 20):
    """List emails matching a Gmail search query."""
    service = get_gmail_service()
    max_results = min(max_results, 50)

    results = (
        service.users()
        .messages()
        .list(userId="me", q=q, maxResults=max_results)
        .execute()
    )

    messages = results.get("messages", [])
    if not messages:
        return {"emails": [], "query": q}

    fetched = {}

    def _on_response(req_id, response, exception):
        if exception is None:
            fetched[req_id] = response

    batch = service.new_batch_http_request(callback=_on_response)
    for msg in messages:
        batch.add(
            service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ),
            request_id=msg["id"],
        )
    batch.execute()

    emails = []
    for msg_meta in messages:
        m = fetched.get(msg_meta["id"])
        if not m:
            continue
        headers = m.get("payload", {}).get("headers", [])
        emails.append({
            "id": m["id"],
            "threadId": m.get("threadId"),
            "snippet": m.get("snippet", ""),
            "labelIds": m.get("labelIds", []),
            "subject": _get_header_value(headers, "Subject"),
            "from": _get_header_value(headers, "From"),
            "date": _get_header_value(headers, "Date"),
            "isUnread": "UNREAD" in m.get("labelIds", []),
        })

    return {"emails": emails, "query": q}


@app.get("/api/emails/{message_id}")
async def read_email(message_id: str):
    """Read a single email by ID."""
    service = get_gmail_service()

    try:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Email not found: {e}")

    headers = msg.get("payload", {}).get("headers", [])
    body = _clean_text(_decode_body(msg["payload"]))

    if len(body) > 10000:
        body = body[:10000] + "\n\n... [truncated]"

    return {
        "id": msg["id"],
        "threadId": msg.get("threadId"),
        "subject": _get_header_value(headers, "Subject"),
        "from": _get_header_value(headers, "From"),
        "to": _get_header_value(headers, "To"),
        "date": _get_header_value(headers, "Date"),
        "body": body,
        "snippet": msg.get("snippet", ""),
        "labelIds": msg.get("labelIds", []),
        "isUnread": "UNREAD" in msg.get("labelIds", []),
    }


@app.post("/api/emails/send")
async def send_email(req: ComposeRequest):
    """Send an email."""
    from email.mime.text import MIMEText

    to = _validate_email_address(req.to)
    subject = _validate_text_field(req.subject, "Subject", max_length=998)
    body = _validate_text_field(req.body, "Body", max_length=50000)

    service = get_gmail_service()

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    send_body = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}

    if req.reply_to_message_id:
        original = (
            service.users()
            .messages()
            .get(userId="me", id=req.reply_to_message_id, format="metadata",
                 metadataHeaders=["Message-ID"])
            .execute()
        )
        orig_header = _get_header_value(
            original.get("payload", {}).get("headers", []), "Message-ID"
        )
        if orig_header:
            message["In-Reply-To"] = orig_header
            message["References"] = orig_header
        send_body["threadId"] = original.get("threadId")
        send_body["raw"] = base64.urlsafe_b64encode(message.as_bytes()).decode()

    sent = service.users().messages().send(userId="me", body=send_body).execute()

    return {"message": "Email sent successfully", "id": sent["id"]}


@app.post("/api/emails/draft")
async def draft_email(req: ComposeRequest):
    """Create a draft email."""
    from email.mime.text import MIMEText

    to = _validate_email_address(req.to)
    subject = _validate_text_field(req.subject, "Subject", max_length=998)
    body = _validate_text_field(req.body, "Body", max_length=50000)

    service = get_gmail_service()

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    draft_body = {"message": {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}}

    if req.reply_to_message_id:
        original = (
            service.users()
            .messages()
            .get(userId="me", id=req.reply_to_message_id, format="metadata",
                 metadataHeaders=["Message-ID"])
            .execute()
        )
        orig_header = _get_header_value(
            original.get("payload", {}).get("headers", []), "Message-ID"
        )
        if orig_header:
            message["In-Reply-To"] = orig_header
            message["References"] = orig_header
        draft_body["message"]["threadId"] = original.get("threadId")
        draft_body["message"]["raw"] = base64.urlsafe_b64encode(message.as_bytes()).decode()

    draft = service.users().drafts().create(userId="me", body=draft_body).execute()

    return {"message": "Draft created successfully", "id": draft["id"]}


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------
@app.get("/api/labels")
async def list_labels():
    """List all Gmail labels."""
    service = get_gmail_service()
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])
    return {
        "labels": [
            {"id": lbl["id"], "name": lbl["name"], "type": lbl.get("type", "user")}
            for lbl in labels
        ]
    }


@app.post("/api/emails/{message_id}/labels")
async def modify_labels(message_id: str, req: LabelRequest):
    """Add or remove labels on an email."""
    if not req.add_labels and not req.remove_labels:
        raise HTTPException(status_code=400, detail="Must specify labels to add or remove")

    service = get_gmail_service()

    all_labels = service.users().labels().list(userId="me").execute().get("labels", [])
    label_map = {lbl["name"].upper(): lbl["id"] for lbl in all_labels}

    add_ids = [label_map.get(l.upper(), l) for l in req.add_labels]
    remove_ids = [label_map.get(l.upper(), l) for l in req.remove_labels]

    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": add_ids, "removeLabelIds": remove_ids},
    ).execute()

    return {"message": f"Labels updated for {message_id}"}


# ---------------------------------------------------------------------------
# Agent Chat (SSE Streaming)
# ---------------------------------------------------------------------------
@app.get("/api/chat")
async def chat_stream(message: str = Query(...), thread_id: str = Query(default=None)):
    """SSE endpoint for streaming agent chat responses."""
    if not thread_id:
        thread_id = str(uuid.uuid4())

    def event_generator():
        agent = get_agent()
        config = {"configurable": {"thread_id": thread_id}}

        yield {"event": "thread_id", "data": json.dumps({"thread_id": thread_id})}

        try:
            for event in agent.stream(
                {"messages": [HumanMessage(content=message)]},
                config=config,
                stream_mode="updates",
            ):
                for node_name, node_output in event.items():
                    if node_name == "agent":
                        for msg in node_output.get("messages", []):
                            if hasattr(msg, "content") and msg.content and isinstance(msg.content, str):
                                yield {
                                    "event": "agent_message",
                                    "data": json.dumps({"content": msg.content}),
                                }
                            elif hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    yield {
                                        "event": "tool_call",
                                        "data": json.dumps({
                                            "name": tc["name"],
                                            "args": tc["args"],
                                        }),
                                    }
                    elif node_name == "tools":
                        for msg in node_output.get("messages", []):
                            yield {
                                "event": "tool_result",
                                "data": json.dumps({
                                    "content": str(msg.content)[:500],
                                }),
                            }
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

        yield {"event": "done", "data": json.dumps({"status": "complete"})}

    return EventSourceResponse(event_generator())
