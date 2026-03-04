"""Tests for skeleton.models — Pydantic model validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from skeleton.models import (
    AgentInput,
    AgentResponse,
    AgentState,
    EvaluationResult,
    PlannerDecision,
    ToolCall,
    ToolInfo,
    ToolReceipt,
)


class TestAgentInput:
    def test_valid_input(self):
        inp = AgentInput(goal="Test goal")
        assert inp.goal == "Test goal"
        assert inp.max_steps == 10  # default
        assert inp.session_id is None
        assert inp.allowed_tools is None

    def test_custom_max_steps(self):
        inp = AgentInput(goal="Test", max_steps=25)
        assert inp.max_steps == 25

    def test_max_steps_too_high(self):
        with pytest.raises(ValidationError):
            AgentInput(goal="Test", max_steps=100)

    def test_max_steps_too_low(self):
        with pytest.raises(ValidationError):
            AgentInput(goal="Test", max_steps=0)

    def test_empty_goal_rejected(self):
        with pytest.raises(ValidationError):
            AgentInput(goal="")

    def test_allowed_tools(self):
        inp = AgentInput(goal="Test", allowed_tools=["add", "multiply"])
        assert inp.allowed_tools == ["add", "multiply"]

    def test_context_default_empty(self):
        inp = AgentInput(goal="Test")
        assert inp.context == {}


class TestAgentState:
    def test_default_state(self):
        state = AgentState(goal="Test goal")
        assert state.goal == "Test goal"
        assert state.step_count == 0
        assert state.status == "running"
        assert state.receipts == []
        assert state.messages == []
        assert len(state.session_id) > 0

    def test_session_id_auto_generated(self):
        s1 = AgentState(goal="A")
        s2 = AgentState(goal="B")
        assert s1.session_id != s2.session_id


class TestToolCall:
    def test_auto_idempotency_key(self):
        tc = ToolCall(tool_name="add", arguments={"a": 1, "b": 2})
        assert len(tc.idempotency_key) > 0

    def test_unique_keys(self):
        tc1 = ToolCall(tool_name="add", arguments={})
        tc2 = ToolCall(tool_name="add", arguments={})
        assert tc1.idempotency_key != tc2.idempotency_key


class TestPlannerDecision:
    def test_finish_decision(self):
        d = PlannerDecision(action="finish", final_answer="42", reasoning="Done")
        assert d.action == "finish"
        assert d.tool_call is None

    def test_call_tool_decision(self):
        tc = ToolCall(tool_name="add", arguments={"a": 1, "b": 2})
        d = PlannerDecision(action="call_tool", tool_call=tc, reasoning="Need to add")
        assert d.action == "call_tool"
        assert d.tool_call is not None


class TestEvaluationResult:
    def test_confidence_bounds(self):
        r = EvaluationResult(goal_achieved=True, confidence=0.95, reasoning="ok")
        assert r.confidence == 0.95

    def test_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            EvaluationResult(goal_achieved=True, confidence=1.5, reasoning="bad")
