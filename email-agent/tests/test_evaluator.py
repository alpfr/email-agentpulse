"""Tests for skeleton.evaluator — SimpleEvaluator."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from skeleton.evaluator import SimpleEvaluator
from skeleton.models import AgentState, ToolReceipt


def _make_receipt(status: str = "success", tool_name: str = "add") -> ToolReceipt:
    now = datetime.now(timezone.utc)
    return ToolReceipt(
        tool_name=tool_name,
        arguments={},
        idempotency_key=f"key-{id(object())}",
        status=status,
        result="ok" if status == "success" else None,
        error="fail" if status != "success" else None,
        started_at=now,
        finished_at=now,
        duration_ms=1.0,
        attempt=1,
        total_attempts=1,
    )


class TestSimpleEvaluator:
    @pytest.mark.asyncio
    async def test_no_receipts_continues(self):
        evaluator = SimpleEvaluator()
        state = AgentState(goal="Test")
        result = await evaluator.evaluate(state)

        assert not result.goal_achieved
        assert result.should_continue

    @pytest.mark.asyncio
    async def test_success_continues(self):
        evaluator = SimpleEvaluator()
        state = AgentState(goal="Test")
        state.receipts.append(_make_receipt("success"))
        result = await evaluator.evaluate(state)

        assert not result.goal_achieved  # Delegates to planner
        assert result.should_continue

    @pytest.mark.asyncio
    async def test_single_failure_continues(self):
        evaluator = SimpleEvaluator(max_consecutive_failures=3)
        state = AgentState(goal="Test")
        state.receipts.append(_make_receipt("error"))
        result = await evaluator.evaluate(state)

        assert result.should_continue  # Only 1 failure, needs 3

    @pytest.mark.asyncio
    async def test_consecutive_failures_stops(self):
        evaluator = SimpleEvaluator(max_consecutive_failures=3)
        state = AgentState(goal="Test")
        state.receipts.extend([
            _make_receipt("error"),
            _make_receipt("timeout"),
            _make_receipt("error"),
        ])
        result = await evaluator.evaluate(state)

        assert not result.goal_achieved
        assert not result.should_continue

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        evaluator = SimpleEvaluator(max_consecutive_failures=3)
        state = AgentState(goal="Test")
        state.receipts.extend([
            _make_receipt("error"),
            _make_receipt("error"),
            _make_receipt("success"),  # Resets count
            _make_receipt("error"),
        ])
        result = await evaluator.evaluate(state)

        assert result.should_continue  # Only 1 consecutive failure after the success
