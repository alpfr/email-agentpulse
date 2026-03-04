"""
skeleton.telemetry — OpenTelemetry instrumentation for the agent skeleton.

Provides TracedAgentRunner, a drop-in wrapper around AgentRunner that
adds distributed tracing spans for every step of the 8-step loop.

Requirements (optional):
    pip install opentelemetry-api opentelemetry-sdk

Usage:
    from skeleton import TracedAgentRunner, AgentRunner, ...

    runner = AgentRunner(registry=..., state_backend=..., planner=..., evaluator=...)
    traced = TracedAgentRunner(runner)  # wrap it
    response = await traced.run(AgentInput(goal="..."))

    # Spans emitted:
    #   agent.run                      (root span)
    #   ├── agent.step.1.validate      (step 1)
    #   ├── agent.step.2.load_state    (step 2)
    #   ├── agent.step.3.plan          (step 3, per iteration)
    #   ├── agent.step.4.call_tool     (step 4, per iteration)
    #   ├── agent.step.5.store_receipt (step 5, per iteration)
    #   ├── agent.step.6.evaluate      (step 6, per iteration)
    #   └── agent.step.8.respond       (step 8)

If OpenTelemetry is NOT installed, TracedAgentRunner degrades gracefully
to a no-op wrapper — all spans become context managers that do nothing.
This means you can always use TracedAgentRunner without guarding imports.
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Any

from .errors import PlannerError, ToolNotFoundError
from .evaluator import Evaluator
from .models import (
    AgentInput,
    AgentResponse,
    AgentState,
    EvaluationResult,
    ToolInfo,
    ToolReceipt,
)
from .planner import Planner
from .runner import AgentRunner, _format_receipt_as_message
from .state import StateBackend
from .tools import ToolRegistry, execute_tool

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# OpenTelemetry detection — graceful fallback if not installed
# ──────────────────────────────────────────────────────────────────────

try:
    from opentelemetry import trace
    from opentelemetry.trace import StatusCode

    _OTEL_AVAILABLE = True
    _tracer = trace.get_tracer("skeleton.agent", "1.0.0")
except ImportError:
    _OTEL_AVAILABLE = False
    _tracer = None  # type: ignore[assignment]


@contextmanager
def _span(name: str, attributes: dict[str, Any] | None = None):
    """
    Create a tracing span.  Falls back to no-op if OpenTelemetry is not installed.
    """
    if _OTEL_AVAILABLE and _tracer is not None:
        with _tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, _safe_attr(v))
            try:
                yield span
            except Exception as exc:
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                raise
    else:
        yield None


def _safe_attr(value: Any) -> str | int | float | bool:
    """Coerce a value to an OTel-safe attribute type."""
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)[:256]


# ──────────────────────────────────────────────────────────────────────
# TracedAgentRunner — wraps AgentRunner with OTel spans
# ──────────────────────────────────────────────────────────────────────


class TracedAgentRunner:
    """
    Drop-in replacement for AgentRunner that adds OpenTelemetry spans.

    Wraps every step of the 8-step agent loop in a named span with
    structured attributes for observability dashboards (Jaeger, Datadog,
    AWS X-Ray, Grafana Tempo, etc.).

    If OpenTelemetry is not installed, all tracing is silently skipped
    and the runner behaves identically to AgentRunner.
    """

    def __init__(
        self,
        inner: AgentRunner | None = None,
        *,
        # If inner is None, pass these to construct an AgentRunner:
        registry: ToolRegistry | None = None,
        state_backend: StateBackend | None = None,
        planner: Planner | None = None,
        evaluator: Evaluator | None = None,
        max_consecutive_planner_failures: int = 3,
    ) -> None:
        if inner is not None:
            self._runner = inner
            self._registry = inner._registry
            self._state_backend = inner._state_backend
            self._planner = inner._planner
            self._evaluator = inner._evaluator
            self._max_planner_failures = inner._max_planner_failures
        else:
            if not all([registry, state_backend, planner, evaluator]):
                raise ValueError(
                    "TracedAgentRunner requires either `inner` (an existing AgentRunner) "
                    "or all of: registry, state_backend, planner, evaluator"
                )
            self._registry = registry  # type: ignore[assignment]
            self._state_backend = state_backend  # type: ignore[assignment]
            self._planner = planner  # type: ignore[assignment]
            self._evaluator = evaluator  # type: ignore[assignment]
            self._max_planner_failures = max_consecutive_planner_failures
            self._runner = AgentRunner(
                registry=self._registry,
                state_backend=self._state_backend,
                planner=self._planner,
                evaluator=self._evaluator,
                max_consecutive_planner_failures=max_consecutive_planner_failures,
            )

        if _OTEL_AVAILABLE:
            logger.info("TracedAgentRunner: OpenTelemetry tracing ENABLED")
        else:
            logger.info("TracedAgentRunner: OpenTelemetry not installed, tracing disabled (no-op)")

    async def run(self, input: AgentInput) -> AgentResponse:
        """
        Execute the 8-step agent loop with OpenTelemetry spans.

        This reimplements the loop (rather than wrapping runner.run())
        so each step gets its own span with precise timing.
        """
        run_start = time.monotonic()

        with _span("agent.run", {
            "agent.goal": input.goal[:256],
            "agent.max_steps": input.max_steps,
            "agent.session_id": input.session_id or "new",
        }) as root_span:

            # ═══════ STEP 1: VALIDATE ═══════
            with _span("agent.step.1.validate", {"agent.goal_length": len(input.goal)}):
                self._runner._validate_input(input)

            # ═══════ STEP 2: LOAD STATE ═══════
            with _span("agent.step.2.load_state", {"agent.session_id": input.session_id or "new"}) as load_span:
                state = await self._runner._load_or_create_state(input)
                if load_span:
                    load_span.set_attribute("agent.session_id.resolved", state.session_id)
                    load_span.set_attribute("agent.resumed", state.step_count > 0)

            executed_keys: set[str] = {r.idempotency_key for r in state.receipts}
            consecutive_planner_failures = 0
            final_answer = "Agent finished without producing an answer."

            # ═══════ STEPS 3–7: MAIN LOOP ═══════
            while state.step_count < input.max_steps:
                state.step_count += 1
                step = state.step_count

                # ─── STEP 3: PLAN ───
                with _span("agent.step.3.plan", {"agent.step": step}) as plan_span:
                    available_tools = self._runner._filter_tools(input.allowed_tools)

                    try:
                        decision = await self._planner.plan_next_step(state, available_tools)
                        consecutive_planner_failures = 0
                        if plan_span:
                            plan_span.set_attribute("planner.action", decision.action)
                            plan_span.set_attribute("planner.reasoning", decision.reasoning[:256])
                            if decision.tool_call:
                                plan_span.set_attribute("planner.tool_name", decision.tool_call.tool_name)
                    except PlannerError as exc:
                        consecutive_planner_failures += 1
                        if plan_span:
                            plan_span.set_attribute("planner.failed", True)
                            plan_span.set_attribute("planner.consecutive_failures", consecutive_planner_failures)

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
                            break
                        continue

                # Planner says finish
                if decision.action == "finish":
                    state.status = "completed"
                    final_answer = decision.final_answer or "Goal completed."
                    state.messages.append({
                        "role": "assistant",
                        "content": f"[Agent Finished]\n{final_answer}",
                    })
                    await self._state_backend.save(state)
                    break

                # ─── STEP 4: CALL TOOL ───
                tool_call = decision.tool_call
                if tool_call is None:
                    state.status = "completed"
                    final_answer = decision.reasoning or "Goal completed (no tool needed)."
                    break

                with _span("agent.step.4.call_tool", {
                    "agent.step": step,
                    "tool.name": tool_call.tool_name,
                    "tool.idempotency_key": tool_call.idempotency_key[:16],
                    "tool.arguments": json.dumps(tool_call.arguments)[:256],
                }) as tool_span:
                    try:
                        receipt = await execute_tool(self._registry, tool_call, executed_keys)
                    except ToolNotFoundError as exc:
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

                    if tool_span:
                        tool_span.set_attribute("tool.status", receipt.status)
                        tool_span.set_attribute("tool.duration_ms", receipt.duration_ms)
                        tool_span.set_attribute("tool.attempt", receipt.attempt)
                        if receipt.error:
                            tool_span.set_attribute("tool.error", receipt.error[:256])

                # ─── STEP 5: STORE RECEIPT ───
                with _span("agent.step.5.store_receipt", {
                    "agent.step": step,
                    "tool.name": receipt.tool_name,
                    "tool.status": receipt.status,
                }):
                    state.receipts.append(receipt)
                    state.messages.append(_format_receipt_as_message(receipt))
                    state.updated_at = datetime.now(timezone.utc)
                    await self._state_backend.save(state)

                # ─── STEP 6: EVALUATE ───
                with _span("agent.step.6.evaluate", {"agent.step": step}) as eval_span:
                    try:
                        evaluation = await self._evaluator.evaluate(state)
                        if eval_span:
                            eval_span.set_attribute("eval.goal_achieved", evaluation.goal_achieved)
                            eval_span.set_attribute("eval.confidence", evaluation.confidence)
                            eval_span.set_attribute("eval.should_continue", evaluation.should_continue)
                    except Exception as exc:
                        evaluation = EvaluationResult(
                            goal_achieved=False,
                            confidence=0.0,
                            reasoning=f"Evaluator error: {exc}",
                            should_continue=True,
                        )

                if evaluation.goal_achieved:
                    state.status = "completed"
                    final_answer = evaluation.reasoning or "Goal achieved."
                    break

                if not evaluation.should_continue:
                    state.status = "failed"
                    final_answer = f"Agent stopped: {evaluation.reasoning}"
                    break

                # Step 7: continue (loop)

            else:
                # while/else: max_steps exceeded
                state.status = "max_steps_exceeded"
                final_answer = (
                    f"Maximum steps ({input.max_steps}) exceeded. "
                    f"Completed {len([r for r in state.receipts if r.status == 'success'])} "
                    f"successful tool calls out of {len(state.receipts)} total."
                )

            # ═══════ STEP 8: RESPOND ═══════
            total_ms = (time.monotonic() - run_start) * 1000
            with _span("agent.step.8.respond", {
                "agent.status": state.status,
                "agent.steps_taken": state.step_count,
                "agent.total_receipts": len(state.receipts),
                "agent.total_duration_ms": round(total_ms, 1),
            }):
                await self._state_backend.save(state)

            if root_span:
                root_span.set_attribute("agent.status", state.status)
                root_span.set_attribute("agent.steps_taken", state.step_count)
                root_span.set_attribute("agent.total_duration_ms", round(total_ms, 1))
                root_span.set_attribute("agent.goal_achieved", state.status == "completed")

            return AgentResponse(
                session_id=state.session_id,
                answer=final_answer,
                goal_achieved=state.status == "completed",
                receipts=state.receipts,
                steps_taken=state.step_count,
                status=state.status,
            )
