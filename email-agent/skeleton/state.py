"""
skeleton.state — Pluggable state persistence for the agent skeleton.

The StateBackend protocol defines the contract.  Swap InMemoryStateBackend
for Redis, PostgreSQL, DynamoDB, etc. without changing the runner.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

from .errors import StateError
from .models import AgentState

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Protocol (interface)
# ──────────────────────────────────────────────────────────────────────


@runtime_checkable
class StateBackend(Protocol):
    """
    Pluggable storage for AgentState.

    Implement this protocol to use any persistence layer.
    All methods are async so network-based backends work naturally.
    """

    async def load(self, session_id: str) -> AgentState | None:
        """Load state by session_id.  Returns None if not found."""
        ...

    async def save(self, state: AgentState) -> None:
        """Persist the current state (upsert)."""
        ...

    async def delete(self, session_id: str) -> None:
        """Remove state for a session.  No-op if not found."""
        ...


# ──────────────────────────────────────────────────────────────────────
# In-Memory implementation (dev / testing)
# ──────────────────────────────────────────────────────────────────────


class InMemoryStateBackend:
    """
    Dict-backed state store.  Fast but lost on process restart.
    Ideal for local development and unit tests.
    """

    def __init__(self) -> None:
        self._store: dict[str, AgentState] = {}

    async def load(self, session_id: str) -> AgentState | None:
        state = self._store.get(session_id)
        if state is not None:
            logger.debug("State loaded for session %s (step %d)", session_id, state.step_count)
        return state

    async def save(self, state: AgentState) -> None:
        state.updated_at = datetime.now(timezone.utc)
        self._store[state.session_id] = state
        logger.debug(
            "State saved for session %s (step %d, status=%s)",
            state.session_id,
            state.step_count,
            state.status,
        )

    async def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)
        logger.debug("State deleted for session %s", session_id)


# ──────────────────────────────────────────────────────────────────────
# File-based implementation (simple persistence across restarts)
# ──────────────────────────────────────────────────────────────────────


class FileStateBackend:
    """
    JSON-file-backed state store.  One file per session.
    Survives process restarts.  Not suitable for multi-process or
    high-concurrency workloads — use Redis/DB for that.
    """

    def __init__(self, directory: str | Path = ".agent_state") -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        # Sanitize session_id to prevent path traversal
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return self._dir / f"{safe_id}.json"

    async def load(self, session_id: str) -> AgentState | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return AgentState.model_validate(data)
        except Exception as exc:
            raise StateError(
                f"Failed to load state from {path}",
                details={"session_id": session_id, "error": str(exc)},
            ) from exc

    async def save(self, state: AgentState) -> None:
        state.updated_at = datetime.now(timezone.utc)
        path = self._path(state.session_id)
        try:
            path.write_text(
                state.model_dump_json(indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            raise StateError(
                f"Failed to save state to {path}",
                details={"session_id": state.session_id, "error": str(exc)},
            ) from exc

    async def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        if path.exists():
            path.unlink()
