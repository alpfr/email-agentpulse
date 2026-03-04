"""
skeleton.models — Pydantic models that define every data contract in the skeleton.

These models flow between the Runner, Planner, Evaluator, Tool Registry,
and State Backend.  Every field is typed and documented so the contracts
are self-describing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────
# Tool-related models
# ──────────────────────────────────────────────────────────────────────


class ToolInfo(BaseModel):
    """Metadata about a registered tool — sent to the LLM so it knows what's available."""

    name: str
    description: str
    parameters_schema: dict[str, Any]  # JSON Schema for the tool's arguments
    timeout_seconds: float
    max_retries: int
    idempotent: bool


class ToolCall(BaseModel):
    """A single tool invocation decided by the Planner."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(default_factory=lambda: uuid4().hex)
    reasoning: str = ""  # Why the planner chose this tool


class ToolReceipt(BaseModel):
    """
    Immutable record of a tool execution — the "receipt".

    Captures timing, status, result/error, retry metadata, and the
    idempotency key so the full audit trail is preserved.
    """

    tool_name: str
    arguments: dict[str, Any]
    idempotency_key: str
    status: Literal["success", "error", "timeout", "skipped_duplicate"]
    result: Any | None = None
    error: str | None = None
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    attempt: int  # Which retry attempt produced this receipt (1-based)
    total_attempts: int  # How many attempts were made in total


# ──────────────────────────────────────────────────────────────────────
# Planner / Evaluator decisions
# ──────────────────────────────────────────────────────────────────────


class PlannerDecision(BaseModel):
    """The Planner's output — either call a tool or finish."""

    action: Literal["call_tool", "finish"]
    tool_call: ToolCall | None = None  # Present when action == "call_tool"
    final_answer: str | None = None  # Present when action == "finish"
    reasoning: str = ""


class EvaluationResult(BaseModel):
    """The Evaluator's assessment after each tool call."""

    goal_achieved: bool
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    reasoning: str = ""
    should_continue: bool = True  # False → agent stops even if goal not achieved


# ──────────────────────────────────────────────────────────────────────
# Agent state (persisted across steps)
# ──────────────────────────────────────────────────────────────────────


class AgentState(BaseModel):
    """
    The full mutable state of an agent run.

    Stored by the StateBackend between steps for crash recovery,
    session resume, and audit.
    """

    session_id: str = Field(default_factory=lambda: uuid4().hex)
    goal: str
    context: dict[str, Any] = Field(default_factory=dict)
    receipts: list[ToolReceipt] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    step_count: int = 0
    status: Literal["running", "completed", "failed", "max_steps_exceeded"] = "running"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ──────────────────────────────────────────────────────────────────────
# Top-level request / response
# ──────────────────────────────────────────────────────────────────────


class AgentInput(BaseModel):
    """Incoming request to the agent — validated on construction."""

    goal: str = Field(min_length=1, max_length=4096)
    context: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None  # Provide to resume an existing session
    max_steps: int = Field(default=10, ge=1, le=50)
    allowed_tools: list[str] | None = None  # None == all tools allowed


class AgentResponse(BaseModel):
    """Final response returned to the caller — includes the full audit trail."""

    session_id: str
    answer: str
    goal_achieved: bool
    receipts: list[ToolReceipt]
    steps_taken: int
    status: str
