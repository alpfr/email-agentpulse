"""
skeleton.runner — The 8-step agent orchestration loop.

This is the heart of the skeleton.  AgentRunner.run() implements:

  1. Validate input
  2. Load state
  3. Plan next step (bounded)
  4. Call tool (timeout + retries + idempotency)
  5. Store receipt in state
  6. Evaluate outcome
  7. Stop or continue
  8. Respond with truth (and receipts)

Every step is clearly delineated, every error path is handled,
and the full audit trail is preserved in ToolReceipts.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from .errors import (
    AgentError,
    MaxStepsExceededError,
    PlannerError,
    ToolNotFoundError,
    ValidationError,
)
from .evaluator import Evaluator
from .models import (
    AgentInput,
    AgentResponse,
    AgentState,
    ToolInfo,
    ToolReceipt,
)
from .planner import Planner
from .state import StateBackend
from .tools import ToolRegistry, execute_tool

logger = logging.getLogger(__name__)


def _format_receipt_as_message(receipt: ToolReceipt) -> dict[str, str]:
    """
    Convert a ToolReceipt into a conversation message so the LLM
    planner can see what happened.
    """
    if receipt.status == "success":
        content = (
            f"Tool '{receipt.tool_name}' succeeded.\n"
            f"Arguments: {json.dumps(receipt.arguments)}\n"
            f"Result: {json.dumps(receipt.result, default=str)[:1000]}"
        )
    elif receipt.status == "skipped_duplicate":
        content = (
            f"Tool '{receipt.tool_name}' skipped (duplicate idempotency key)."
        )
    else:
        content = (
            f"Tool '{receipt.tool_name}' failed with status='{receipt.status}'.\n"
            f"Arguments: {json.dumps(receipt.arguments)}\n"
            f"Error: {receipt.error}"
        )
    return {"role": "user", "content": f"[Tool Result]\n{content}"}


class AgentRunner:
    """
    Orchestrates the 8-step production agent loop.

    Usage:
        runner = AgentRunner(
            registry=my_tool_registry,
            state_backend=InMemoryStateBackend(),
            planner=LLMPlanner(),
            evaluator=SimpleEvaluator(),
        )
        response = await runner.run(AgentInput(goal="What is 2+2?"))
    """

    def __init__(
        self,
        *,
        registry: ToolRegistry,
        state_backend: StateBackend,
        planner: Planner,
        evaluator: Evaluator,
        max_consecutive_planner_failures: int = 3,
    ) -> None:
        self._registry = registry
        self._state_backend = state_backend
        self._planner = planner
        self._evaluator = evaluator
        self._max_planner_failures = max_consecutive_planner_failures

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    async def run(self, input: AgentInput) -> AgentResponse:
        """
        Execute the 8-step agent loop.

        Returns an AgentResponse with the final answer, status, and
        the full list of ToolReceipts for audit / debugging.
        """
        # ════════════════════════════════════════════════════════════
        # STEP 1: VALIDATE INPUT
        # ════════════════════════════════════════════════════════════
        # Pydantic already validates types/constraints on AgentInput
        # construction.  Here we do semantic validation.
        logger.info("Step 1: Validating input — goal=%r, max_steps=%d", input.goal[:80], input.max_steps)
        self._validate_input(input)

        # ════════════════════════════════════════════════════════════
        # STEP 2: LOAD STATE
        # ════════════════════════════════════════════════════════════
        logger.info("Step 2: Loading state (session_id=%s)", input.session_id or "new")
        state = await self._load_or_create_state(input)
        executed_keys: set[str] = {r.idempotency_key for r in state.receipts}

        # Track planner health
        consecutive_planner_failures = 0
        final_answer = "Agent finished without producing an answer."

        # ════════════════════════════════════════════════════════════
        # STEPS 3–7: MAIN LOOP
        # ════════════════════════════════════════════════════════════
        while state.step_count < input.max_steps:
            state.step_count += 1
            step = state.step_count
            logger.info("─── Step %d / %d ───", step, input.max_steps)

            # ────────────────────────────────────────────────────────
            # STEP 3: PLAN NEXT STEP (bounded)
            # ────────────────────────────────────────────────────────
            logger.info("Step 3: Planning next action...")
            available_tools = self._filter_tools(input.allowed_tools)

            try:
                decision = await self._planner.plan_next_step(state, available_tools)
                consecutive_planner_failures = 0
                logger.info(
                    "Planner decided: action=%s, reasoning=%s",
                    decision.action,
                    decision.reasoning[:100],
                )
            except PlannerError as exc:
                consecutive_planner_failures += 1
                logger.warning(
                    "Planner failed (attempt %d/%d): %s",
                    consecutive_planner_failures,
                    self._max_planner_failures,
                    exc.message,
                )

                # Record the planner failure as a pseudo-receipt for visibility
                now = datetime.now(timezone.utc)
                error_receipt = ToolReceipt(
                    tool_name="__planner__",
                    arguments={},
                    idempotency_key=f"planner-error-{step}",
                    status="error",
                    result=None,
                    error=exc.message,
                    started_at=now,
                    finished_at=now,
                    duration_ms=0.0,
                    attempt=consecutive_planner_failures,
                    total_attempts=self._max_planner_failures,
                )
                state.receipts.append(error_receipt)
                state.messages.append(_format_receipt_as_message(error_receipt))
                await self._state_backend.save(state)

                if consecutive_planner_failures >= self._max_planner_failures:
                    state.status = "failed"
                    final_answer = (
                        f"Agent stopped: planner failed {self._max_planner_failures} "
                        f"consecutive times. Last error: {exc.message}"
                    )
                    logger.error("Planner exceeded max consecutive failures. Stopping.")
                    break
                continue

            # ── Planner says "finish" ──
            if decision.action == "finish":
                state.status = "completed"
                final_answer = decision.final_answer or "Goal completed."
                logger.info("Planner decided to finish: %s", final_answer[:200])

                # Add the finish decision as a message so it's visible in state
                state.messages.append({
                    "role": "assistant",
                    "content": f"[Agent Finished]\n{final_answer}",
                })
                await self._state_backend.save(state)
                break

            # ────────────────────────────────────────────────────────
            # STEP 4: CALL TOOL
            # ────────────────────────────────────────────────────────
            tool_call = decision.tool_call
            if tool_call is None:
                # Defensive: planner said call_tool but provided no tool_call
                logger.warning("Planner returned call_tool with no tool_call. Treating as finish.")
                state.status = "completed"
                final_answer = decision.reasoning or "Goal completed (no tool needed)."
                break

            logger.info(
                "Step 4: Calling tool '%s' with args=%s (key=%s)",
                tool_call.tool_name,
                json.dumps(tool_call.arguments)[:200],
                tool_call.idempotency_key[:12],
            )

            try:
                receipt = await execute_tool(self._registry, tool_call, executed_keys)
            except ToolNotFoundError as exc:
                # Tool doesn't exist — record error and let the planner try again
                now = datetime.now(timezone.utc)
                receipt = ToolReceipt(
                    tool_name=tool_call.tool_name,
                    arguments=tool_call.arguments,
                    idempotency_key=tool_call.idempotency_key,
                    status="error",
                    result=None,
                    error=exc.message,
                    started_at=now,
                    finished_at=now,
                    duration_ms=0.0,
                    attempt=1,
                    total_attempts=1,
                )

            logger.info(
                "Tool '%s' completed: status=%s, duration=%.1fms",
                receipt.tool_name,
                receipt.status,
                receipt.duration_ms,
            )

            # ────────────────────────────────────────────────────────
            # STEP 5: STORE RECEIPT IN STATE
            # ────────────────────────────────────────────────────────
            logger.info("Step 5: Storing receipt in state...")
            state.receipts.append(receipt)
            state.messages.append(_format_receipt_as_message(receipt))
            state.updated_at = datetime.now(timezone.utc)
            await self._state_backend.save(state)

            # ────────────────────────────────────────────────────────
            # STEP 6: EVALUATE OUTCOME
            # ────────────────────────────────────────────────────────
            logger.info("Step 6: Evaluating outcome...")
            try:
                evaluation = await self._evaluator.evaluate(state)
                logger.info(
                    "Evaluation: goal_achieved=%s, confidence=%.2f, should_continue=%s",
                    evaluation.goal_achieved,
                    evaluation.confidence,
                    evaluation.should_continue,
                )
            except Exception as exc:
                # Evaluator failure should not crash the agent — default to continue
                logger.warning("Evaluator raised an exception, defaulting to continue: %s", exc)
                from .models import EvaluationResult

                evaluation = EvaluationResult(
                    goal_achieved=False,
                    confidence=0.0,
                    reasoning=f"Evaluator error: {exc}",
                    should_continue=True,
                )

            if evaluation.goal_achieved:
                state.status = "completed"
                final_answer = evaluation.reasoning or "Goal achieved."
                logger.info("Goal achieved! Stopping.")
                break

            if not evaluation.should_continue:
                state.status = "failed"
                final_answer = f"Agent stopped: {evaluation.reasoning}"
                logger.info("Evaluator says stop. Reason: %s", evaluation.reasoning)
                break

            # ────────────────────────────────────────────────────────
            # STEP 7: CONTINUE (loop back to step 3)
            # ────────────────────────────────────────────────────────
            logger.info("Step 7: Continuing to next iteration...")

        else:
            # ── while/else: max_steps exceeded ──
            state.status = "max_steps_exceeded"
            final_answer = (
                f"Maximum steps ({input.max_steps}) exceeded. "
                f"Completed {len([r for r in state.receipts if r.status == 'success'])} "
                f"successful tool calls out of {len(state.receipts)} total."
            )
            logger.warning("Max steps exceeded (%d). Stopping.", input.max_steps)

        # ════════════════════════════════════════════════════════════
        # STEP 8: RESPOND WITH TRUTH (and receipts)
        # ════════════════════════════════════════════════════════════
        logger.info("Step 8: Building final response (status=%s)", state.status)
        await self._state_backend.save(state)

        return AgentResponse(
            session_id=state.session_id,
            answer=final_answer,
            goal_achieved=state.status == "completed",
            receipts=state.receipts,
            steps_taken=state.step_count,
            status=state.status,
        )

    # ──────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────

    def _validate_input(self, input: AgentInput) -> None:
        """
        Semantic validation beyond what Pydantic enforces.
        Raises ValidationError if something is wrong.
        """
        # Check allowed_tools actually exist
        if input.allowed_tools is not None:
            unknown = [t for t in input.allowed_tools if not self._registry.has(t)]
            if unknown:
                raise ValidationError(
                    f"Unknown tools in allowed_tools: {unknown}",
                    details={
                        "unknown_tools": unknown,
                        "available_tools": self._registry.tool_names,
                    },
                )

    async def _load_or_create_state(self, input: AgentInput) -> AgentState:
        """Load existing state or create a fresh one."""
        if input.session_id:
            existing = await self._state_backend.load(input.session_id)
            if existing is not None:
                logger.info(
                    "Resuming session %s at step %d",
                    existing.session_id,
                    existing.step_count,
                )
                existing.status = "running"
                return existing
            logger.info(
                "Session %s not found, creating new state",
                input.session_id,
            )

        state = AgentState(
            goal=input.goal,
            context=input.context,
            messages=[],
        )
        logger.info("Created new session %s", state.session_id)
        await self._state_backend.save(state)
        return state

    def _filter_tools(self, allowed_tools: list[str] | None) -> list[ToolInfo]:
        """Return tool info, filtered by the allowed_tools whitelist."""
        all_tools = self._registry.list_tools()
        if allowed_tools is None:
            return all_tools
        return [t for t in all_tools if t.name in allowed_tools]
