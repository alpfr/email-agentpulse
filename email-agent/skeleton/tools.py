"""
skeleton.tools — Tool registry, decorator, and execution engine.

Provides:
  • @agent_tool decorator to register async functions as tools
  • ToolRegistry to manage the catalogue of available tools
  • execute_tool() to call a tool with timeout, retries, exponential
    backoff, jitter, and idempotency enforcement
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from .errors import ToolExecutionError, ToolNotFoundError, ToolTimeoutError
from .models import ToolCall, ToolInfo, ToolReceipt

logger = logging.getLogger(__name__)

# Type alias for an async tool function
AsyncToolFn = Callable[..., Coroutine[Any, Any, Any]]


# ──────────────────────────────────────────────────────────────────────
# RegisteredTool data class
# ──────────────────────────────────────────────────────────────────────


@dataclass
class RegisteredTool:
    """Internal record of a registered tool and its metadata."""

    name: str
    description: str
    fn: AsyncToolFn
    parameters_schema: dict[str, Any]
    timeout_seconds: float = 30.0
    max_retries: int = 2
    idempotent: bool = False

    def to_info(self) -> ToolInfo:
        return ToolInfo(
            name=self.name,
            description=self.description,
            parameters_schema=self.parameters_schema,
            timeout_seconds=self.timeout_seconds,
            max_retries=self.max_retries,
            idempotent=self.idempotent,
        )


# ──────────────────────────────────────────────────────────────────────
# Schema extraction from function signature
# ──────────────────────────────────────────────────────────────────────


_PY_TYPE_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}

# Also map string representations (from `from __future__ import annotations`)
_PY_STR_TO_JSON: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
}


def _resolve_json_type(hint: Any) -> str:
    """Resolve a Python type hint (or its string form) to a JSON Schema type."""
    # Direct type match
    if hint in _PY_TYPE_TO_JSON:
        return _PY_TYPE_TO_JSON[hint]
    # String annotation (from __future__ annotations or Python 3.12+)
    if isinstance(hint, str) and hint in _PY_STR_TO_JSON:
        return _PY_STR_TO_JSON[hint]
    return "string"


def _build_parameters_schema(fn: Callable) -> dict[str, Any]:
    """
    Build a JSON Schema 'properties' dict from a function's type hints.
    This gives the LLM a structured description of what arguments the tool accepts.
    Handles both real types and string annotations (from __future__ import annotations).
    """
    sig = inspect.signature(fn)
    # Use typing.get_type_hints() for resolved types, fall back to __annotations__
    try:
        import typing
        hints = typing.get_type_hints(fn)
    except Exception:
        hints = fn.__annotations__ if hasattr(fn, "__annotations__") else {}
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls", "return"):
            continue
        hint = hints.get(param_name, Any)

        # Resolve to JSON Schema type
        json_type = _resolve_json_type(hint)
        prop: dict[str, Any] = {"type": json_type}

        # If there's a default, include it
        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default
        else:
            required.append(param_name)

        properties[param_name] = prop

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


# ──────────────────────────────────────────────────────────────────────
# Tool Registry
# ──────────────────────────────────────────────────────────────────────


class ToolRegistry:
    """
    Catalogue of all available tools.

    Tools can be added via:
      1. The @agent_tool decorator
      2. registry.register(fn, name=..., ...)
    """

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        fn: AsyncToolFn,
        *,
        name: str | None = None,
        description: str = "",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        idempotent: bool = False,
    ) -> RegisteredTool:
        """Register an async function as a tool."""
        tool_name = name or fn.__name__
        if not asyncio.iscoroutinefunction(fn):
            raise TypeError(f"Tool '{tool_name}' must be an async function")

        tool = RegisteredTool(
            name=tool_name,
            description=description or fn.__doc__ or "",
            fn=fn,
            parameters_schema=_build_parameters_schema(fn),
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            idempotent=idempotent,
        )
        self._tools[tool_name] = tool
        logger.info("Registered tool: %s (timeout=%ss, retries=%d)", tool_name, timeout_seconds, max_retries)
        return tool

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolInfo]:
        """Return metadata for all registered tools (for LLM system prompts)."""
        return [t.to_info() for t in self._tools.values()]

    def list_tool_schemas(self) -> list[dict[str, Any]]:
        """Return JSON-serializable tool descriptions for the LLM."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters_schema,
            }
            for t in self._tools.values()
        ]

    def has(self, name: str) -> bool:
        return name in self._tools

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())


# ──────────────────────────────────────────────────────────────────────
# @agent_tool decorator
# ──────────────────────────────────────────────────────────────────────

# Module-level default registry so decorators work at import time
_default_registry = ToolRegistry()


def get_default_registry() -> ToolRegistry:
    """Access the module-level default ToolRegistry."""
    return _default_registry


