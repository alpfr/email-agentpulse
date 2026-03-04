"""Tests for skeleton.runner — AgentRunner 8-step loop with mock planner."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

from skeleton.errors import ValidationError
from skeleton.evaluator import SimpleEvaluator
from skeleton.models import (
    AgentInput,
    AgentState,
    EvaluationResult,
    PlannerDecision,
    ToolCall,
    ToolInfo,
)
from skeleton.runner import AgentRunner
from skeleton.state import InMemoryStateBackend
from skeleton.tools import ToolRegistry


# ──────────────────────────────────────────────────────────────────────
# Mock Planner — returns scripted decisions
# ──────────────────────────────────────────────────────────────────────


class MockPlanner:
    """Planner that returns decisions from a pre-set list."""

    def __init__(self, decisions: list[PlannerDecision]) -> None:
        self._decisions = list(decisions)
        self._call_count = 0

    async def plan_next_step(
        self,
        state: AgentState,
        available_tools: list[ToolInfo],
    ) -> PlannerDecision:
        if self._call_count >= len(self._decisions):
            return PlannerDecision(action="finish", final_answer="Ran out of decisions", reasoning="done")
        decision = self._decisions[self._call_count]
        self._call_count += 1
        return decision


class FailingPlanner:
    """Planner that always raises an error."""

    async def plan_next_step(self, state, available_tools):
        from skeleton.errors import PlannerError
        raise PlannerError("Planner is broken")


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────


class TestAgentRunner:
    @pytest.mark.asyncio
    async def test_immediate_finish(self, registry, state_backend, evaluator):
        """Planner immediately says finish → 1 step, completed."""
        planner = MockPlanner([
            PlannerDecision(action="finish", final_answer="The answer is 42", reasoning="I just know"),
        ])
        runner = AgentRunner(
            registry=registry,
            state_backend=state_backend,
            planner=planner,
            evaluator=evaluator,
        )
        response = await runner.run(AgentInput(goal="What is the answer?"))

        assert response.goal_achieved
        assert response.status == "completed"
        assert response.answer == "The answer is 42"
        assert response.steps_taken == 1
        assert len(response.receipts) == 0  # No tools called

    @pytest.mark.asyncio
    async def test_single_tool_call_then_finish(self, registry, state_backend, evaluator):
        """Planner calls add(2,3), then finishes."""
        planner = MockPlanner([
            PlannerDecision(
                action="call_tool",
                tool_call=ToolCall(tool_name="add", arguments={"a": 2, "b": 3}),
                reasoning="Need to add",
            ),
            PlannerDecision(action="finish", final_answer="2 + 3 = 5", reasoning="Got the result"),
        ])
        runner = AgentRunner(
            registry=registry,
            state_backend=state_backend,
            planner=planner,
            evaluator=evaluator,
        )
        response = await runner.run(AgentInput(goal="What is 2+3?"))

        assert response.goal_achieved
        assert response.answer == "2 + 3 = 5"
        assert response.steps_taken == 2
        assert len(response.receipts) == 1
        assert response.receipts[0].status == "success"
        assert response.receipts[0].result == 5.0

    @pytest.mark.asyncio
    async def test_multi_step_chain(self, registry, state_backend, evaluator):
        """Planner calls add(5,3)=8, then multiply(8,2)=16, then finishes."""
        planner = MockPlanner([
            PlannerDecision(
                action="call_tool",
                tool_call=ToolCall(tool_name="add", arguments={"a": 5, "b": 3}),
                reasoning="Step 1: add",
            ),
            PlannerDecision(
                action="call_tool",
                tool_call=ToolCall(tool_name="multiply", arguments={"a": 8, "b": 2}),
                reasoning="Step 2: multiply",
            ),
            PlannerDecision(action="finish", final_answer="Result is 16", reasoning="done"),
        ])
        runner = AgentRunner(
            registry=registry,
            state_backend=state_backend,
            planner=planner,
            evaluator=evaluator,
        )
        response = await runner.run(AgentInput(goal="5+3 then multiply by 2"))

        assert response.goal_achieved
        assert response.steps_taken == 3
        assert len(response.receipts) == 2
        assert response.receipts[0].result == 8.0
        assert response.receipts[1].result == 16.0

    @pytest.mark.asyncio
    async def test_max_steps_exceeded(self, registry, state_backend, evaluator):
        """Planner never finishes → hits max_steps."""
        # Create decisions that keep calling tools forever
        planner = MockPlanner([
            PlannerDecision(
                action="call_tool",
                tool_call=ToolCall(tool_name="add", arguments={"a": 1, "b": 1}, idempotency_key=f"step-{i}"),
                reasoning="keep going",
            )
            for i in range(10)
        ])
        runner = AgentRunner(
            registry=registry,
            state_backend=state_backend,
            planner=planner,
            evaluator=evaluator,
        )
        response = await runner.run(AgentInput(goal="Count forever", max_steps=3))

        assert not response.goal_achieved
        assert response.status == "max_steps_exceeded"
        assert response.steps_taken == 3

    @pytest.mark.asyncio
    async def test_planner_failure_recovery(self, registry, state_backend, evaluator):
        """Planner fails 3 times → agent stops with 'failed' status."""
        planner = FailingPlanner()
        runner = AgentRunner(
            registry=registry,
            state_backend=state_backend,
            planner=planner,
            evaluator=evaluator,
            max_consecutive_planner_failures=3,
        )
        response = await runner.run(AgentInput(goal="Test", max_steps=10))

        assert not response.goal_achieved
        assert response.status == "failed"
        assert "planner failed 3 consecutive times" in response.answer
        # Planner errors are recorded as pseudo-receipts
        assert len(response.receipts) == 3
        assert all(r.tool_name == "__planner__" for r in response.receipts)

    @pytest.mark.asyncio
    async def test_tool_error_recorded(self, registry, state_backend, evaluator):
        """Calling a tool that fails → error receipt recorded, agent continues."""
        planner = MockPlanner([
            PlannerDecision(
                action="call_tool",
                tool_call=ToolCall(tool_name="fail_always", arguments={}),
                reasoning="Try it",
            ),
            PlannerDecision(action="finish", final_answer="Tool failed, giving up", reasoning="error"),
        ])
        runner = AgentRunner(
            registry=registry,
            state_backend=state_backend,
            planner=planner,
            evaluator=evaluator,
        )
        response = await runner.run(AgentInput(goal="Test failure"))

        assert response.goal_achieved  # Planner said finish
        assert len(response.receipts) == 1
        assert response.receipts[0].status == "error"
        assert "RuntimeError" in response.receipts[0].error

    @pytest.mark.asyncio
    async def test_unknown_tool_handled(self, registry, state_backend, evaluator):
        """Planner requests a tool that doesn't exist → error receipt, continues."""
        planner = MockPlanner([
            PlannerDecision(
                action="call_tool",
                tool_call=ToolCall(tool_name="nonexistent_tool", arguments={}),
                reasoning="Try it",
            ),
            PlannerDecision(action="finish", final_answer="Tool not found", reasoning="fallback"),
        ])
        runner = AgentRunner(
            registry=registry,
            state_backend=state_backend,
            planner=planner,
            evaluator=evaluator,
        )
        response = await runner.run(AgentInput(goal="Test unknown tool"))

        assert response.goal_achieved
        assert len(response.receipts) == 1
        assert response.receipts[0].status == "error"
        assert "not found" in response.receipts[0].error

    @pytest.mark.asyncio
    async def test_validation_unknown_allowed_tools(self, registry, state_backend, evaluator):
        """Specifying unknown tools in allowed_tools → ValidationError."""
        planner = MockPlanner([])
        runner = AgentRunner(
            registry=registry,
            state_backend=state_backend,
            planner=planner,
            evaluator=evaluator,
        )
        with pytest.raises(ValidationError, match="Unknown tools"):
            await runner.run(AgentInput(goal="Test", allowed_tools=["nonexistent"]))

    @pytest.mark.asyncio
    async def test_session_resume(self, registry, state_backend, evaluator):
        """Run with a session_id, then resume it."""
        planner = MockPlanner([
            PlannerDecision(
                action="call_tool",
                tool_call=ToolCall(tool_name="add", arguments={"a": 1, "b": 1}),
                reasoning="first call",
            ),
            PlannerDecision(action="finish", final_answer="Done first run", reasoning="ok"),
        ])
        runner = AgentRunner(
            registry=registry,
            state_backend=state_backend,
            planner=planner,
            evaluator=evaluator,
        )
        response1 = await runner.run(AgentInput(goal="Test"))
        session_id = response1.session_id
        assert response1.steps_taken == 2

        # Resume with same session_id
        planner2 = MockPlanner([
            PlannerDecision(action="finish", final_answer="Resumed and done", reasoning="resumed"),
        ])
        runner2 = AgentRunner(
            registry=registry,
            state_backend=state_backend,
            planner=planner2,
            evaluator=evaluator,
        )
        response2 = await runner2.run(AgentInput(goal="Continue", session_id=session_id))
        assert response2.session_id == session_id
        assert response2.steps_taken == 3  # Continued from step 2

    @pytest.mark.asyncio
    async def test_state_saved_after_each_tool_call(self, registry, evaluator):
        """Verify state is persisted after every tool call."""
        backend = InMemoryStateBackend()
        planner = MockPlanner([
            PlannerDecision(
                action="call_tool",
                tool_call=ToolCall(tool_name="add", arguments={"a": 1, "b": 2}),
                reasoning="call",
            ),
            PlannerDecision(action="finish", final_answer="done", reasoning="ok"),
        ])
        runner = AgentRunner(
            registry=registry,
            state_backend=backend,
            planner=planner,
            evaluator=evaluator,
        )
        response = await runner.run(AgentInput(goal="Test state"))

        # State should be in the backend
        state = await backend.load(response.session_id)
        assert state is not None
        assert state.status == "completed"
        assert len(state.receipts) == 1
