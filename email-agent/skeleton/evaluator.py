"""
skeleton.evaluator — Assesses whether the agent's goal has been achieved.

Two implementations:
  • SimpleEvaluator  — rule-based, zero LLM cost, trusts the planner's "finish"
  • LLMEvaluator     — asks an LLM to judge goal completion with a confidence score
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Protocol, runtime_checkable

from .errors import AgentError
from .models import AgentState, EvaluationResult

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Protocol (interface)
# ──────────────────────────────────────────────────────────────────────


@runtime_checkable
class Evaluator(Protocol):
    """Assess the current state to determine if the goal is achieved."""

    async def evaluate(self, state: AgentState) -> EvaluationResult: ...


# ──────────────────────────────────────────────────────────────────────
# Simple rule-based Evaluator (no LLM cost)
# ──────────────────────────────────────────────────────────────────────


class SimpleEvaluator:
    """
    Trusts the planner's decision cycle.  Does not call an LLM.

    Logic:
      • If the last receipt was successful → should_continue = True
        (let the planner decide when to stop)
      • If the last 3 consecutive receipts all failed → should_continue = False
        (the agent is stuck)
      • Otherwise → should_continue = True
    """

    def __init__(self, *, max_consecutive_failures: int = 3) -> None:
        self._max_failures = max_consecutive_failures

    async def evaluate(self, state: AgentState) -> EvaluationResult:
        if not state.receipts:
            return EvaluationResult(
                goal_achieved=False,
                confidence=0.0,
                reasoning="No tool calls executed yet.",
                should_continue=True,
            )

        # Count consecutive trailing failures
        consecutive_failures = 0
        for receipt in reversed(state.receipts):
            if receipt.status in ("error", "timeout"):
                consecutive_failures += 1
            else:
                break

        if consecutive_failures >= self._max_failures:
            return EvaluationResult(
                goal_achieved=False,
                confidence=0.0,
                reasoning=f"Last {consecutive_failures} tool calls failed consecutively. Stopping.",
                should_continue=False,
            )

        last = state.receipts[-1]
        return EvaluationResult(
            goal_achieved=False,  # Delegate goal detection to the planner
            confidence=0.0,
            reasoning=f"Last tool '{last.tool_name}' returned status='{last.status}'. Continuing.",
            should_continue=True,
        )


# ──────────────────────────────────────────────────────────────────────
# LLM-based Evaluator (higher accuracy, higher cost)
# ──────────────────────────────────────────────────────────────────────


EVALUATOR_SYSTEM_PROMPT = """\
You are an evaluation module inside an AI agent.  Your job is to assess
whether the agent's goal has been achieved based on the tool results so far.

Respond ONLY with valid JSON (no markdown fences):
{{
  "goal_achieved": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "...",
  "should_continue": true/false
}}

Rules:
- Set goal_achieved=true ONLY if the tool results clearly satisfy the goal.
- Set should_continue=false if the agent is stuck, looping, or cannot
  make progress (even if the goal is not achieved).
- Keep reasoning concise (1-2 sentences).
"""


class LLMEvaluator:
    """
    Uses an LLM to evaluate whether the agent's goal is complete.

    More accurate than SimpleEvaluator but costs one LLM call per step.
    Consider using SimpleEvaluator for simple/deterministic tools and
    LLMEvaluator for complex, ambiguous goals.
    """

    def __init__(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        self._provider = provider or os.getenv("LLM_PROVIDER", "anthropic")
        self._model = model or os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
        self._temperature = temperature
        self._llm = self._build_llm()

    def _build_llm(self) -> Any:
        if self._provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model=self._model, temperature=self._temperature)
        else:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=self._model,
                temperature=self._temperature,
                max_tokens=512,
            )

    async def evaluate(self, state: AgentState) -> EvaluationResult:
        """Ask the LLM to evaluate goal completion."""
        from langchain_core.messages import HumanMessage, SystemMessage

        # Build a summary of receipts for the evaluator
        receipts_summary = []
        for r in state.receipts:
            entry = {
                "tool": r.tool_name,
                "status": r.status,
                "result": str(r.result)[:300] if r.result else None,
                "error": r.error,
            }
            receipts_summary.append(entry)

        user_content = (
            f"Goal: {state.goal}\n\n"
            f"Tool results so far ({len(state.receipts)} calls):\n"
            f"{json.dumps(receipts_summary, indent=2)}"
        )

        messages = [
            SystemMessage(content=EVALUATOR_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        try:
            response = await self._llm.ainvoke(messages)
            raw = response.content if hasattr(response, "content") else str(response)

            # Strip markdown fences
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines).strip()

            data = json.loads(cleaned)
            return EvaluationResult(
                goal_achieved=bool(data.get("goal_achieved", False)),
                confidence=float(data.get("confidence", 0.0)),
                reasoning=data.get("reasoning", ""),
                should_continue=bool(data.get("should_continue", True)),
            )

        except Exception as exc:
            logger.warning("LLM evaluator failed, defaulting to continue: %s", exc)
            # Fail open — let the agent continue rather than crashing
            return EvaluationResult(
                goal_achieved=False,
                confidence=0.0,
                reasoning=f"Evaluator error: {exc}. Defaulting to continue.",
                should_continue=True,
            )
