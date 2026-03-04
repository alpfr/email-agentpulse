"""
skeleton.planner — Decides what the agent does next.

The Planner protocol is pluggable.  Two LLM implementations:

  • StructuredPlanner  — Uses native tool_use / function_calling for
                         reliable structured output (RECOMMENDED)
  • LLMPlanner         — Original free-form JSON planner (fallback)

The StructuredPlanner uses LangChain's .bind_tools() to define two
"meta-tools" — `call_tool` and `finish` — so the LLM returns structured
tool invocations instead of free-form JSON.  This eliminates parse failures.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from .errors import PlannerError
from .models import AgentState, PlannerDecision, ToolCall, ToolInfo

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Protocol (interface)
# ──────────────────────────────────────────────────────────────────────


@runtime_checkable
class Planner(Protocol):
    """
    Given the current agent state and available tools, decide the next action.

    Returns PlannerDecision with action = "call_tool" or "finish".
    """

    async def plan_next_step(
        self,
        state: AgentState,
        available_tools: list[ToolInfo],
    ) -> PlannerDecision: ...


# ──────────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────────


def _build_tools_section(tools: list[ToolInfo]) -> str:
    """Format tool metadata into a readable section for the system prompt."""
    lines: list[str] = []
    for t in tools:
        params = json.dumps(t.parameters_schema, indent=2)
        lines.append(f"### {t.name}\n{t.description}\nParameters:\n```json\n{params}\n```\n")
    return "\n".join(lines)


def _build_llm(provider: str, model: str, temperature: float) -> Any:
    """Construct the LangChain chat model (shared by both planners)."""
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, temperature=temperature)
    else:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=1024,
        )


def _resolve_llm_config(
    provider: str | None,
    model: str | None,
) -> tuple[str, str]:
    """Resolve provider/model from explicit args or env vars."""
    p = provider or os.getenv("LLM_PROVIDER", "anthropic")
    m = model or os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
    return p, m


def _build_lc_messages(state: AgentState, system_prompt: str) -> list:
    """Build LangChain message list from state."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    lc_messages: list = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Goal: {state.goal}"),
    ]
    for msg in state.messages:
        role = msg["role"]
        content = msg["content"]
        if role == "assistant":
            lc_messages.append(AIMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))
    return lc_messages


# ──────────────────────────────────────────────────────────────────────
# StructuredPlanner — uses native tool_use / function_calling
#                     (RECOMMENDED for production)
# ──────────────────────────────────────────────────────────────────────


STRUCTURED_SYSTEM_PROMPT = """\
You are a planning module inside an AI agent.  Your job is to decide the
SINGLE next action the agent should take to accomplish the user's goal.

You have access to the following agent tools:
{tools_section}

## Instructions
- Analyze the goal and any previous tool results in the conversation.
- Decide whether to call ONE agent tool, or finish with a final answer.
- To call an agent tool, use the `call_tool` function with the tool name and arguments.
- To finish, use the `finish` function with your final answer.
- Do NOT repeat a tool call with identical arguments if the result is already available.
- Keep reasoning concise (1-2 sentences).
"""

# These are "meta-tools" the LLM calls to communicate its decision.
# They are NOT the actual agent tools — they're a structured channel.
_CALL_TOOL_SCHEMA = {
    "name": "call_tool",
    "description": (
        "Call one of the available agent tools. "
        "Provide the tool_name exactly as listed, "
        "the arguments as a JSON object, and brief reasoning."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "description": "The exact name of the agent tool to call.",
            },
            "arguments": {
                "type": "object",
                "description": "Arguments to pass to the tool, matching its parameter schema.",
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of why this tool is being called.",
            },
        },
        "required": ["tool_name", "arguments", "reasoning"],
    },
}

_FINISH_SCHEMA = {
    "name": "finish",
    "description": (
        "The goal has been achieved or cannot be achieved. "
        "Return the final answer to the user."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "final_answer": {
                "type": "string",
                "description": "The complete answer to the user's goal, based on tool results.",
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of why the goal is complete.",
            },
        },
        "required": ["final_answer", "reasoning"],
    },
}


