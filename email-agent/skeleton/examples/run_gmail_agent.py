"""
skeleton.examples.run_gmail_agent — Production Gmail agent using the skeleton framework.

This replaces the LangGraph create_react_agent() approach with the explicit
8-step skeleton loop, giving full visibility into planning, tool execution,
retries, receipts, and evaluation.

Starts a FastAPI server with:
  POST /agent/run     — Execute the Gmail agent
  GET  /agent/tools   — List all registered Gmail tools
  GET  /health        — Health check

Run:
    cd email-agent
    python -m skeleton.examples.run_gmail_agent

Then test:
    # Search emails
    curl -s -X POST http://localhost:8005/agent/run \\
      -H "Content-Type: application/json" \\
      -d '{"goal": "Search for unread emails from the last week"}' | python -m json.tool

    # Read + summarize
    curl -s -X POST http://localhost:8005/agent/run \\
      -H "Content-Type: application/json" \\
      -d '{"goal": "Find the latest email from my boss and summarize it"}' | python -m json.tool

    # Draft a reply
    curl -s -X POST http://localhost:8005/agent/run \\
      -H "Content-Type: application/json" \\
      -d '{"goal": "Draft a polite reply to the most recent unread email"}' | python -m json.tool

    # Classify emails
    curl -s -X POST http://localhost:8005/agent/run \\
      -H "Content-Type: application/json" \\
      -d '{"goal": "Find emails labeled INBOX that are older than 30 days and archive them"}' | python -m json.tool
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
    TracedAgentRunner,
)
from skeleton.gmail_tools import gmail_registry

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
# Build the Gmail agent
# ──────────────────────────────────────────────────────────────────────

state_backend = InMemoryStateBackend()

# StructuredPlanner uses native tool_use for reliable structured output
planner = StructuredPlanner(temperature=0.0)

# SimpleEvaluator: trusts the planner's finish decision, stops on 3 consecutive failures
evaluator = SimpleEvaluator(max_consecutive_failures=3)

# Base runner with Gmail tools
base_runner = AgentRunner(
    registry=gmail_registry,
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
    title="Gmail Agent (Skeleton Framework)",
    description=(
        "Production-ready Gmail AI agent built on the 8-step skeleton framework. "
        "Replaces LangGraph's create_react_agent() with explicit control over "
        "planning, tool execution, retries, receipts, and evaluation."
    ),
    version="1.0.0",
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
        "agent": "gmail",
        "tools": gmail_registry.tool_names,
        "tool_count": len(gmail_registry.tool_names),
        "planner": "StructuredPlanner (native tool_use)",
        "tracing": "OpenTelemetry" if hasattr(runner, '_runner') else "disabled",
    }


@app.get("/agent/tools")
async def list_tools():
    """List all registered Gmail tools with their schemas."""
    return {
        "tools": [t.model_dump() for t in gmail_registry.list_tools()],
    }


@app.post("/agent/run", response_model=AgentResponse)
async def run_agent(input: AgentInput):
    """
    Execute the 8-step Gmail agent loop.

    The response includes:
      - answer: The final answer
      - goal_achieved: Whether the goal was met
      - receipts: Full audit trail of every Gmail API call
      - steps_taken: How many loop iterations occurred
      - status: completed | failed | max_steps_exceeded
    """
    try:
        response = await runner.run(input)
        return response
    except Exception as exc:
        logger.exception("Gmail agent run failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────────────────────────────────
# Run directly
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("GMAIL_AGENT_PORT", "8005"))

    print("\n" + "=" * 60)
    print("  Gmail Agent (Skeleton Framework) v1.0")
    print("=" * 60)
    print(f"  Tools:    {', '.join(gmail_registry.tool_names)}")
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
