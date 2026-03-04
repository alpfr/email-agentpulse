"""
skeleton.examples.run_example — Runnable FastAPI demo of the agent skeleton.

Starts a FastAPI server with:
  POST /agent/run     — Execute the agent with calculator + weather tools
  GET  /agent/tools   — List all registered tools
  GET  /health        — Health check

Uses StructuredPlanner (native tool_use) by default for reliability.
Wraps the runner in TracedAgentRunner for OpenTelemetry observability.

Run:
    cd email-agent
    python -m skeleton.examples.run_example

Then test:
    # Calculator (multi-step)
    curl -s -X POST http://localhost:8003/agent/run \
      -H "Content-Type: application/json" \
      -d '{"goal": "What is 5 + 3, then multiply the result by 2?"}' | python -m json.tool

    # Weather
    curl -s -X POST http://localhost:8003/agent/run \
      -H "Content-Type: application/json" \
      -d '{"goal": "What is the weather in Tokyo?"}' | python -m json.tool

    # Cross-domain
    curl -s -X POST http://localhost:8003/agent/run \
      -H "Content-Type: application/json" \
      -d '{"goal": "Compare weather in New York and London, then add their temperatures in Fahrenheit"}' | python -m json.tool

    # Bounded execution
    curl -s -X POST http://localhost:8003/agent/run \
      -H "Content-Type: application/json" \
      -d '{"goal": "Keep adding 1 to itself forever", "max_steps": 3}' | python -m json.tool
"""

from __future__ import annotations

import logging
import os
import sys

# ── Ensure the project root is on sys.path ──
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from skeleton import (
    AgentInput,
    AgentResponse,
    AgentRunner,
    InMemoryStateBackend,
    SimpleEvaluator,
    StructuredPlanner,
    ToolRegistry,
    TracedAgentRunner,
)
from skeleton.examples.calculator_tools import calculator_registry
from skeleton.examples.weather_tools import weather_registry

# ── Load environment ──
load_dotenv()

# ── Configure logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-28s │ %(levelname)-5s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Merge tool registries
# ──────────────────────────────────────────────────────────────────────


def _build_combined_registry() -> ToolRegistry:
    """Combine calculator + weather tools into a single registry."""
    combined = ToolRegistry()

    for source in [calculator_registry, weather_registry]:
        for tool_info in source.list_tools():
            original = source.get(tool_info.name)
            if original:
                combined.register(
                    original.fn,
                    name=original.name,
                    description=original.description,
                    timeout_seconds=original.timeout_seconds,
                    max_retries=original.max_retries,
                    idempotent=original.idempotent,
                )

    return combined


# ──────────────────────────────────────────────────────────────────────
# Build the agent
# ──────────────────────────────────────────────────────────────────────

registry = _build_combined_registry()
state_backend = InMemoryStateBackend()

# StructuredPlanner uses native tool_use / function_calling (RECOMMENDED)
planner = StructuredPlanner(temperature=0.0)

evaluator = SimpleEvaluator(max_consecutive_failures=3)

# Base runner
base_runner = AgentRunner(
    registry=registry,
    state_backend=state_backend,
    planner=planner,
    evaluator=evaluator,
)

# Wrap with OpenTelemetry tracing (graceful no-op if OTel not installed)
runner = TracedAgentRunner(base_runner)


# ──────────────────────────────────────────────────────────────────────
# FastAPI app
# ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Agent Skeleton Demo",
    description=(
        "Production-ready 8-step AI agent skeleton. "
        "Uses StructuredPlanner (native tool_use) + TracedAgentRunner (OTel spans)."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "tools": registry.tool_names,
        "tool_count": len(registry.tool_names),
        "planner": "StructuredPlanner (native tool_use)",
        "tracing": "OpenTelemetry" if hasattr(runner, '_runner') else "disabled",
    }


@app.get("/agent/tools")
async def list_tools():
    """List all registered tools with their schemas."""
    return {
        "tools": [t.model_dump() for t in registry.list_tools()],
    }


@app.post("/agent/run", response_model=AgentResponse)
async def run_agent(input: AgentInput):
    """
    Execute the 8-step agent loop.

    The response includes:
      - answer: The final answer
      - goal_achieved: Whether the goal was met
      - receipts: Full audit trail of every tool call
      - steps_taken: How many loop iterations occurred
      - status: completed | failed | max_steps_exceeded
    """
    try:
        response = await runner.run(input)
        return response
    except Exception as exc:
        logger.exception("Agent run failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────────────────────────────────
# Run directly
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("SKELETON_PORT", "8003"))

    print("\n" + "=" * 60)
    print("  Agent Skeleton Demo v2.0")
    print("=" * 60)
    print(f"  Tools:    {', '.join(registry.tool_names)}")
    print(f"  Planner:  StructuredPlanner ({planner._provider} / {planner._model})")
    print(f"  Tracing:  TracedAgentRunner (OTel)")
    print(f"  URL:      http://localhost:{port}")
    print("=" * 60 + "\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
