"""Tests for skeleton.state — StateBackend implementations."""

from __future__ import annotations

import tempfile

import pytest

from skeleton.models import AgentState
from skeleton.state import FileStateBackend, InMemoryStateBackend


class TestInMemoryStateBackend:
    @pytest.mark.asyncio
    async def test_save_and_load(self):
        backend = InMemoryStateBackend()
        state = AgentState(goal="Test")
        await backend.save(state)

        loaded = await backend.load(state.session_id)
        assert loaded is not None
        assert loaded.goal == "Test"
        assert loaded.session_id == state.session_id

    @pytest.mark.asyncio
    async def test_load_nonexistent(self):
        backend = InMemoryStateBackend()
        result = await backend.load("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self):
        backend = InMemoryStateBackend()
        state = AgentState(goal="Test")
        await backend.save(state)
        await backend.delete(state.session_id)
        assert await backend.load(state.session_id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_noop(self):
        backend = InMemoryStateBackend()
        await backend.delete("does-not-exist")  # Should not raise

    @pytest.mark.asyncio
    async def test_overwrite(self):
        backend = InMemoryStateBackend()
        state = AgentState(goal="Original")
        await backend.save(state)

        state.goal = "Updated"
        state.step_count = 5
        await backend.save(state)

        loaded = await backend.load(state.session_id)
        assert loaded.goal == "Updated"
        assert loaded.step_count == 5


class TestFileStateBackend:
    @pytest.mark.asyncio
    async def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileStateBackend(tmpdir)
            state = AgentState(goal="File test")
            await backend.save(state)

            loaded = await backend.load(state.session_id)
            assert loaded is not None
            assert loaded.goal == "File test"

    @pytest.mark.asyncio
    async def test_load_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileStateBackend(tmpdir)
            assert await backend.load("nonexistent") is None

    @pytest.mark.asyncio
    async def test_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileStateBackend(tmpdir)
            state = AgentState(goal="Delete me")
            await backend.save(state)
            await backend.delete(state.session_id)
            assert await backend.load(state.session_id) is None

    @pytest.mark.asyncio
    async def test_persists_receipts(self):
        """Ensure complex nested state (receipts) round-trips through JSON."""
        from datetime import datetime, timezone
        from skeleton.models import ToolReceipt

        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileStateBackend(tmpdir)
            state = AgentState(goal="Receipt test")
            state.receipts.append(
                ToolReceipt(
                    tool_name="add",
                    arguments={"a": 1, "b": 2},
                    idempotency_key="test-key",
                    status="success",
                    result=3.0,
                    error=None,
                    started_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc),
                    duration_ms=1.5,
                    attempt=1,
                    total_attempts=1,
                )
            )
            await backend.save(state)

            loaded = await backend.load(state.session_id)
            assert len(loaded.receipts) == 1
            assert loaded.receipts[0].tool_name == "add"
            assert loaded.receipts[0].result == 3.0
