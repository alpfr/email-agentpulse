"""
skeleton — A production-ready 8-step AI agent framework.

Public API:
    from skeleton import AgentRunner, AgentInput, AgentResponse
    from skeleton import ToolRegistry, agent_tool
    from skeleton import InMemoryStateBackend, FileStateBackend
    from skeleton import StructuredPlanner, LLMPlanner, SimpleEvaluator, LLMEvaluator
    from skeleton import RedisStateBackend
"""

from .errors import (
    AgentError,
    MaxStepsExceededError,
    PlannerError,
    StateError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolTimeoutError,
    ValidationError,
)
from .evaluator import Evaluator, LLMEvaluator, SimpleEvaluator
from .models import (
    AgentInput,
    AgentResponse,
    AgentState,
    EvaluationResult,
    PlannerDecision,
    ToolCall,
    ToolInfo,
    ToolReceipt,
)
from .planner import LLMPlanner, Planner, StructuredPlanner
from .runner import AgentRunner
from .state import FileStateBackend, InMemoryStateBackend, StateBackend
from .telemetry import TracedAgentRunner
from .tools import ToolRegistry, agent_tool, get_default_registry

# Conditional imports — only available if optional deps installed
try:
    from .state_redis import RedisStateBackend
except ImportError:
    pass  # redis not installed; RedisStateBackend unavailable

__all__ = [
    # Runner
    "AgentRunner",
    "TracedAgentRunner",
    # Models
    "AgentInput",
    "AgentResponse",
    "AgentState",
    "EvaluationResult",
    "PlannerDecision",
    "ToolCall",
    "ToolInfo",
    "ToolReceipt",
    # Tools
    "ToolRegistry",
    "agent_tool",
    "get_default_registry",
    # State
    "StateBackend",
    "InMemoryStateBackend",
    "FileStateBackend",
    "RedisStateBackend",
    # Planner
    "Planner",
    "StructuredPlanner",
    "LLMPlanner",
    # Evaluator
    "Evaluator",
    "SimpleEvaluator",
    "LLMEvaluator",
    # Errors
    "AgentError",
    "ValidationError",
    "StateError",
    "PlannerError",
    "ToolExecutionError",
    "ToolTimeoutError",
    "ToolNotFoundError",
    "MaxStepsExceededError",
]
