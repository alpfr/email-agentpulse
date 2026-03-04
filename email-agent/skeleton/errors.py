"""
skeleton.errors — Structured exception hierarchy for the agent skeleton.

Every exception carries a machine-readable `code` and optional `details` dict
so callers can handle errors programmatically, not just by type.
"""

from __future__ import annotations

from typing import Any


class AgentError(Exception):
    """Base exception for all agent skeleton errors."""

    code: str = "AGENT_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(AgentError):
    """Input validation failed (bad goal, unknown tool, out-of-range max_steps)."""

    code = "VALIDATION_ERROR"


class StateError(AgentError):
    """State backend failed to load or save."""

    code = "STATE_ERROR"


class PlannerError(AgentError):
    """The planner (LLM) failed to produce a valid decision."""

    code = "PLANNER_ERROR"


class ToolExecutionError(AgentError):
    """A tool raised an unexpected exception during execution."""

    code = "TOOL_EXECUTION_ERROR"


class ToolTimeoutError(ToolExecutionError):
    """A tool exceeded its configured timeout after all retries."""

    code = "TOOL_TIMEOUT_ERROR"


class ToolNotFoundError(AgentError):
    """A requested tool does not exist in the registry."""

    code = "TOOL_NOT_FOUND"


class MaxStepsExceededError(AgentError):
    """The agent hit its configured max_steps bound without reaching the goal."""

    code = "MAX_STEPS_EXCEEDED"
