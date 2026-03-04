"""
Example tools: basic calculator operations.

Demonstrates:
  • @agent_tool decorator
  • Type-hinted parameters → auto-generated JSON Schema
  • Idempotent, pure functions with no side effects
"""

from __future__ import annotations

from ..tools import ToolRegistry, agent_tool

# Create a dedicated registry for calculator tools
# (keeps examples isolated from the default global registry)
calculator_registry = ToolRegistry()


@agent_tool(
    name="add",
    description="Add two numbers together. Returns the sum.",
    timeout_seconds=5,
    max_retries=0,
    idempotent=True,
    registry=calculator_registry,
)
async def add(a: float, b: float) -> float:
    """Add a + b."""
    return a + b


@agent_tool(
    name="subtract",
    description="Subtract b from a. Returns the difference (a - b).",
    timeout_seconds=5,
    max_retries=0,
    idempotent=True,
    registry=calculator_registry,
)
async def subtract(a: float, b: float) -> float:
    """Subtract a - b."""
    return a - b


@agent_tool(
    name="multiply",
    description="Multiply two numbers. Returns the product.",
    timeout_seconds=5,
    max_retries=0,
    idempotent=True,
    registry=calculator_registry,
)
async def multiply(a: float, b: float) -> float:
    """Multiply a * b."""
    return a * b


@agent_tool(
    name="divide",
    description="Divide a by b. Returns the quotient. Raises error if b is zero.",
    timeout_seconds=5,
    max_retries=0,
    idempotent=True,
    registry=calculator_registry,
)
async def divide(a: float, b: float) -> float:
    """Divide a / b."""
    if b == 0:
        raise ValueError("Division by zero is not allowed")
    return a / b