class StructuredPlanner:
    """
    Planner that uses native tool_use (Anthropic) or function_calling (OpenAI)
    for reliable structured output.

    Instead of asking the LLM to produce free-form JSON (which can fail to parse),
    this planner defines two meta-tools — `call_tool` and `finish` — using
    LangChain's `.bind_tools()`.  The LLM's response is always a valid tool
    invocation, eliminating parse errors.

    This is the RECOMMENDED planner for production use.
    """

    def __init__(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        self._provider, self._model = _resolve_llm_config(provider, model)
        self._temperature = temperature
        self._llm = _build_llm(self._provider, self._model, self._temperature)

    async def plan_next_step(
        self,
        state: AgentState,
        available_tools: list[ToolInfo],
    ) -> PlannerDecision:
        """
        Ask the LLM to call either `call_tool` or `finish` via native tool_use.
        """
        tools_section = _build_tools_section(available_tools)
        system_prompt = STRUCTURED_SYSTEM_PROMPT.format(tools_section=tools_section)
        lc_messages = _build_lc_messages(state, system_prompt)

        # Bind the two meta-tools and invoke
        try:
            llm_with_tools = self._llm.bind_tools(
                [_CALL_TOOL_SCHEMA, _FINISH_SCHEMA],
                tool_choice="any",  # Force the LLM to use a tool (no free text)
            )
            response = await llm_with_tools.ainvoke(lc_messages)
        except Exception as exc:
            raise PlannerError(
                f"LLM invocation failed: {exc}",
                details={"provider": self._provider, "model": self._model},
            ) from exc

        # Extract tool calls from the response
        tool_calls = getattr(response, "tool_calls", None) or []

        if not tool_calls:
            # LLM responded with text instead of a tool call (shouldn't happen
            # with tool_choice="any", but handle gracefully).
            raw_text = response.content if hasattr(response, "content") else str(response)
            logger.warning(
                "StructuredPlanner: LLM returned text instead of tool call. "
                "Treating as finish: %s",
                raw_text[:200],
            )
            return PlannerDecision(
                action="finish",
                final_answer=raw_text,
                reasoning="LLM responded with text (no tool call).",
            )

        # Use the first tool call
        tc = tool_calls[0]
        meta_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
        args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})

        if meta_name == "finish":
            return PlannerDecision(
                action="finish",
                final_answer=args.get("final_answer", ""),
                reasoning=args.get("reasoning", ""),
            )

        if meta_name == "call_tool":
            tool_name = args.get("tool_name", "")
            tool_args = args.get("arguments", {})
            reasoning = args.get("reasoning", "")

            if not tool_name:
                raise PlannerError(
                    "StructuredPlanner: call_tool missing tool_name",
                    details={"args": args},
                )

            return PlannerDecision(
                action="call_tool",
                tool_call=ToolCall(
                    tool_name=tool_name,
                    arguments=tool_args,
                    idempotency_key=uuid4().hex,
                    reasoning=reasoning,
                ),
                reasoning=reasoning,
            )

        raise PlannerError(
            f"StructuredPlanner: unexpected meta-tool '{meta_name}'",
            details={"tool_calls": [str(tc) for tc in tool_calls]},
        )


# ──────────────────────────────────────────────────────────────────────
# LLMPlanner — free-form JSON fallback
# ──────────────────────────────────────────────────────────────────────


FREEFORM_SYSTEM_PROMPT = """\
You are a planning module inside an AI agent.  Your job is to decide the
SINGLE next action: either call exactly one tool, or finish with a final answer.

## Available Tools
{tools_section}

## Rules
1. Respond ONLY with valid JSON — no markdown fences, no commentary.
2. If you need to call a tool, respond with:
   {{"action": "call_tool", "tool_name": "<name>", "arguments": {{...}}, "reasoning": "..."}}
3. If the goal is achieved (or cannot be achieved), respond with:
   {{"action": "finish", "final_answer": "...", "reasoning": "..."}}
4. Only call tools from the list above.
5. Use information from previous tool results (shown in the conversation)
   to inform your decisions.  Do NOT repeat a tool call with identical arguments.
6. Keep reasoning concise (1-2 sentences).
"""


def _parse_planner_response(raw: str) -> PlannerDecision:
    """Parse the LLM's free-form JSON response into a PlannerDecision."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise PlannerError(
            f"Failed to parse planner JSON: {exc}",
            details={"raw_response": raw[:500]},
        ) from exc

    action = data.get("action")
    if action not in ("call_tool", "finish"):
        raise PlannerError(
            f"Invalid planner action: {action!r}",
            details={"raw_response": raw[:500]},
        )

    reasoning = data.get("reasoning", "")

    if action == "finish":
        return PlannerDecision(
            action="finish",
            final_answer=data.get("final_answer", ""),
            reasoning=reasoning,
        )

    tool_name = data.get("tool_name")
    arguments = data.get("arguments", {})
    if not tool_name:
        raise PlannerError(
            "Planner returned call_tool but no tool_name",
            details={"raw_response": raw[:500]},
        )

    return PlannerDecision(
        action="call_tool",
        tool_call=ToolCall(
            tool_name=tool_name,
            arguments=arguments,
            idempotency_key=uuid4().hex,
            reasoning=reasoning,
        ),
        reasoning=reasoning,
    )


class LLMPlanner:
    """
    Planner that uses free-form JSON responses from the LLM.

    Works with any LLM but is less reliable than StructuredPlanner.
    Use StructuredPlanner for production; keep LLMPlanner as a
    fallback for models that don't support tool_use.
    """

    def __init__(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        self._provider, self._model = _resolve_llm_config(provider, model)
        self._temperature = temperature
        self._llm = _build_llm(self._provider, self._model, self._temperature)

    async def plan_next_step(
        self,
        state: AgentState,
        available_tools: list[ToolInfo],
    ) -> PlannerDecision:
        """Ask the LLM which tool to call next (or whether to finish)."""
        tools_section = _build_tools_section(available_tools)
        system_prompt = FREEFORM_SYSTEM_PROMPT.format(tools_section=tools_section)
        lc_messages = _build_lc_messages(state, system_prompt)

        try:
            response = await self._llm.ainvoke(lc_messages)
            raw_text = response.content if hasattr(response, "content") else str(response)
            logger.debug("Planner raw response: %s", raw_text[:300])
            return _parse_planner_response(raw_text)
        except PlannerError:
            raise
        except Exception as exc:
            raise PlannerError(
                f"LLM invocation failed: {exc}",
                details={"provider": self._provider, "model": self._model},
            ) from exc
