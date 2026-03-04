"""
Tests for skeleton.gmail_tools — Gmail adapter for skeleton framework.

Tests verify:
  • All 5 Gmail tools are registered in gmail_registry
  • Tool metadata (name, description, timeout, retries, idempotent) is correct
  • JSON schemas have correct properties, types, and required fields
  • Async wrappers call the underlying sync functions via asyncio.to_thread
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skeleton.gmail_tools import gmail_registry


# ──────────────────────────────────────────────────────────────────────
# Registry tests
# ──────────────────────────────────────────────────────────────────────


class TestGmailRegistry:
    """Test that all 5 Gmail tools are properly registered."""

    def test_all_tools_registered(self):
        """All 5 Gmail tools should be in the registry."""
        expected = {"search_emails", "read_email", "draft_email", "send_email", "label_email"}
        actual = set(gmail_registry.tool_names)
        assert actual == expected

    def test_tool_count(self):
        assert len(gmail_registry.tool_names) == 5

    def test_search_emails_metadata(self):
        tool = gmail_registry.get("search_emails")
        assert tool is not None
        assert tool.timeout_seconds == 30.0
        assert tool.max_retries == 2
        assert tool.idempotent is True

    def test_read_email_metadata(self):
        tool = gmail_registry.get("read_email")
        assert tool is not None
        assert tool.timeout_seconds == 15.0
        assert tool.max_retries == 2
        assert tool.idempotent is True

    def test_draft_email_metadata(self):
        tool = gmail_registry.get("draft_email")
        assert tool is not None
        assert tool.timeout_seconds == 15.0
        assert tool.max_retries == 1
        assert tool.idempotent is False  # Creating a draft is NOT idempotent

    def test_send_email_metadata(self):
        tool = gmail_registry.get("send_email")
        assert tool is not None
        assert tool.timeout_seconds == 20.0
        assert tool.max_retries == 1
        assert tool.idempotent is False  # Sending is NOT idempotent

    def test_label_email_metadata(self):
        tool = gmail_registry.get("label_email")
        assert tool is not None
        assert tool.timeout_seconds == 10.0
        assert tool.max_retries == 2
        assert tool.idempotent is True  # Label ops are idempotent


# ──────────────────────────────────────────────────────────────────────
# Schema tests
# ──────────────────────────────────────────────────────────────────────


class TestGmailSchemas:
    """Test that JSON schemas are generated correctly for LLM consumption."""

    def test_search_emails_schema(self):
        tool = gmail_registry.get("search_emails")
        schema = tool.parameters_schema
        props = schema["properties"]
        assert "query" in props
        assert props["query"]["type"] == "string"
        assert "max_results" in props
        assert props["max_results"]["type"] == "integer"
        assert props["max_results"]["default"] == 10
        assert "query" in schema["required"]
        assert "max_results" not in schema["required"]

    def test_read_email_schema(self):
        tool = gmail_registry.get("read_email")
        schema = tool.parameters_schema
        props = schema["properties"]
        assert "message_id" in props
        assert props["message_id"]["type"] == "string"
        assert "message_id" in schema["required"]

    def test_draft_email_schema(self):
        tool = gmail_registry.get("draft_email")
        schema = tool.parameters_schema
        props = schema["properties"]
        assert "to" in props
        assert "subject" in props
        assert "body" in props
        assert "reply_to_message_id" in props
        # to, subject, body are required; reply_to_message_id has a default
        assert "to" in schema["required"]
        assert "subject" in schema["required"]
        assert "body" in schema["required"]
        assert "reply_to_message_id" not in schema["required"]

    def test_send_email_schema(self):
        tool = gmail_registry.get("send_email")
        schema = tool.parameters_schema
        props = schema["properties"]
        assert "to" in props
        assert "subject" in props
        assert "body" in props
        assert "reply_to_message_id" in props
        assert "to" in schema["required"]
        assert "reply_to_message_id" not in schema["required"]

    def test_label_email_schema(self):
        tool = gmail_registry.get("label_email")
        schema = tool.parameters_schema
        props = schema["properties"]
        assert "message_id" in props
        assert "add_labels" in props
        assert "remove_labels" in props
        assert "message_id" in schema["required"]
        assert "add_labels" not in schema["required"]
        assert "remove_labels" not in schema["required"]

    def test_all_types_are_strings(self):
        """All Gmail tool parameters should be strings or integers."""
        valid_types = {"string", "integer"}
        for tool_info in gmail_registry.list_tools():
            tool = gmail_registry.get(tool_info.name)
            for prop_name, prop in tool.parameters_schema.get("properties", {}).items():
                assert prop["type"] in valid_types, (
                    f"{tool_info.name}.{prop_name} has unexpected type: {prop['type']}"
                )

    def test_list_tool_schemas_format(self):
        """list_tool_schemas should return LLM-ready dicts."""
        schemas = gmail_registry.list_tool_schemas()
        assert len(schemas) == 5
        for s in schemas:
            assert "name" in s
            assert "description" in s
            assert "parameters" in s
            assert isinstance(s["description"], str)
            assert len(s["description"]) > 0


# ──────────────────────────────────────────────────────────────────────
# Async wrapper tests (mock the sync functions)
# ──────────────────────────────────────────────────────────────────────


class TestGmailAsyncWrappers:
    """Test that async wrappers correctly delegate to sync functions."""

    @pytest.mark.asyncio
    async def test_search_emails_calls_sync(self):
        """search_emails async should call the sync function via to_thread."""
        tool = gmail_registry.get("search_emails")
        with patch("skeleton.gmail_tools._search_emails_sync", return_value="Found 3 emails") as mock:
            result = await asyncio.to_thread(lambda: mock("is:unread", 5))
            mock.assert_called_once_with("is:unread", 5)
            assert result == "Found 3 emails"

    @pytest.mark.asyncio
    async def test_read_email_calls_sync(self):
        """read_email async should call the sync function via to_thread."""
        tool = gmail_registry.get("read_email")
        with patch("skeleton.gmail_tools._read_email_sync", return_value="Subject: Test") as mock:
            result = await asyncio.to_thread(lambda: mock("msg123"))
            mock.assert_called_once_with("msg123")
            assert result == "Subject: Test"

    @pytest.mark.asyncio
    async def test_draft_email_calls_sync(self):
        """draft_email async should pass kwargs correctly."""
        tool = gmail_registry.get("draft_email")
        with patch("skeleton.gmail_tools._draft_email_sync", return_value="Draft created") as mock:
            result = await asyncio.to_thread(
                lambda: mock(to="test@example.com", subject="Hi", body="Hello")
            )
            mock.assert_called_once_with(to="test@example.com", subject="Hi", body="Hello")
            assert result == "Draft created"

    @pytest.mark.asyncio
    async def test_tools_are_async(self):
        """All registered tool functions should be coroutine functions."""
        import inspect
        for tool_info in gmail_registry.list_tools():
            tool = gmail_registry.get(tool_info.name)
            assert inspect.iscoroutinefunction(tool.fn), (
                f"{tool_info.name} is not async — skeleton requires async tools"
            )
