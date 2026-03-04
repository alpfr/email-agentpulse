"""Tests for skeleton.tools — ToolRegistry, decorator, execute_tool."""

from __future__ import annotations

import asyncio

import pytest

from skeleton.errors import ToolNotFoundError
from skeleton.models import ToolCall
from skeleton.tools import ToolRegistry, agent_tool, execute_tool


class TestToolRegistry:
    def test_register_and_get(self, registry: ToolRegistry):
        tool = registry.get("add")
        assert tool is not None
        assert tool.name == "add"
        assert tool.description == "Add two numbers"

    def test_get_nonexistent(self, registry: ToolRegistry):
        assert registry.get("nonexistent") is None

    def test_has(self, registry: ToolRegistry):
        assert registry.has("add")
        assert not registry.has("nonexistent")

    def test_tool_names(self, registry: ToolRegistry):
        names = registry.tool_names
        assert "add" in names
        assert "multiply" in names

    def test_list_tools(self, registry: ToolRegistry):
        tools = registry.list_tools()
        assert len(tools) >= 2
        names = [t.name for t in tools]
        assert "add" in names

    def test_list_tool_schemas(self, registry: ToolRegistry):
        schemas = registry.list_tool_schemas()
        assert len(schemas) >= 2
        add_schema = next(s for s in schemas if s["name"] == "add")
        assert "parameters" in add_schema
        assert add_schema["parameters"]["properties"]["a"]["type"] == "number"

    def test_register_sync_function_raises(self):
        reg = ToolRegistry()

        def sync_fn(x: int) -> int:
            return x

        with pytest.raises(TypeError, match="must be an async function"):
            reg.register(sync_fn, name="sync_tool")


class TestAgentToolDecorator:
    def test_decorator_registers(self):
        reg = ToolRegistry()

        @agent_tool(name="my_tool", description="Test", timeout_seconds=3, registry=reg)
        async def my_tool(x: int) -> int:
            return x * 2

        assert reg.has("my_tool")
        tool = reg.get("my_tool")
        assert tool.timeout_seconds == 3

    @pytest.mark.asyncio
    async def test_decorator_preserves_function(self):
        reg = ToolRegistry()

        @agent_tool(name="double", description="Double it", registry=reg)
        async def double(n: float) -> float:
            return n * 2

        # The original function should still work
        result = await double(5)
        assert result == 10


class TestExecuteTool:
    @pytest.mark.asyncio
    async def test_successful_execution(self, registry: ToolRegistry):
        call = ToolCall(tool_name="add", arguments={"a": 3, "b": 4})
        executed = set()
        receipt = await execute_tool(registry, call, executed)

        assert receipt.status == "success"
        assert receipt.result == 7.0
        assert receipt.error is None
        assert receipt.duration_ms >= 0
        assert receipt.attempt == 1
        assert call.idempotency_key in executed

    @pytest.mark.asyncio
    async def test_idempotency_skip(self, registry: ToolRegistry):
        call = ToolCall(tool_name="add", arguments={"a": 1, "b": 2}, idempotency_key="key-1")
        executed = {"key-1"}  # Already executed
        receipt = await execute_tool(registry, call, executed)

        assert receipt.status == "skipped_duplicate"
        assert receipt.duration_ms == 0.0

    @pytest.mark.asyncio
    async def test_tool_not_found(self, registry: ToolRegistry):
        call = ToolCall(tool_name="nonexistent", arguments={})
        with pytest.raises(ToolNotFoundError):
            await execute_tool(registry, call, set())

    @pytest.mark.asyncio
    async def test_timeout_with_retry(self, registry: ToolRegistry):
        call = ToolCall(tool_name="slow_tool", arguments={})
        executed = set()
        receipt = await execute_tool(registry, call, executed, base_delay=0.01)

        assert receipt.status == "timeout"
        assert "Timeout" in receipt.error
        assert receipt.total_attempts == 1  # max_retries=0

    @pytest.mark.asyncio
    async def test_error_with_retry(self, registry: ToolRegistry):
        call = ToolCall(tool_name="fail_always", arguments={})
        executed = set()
        receipt = await execute_tool(registry, call, executed, base_delay=0.01)

        assert receipt.status == "error"
        assert "RuntimeError" in receipt.error
        assert receipt.total_attempts == 2  # 1 initial + 1 retry

    @pytest.mark.asyncio
    async def test_different_keys_both_execute(self, registry: ToolRegistry):
        executed = set()
        call1 = ToolCall(tool_name="add", arguments={"a": 1, "b": 2}, idempotency_key="k1")
        call2 = ToolCall(tool_name="add", arguments={"a": 1, "b": 2}, idempotency_key="k2")

        r1 = await execute_tool(registry, call1, executed)
        r2 = await execute_tool(registry, call2, executed)

        assert r1.status == "success"
        assert r2.status == "success"
        assert executed == {"k1", "k2"}
