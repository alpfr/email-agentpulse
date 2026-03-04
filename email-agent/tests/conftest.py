"""Shared fixtures for skeleton tests."""

from __future__ import annotations

import pytest

from skeleton import (
    AgentInput,
    InMemoryStateBackend,
    SimpleEvaluator,
    ToolRegistry,
    agent_tool,
)


# ──────────────────────────────────────────────────────────────────────
# Tool fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def registry() -> ToolRegistry:
    """A fresh ToolRegistry with calculator + mock tools."""
    reg = ToolRegistry()

    async def _add(a: float, b: float) -> float:
        return a + b

    async def _multiply(a: float, b: float) -> float:
        return a * b

    async def _fail_always() -> str:
        raise RuntimeError("Tool always fails")

    async def _slow_tool() -> str:
        import asyncio
        await asyncio.sleep(10)
        return "done"

    reg.register(_add, name="add", description="Add two numbers", timeout_seconds=5, max_retries=0, idempotent=True)
    reg.register(_multiply, name="multiply", description="Multiply two numbers", timeout_seconds=5, max_retries=0, idempotent=True)
    reg.register(_fail_always, name="fail_always", description="Always fails", timeout_seconds=5, max_retries=1, idempotent=False)
    reg.register(_slow_tool, name="slow_tool", description="Very slow tool", timeout_seconds=0.1, max_retries=0, idempotent=True)

    return reg


@pytest.fixture
def state_backend() -> InMemoryStateBackend:
    return InMemoryStateBackend()


@pytest.fixture
def evaluator() -> SimpleEvaluator:
    return SimpleEvaluator(max_consecutive_failures=3)


@pytest.fixture
def sample_input() -> AgentInput:
    return AgentInput(goal="What is 2 + 3?", max_steps=5)