def agent_tool(
    *,
    name: str | None = None,
    description: str = "",
    timeout_seconds: float = 30.0,
    max_retries: int = 2,
    idempotent: bool = False,
    registry: ToolRegistry | None = None,
) -> Callable[[AsyncToolFn], AsyncToolFn]:
    """
    Decorator to register an async function as an agent tool.

    Usage:
        @agent_tool(name="add", description="Add two numbers", timeout_seconds=5)
        async def add(a: float, b: float) -> float:
            return a + b
    """

    def decorator(fn: AsyncToolFn) -> AsyncToolFn:
        target = registry or _default_registry
        target.register(
            fn,
            name=name,
            description=description,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            idempotent=idempotent,
        )
        return fn

    return decorator


# ──────────────────────────────────────────────────────────────────────
# Tool execution with timeout, retries, backoff, idempotency
# ──────────────────────────────────────────────────────────────────────


async def execute_tool(
    registry: ToolRegistry,
    tool_call: ToolCall,
    executed_keys: set[str],
    *,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> ToolReceipt:
    """
    Execute a tool call with production safeguards:

      1. Idempotency check — skip if this key was already executed
      2. Registry lookup — fail fast if tool doesn't exist
      3. Retry loop with:
         a. asyncio.wait_for timeout
         b. Exponential backoff with ±25% jitter
      4. Returns an immutable ToolReceipt capturing the outcome
    """
    now = datetime.now(timezone.utc)

    # ── 1. Idempotency guard ──
    if tool_call.idempotency_key in executed_keys:
        logger.info(
            "Skipping duplicate tool call: %s (key=%s)",
            tool_call.tool_name,
            tool_call.idempotency_key,
        )
        return ToolReceipt(
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
            idempotency_key=tool_call.idempotency_key,
            status="skipped_duplicate",
            result=None,
            error="Duplicate idempotency key — already executed",
            started_at=now,
            finished_at=now,
            duration_ms=0.0,
            attempt=0,
            total_attempts=0,
        )

    # ── 2. Registry lookup ──
    registered = registry.get(tool_call.tool_name)
    if registered is None:
        raise ToolNotFoundError(
            f"Tool '{tool_call.tool_name}' not found in registry",
            details={"tool_name": tool_call.tool_name, "available": registry.tool_names},
        )

    # ── 3. Retry loop ──
    max_attempts = registered.max_retries + 1  # retries + the initial attempt
    last_error: str | None = None
    last_status: str = "error"

    for attempt in range(1, max_attempts + 1):
        started_at = datetime.now(timezone.utc)
        try:
            result = await asyncio.wait_for(
                registered.fn(**tool_call.arguments),
                timeout=registered.timeout_seconds,
            )
            finished_at = datetime.now(timezone.utc)
            duration_ms = (finished_at - started_at).total_seconds() * 1000

            # ── Success ──
            executed_keys.add(tool_call.idempotency_key)
            logger.info(
                "Tool %s succeeded (attempt %d/%d, %.1fms)",
                tool_call.tool_name,
                attempt,
                max_attempts,
                duration_ms,
            )
            return ToolReceipt(
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                idempotency_key=tool_call.idempotency_key,
                status="success",
                result=result,
                error=None,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                attempt=attempt,
                total_attempts=attempt,
            )

        except asyncio.TimeoutError:
            finished_at = datetime.now(timezone.utc)
            duration_ms = (finished_at - started_at).total_seconds() * 1000
            last_error = f"Timeout after {registered.timeout_seconds}s"
            last_status = "timeout"
            logger.warning(
                "Tool %s timed out (attempt %d/%d, %.1fms)",
                tool_call.tool_name,
                attempt,
                max_attempts,
                duration_ms,
            )

        except Exception as exc:
            finished_at = datetime.now(timezone.utc)
            duration_ms = (finished_at - started_at).total_seconds() * 1000
            last_error = f"{type(exc).__name__}: {exc}"
            last_status = "error"
            logger.warning(
                "Tool %s failed (attempt %d/%d): %s",
                tool_call.tool_name,
                attempt,
                max_attempts,
                last_error,
            )

        # ── Backoff before retry (skip on last attempt) ──
        if attempt < max_attempts:
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            jitter = delay * random.uniform(-0.25, 0.25)
            sleep_time = max(0.0, delay + jitter)
            logger.debug("Backing off %.2fs before retry %d", sleep_time, attempt + 1)
            await asyncio.sleep(sleep_time)

    # ── 4. All retries exhausted ──
    executed_keys.add(tool_call.idempotency_key)
    finished_at = datetime.now(timezone.utc)
    return ToolReceipt(
        tool_name=tool_call.tool_name,
        arguments=tool_call.arguments,
        idempotency_key=tool_call.idempotency_key,
        status=last_status,  # type: ignore[arg-type]
        result=None,
        error=last_error,
        started_at=started_at,  # type: ignore[possibly-undefined]
        finished_at=finished_at,
        duration_ms=(finished_at - started_at).total_seconds() * 1000,  # type: ignore[possibly-undefined]
        attempt=max_attempts,
        total_attempts=max_attempts,
    )
