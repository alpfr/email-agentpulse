"""
Email AI Agent — Interactive CLI
----------------------------------
Run this to chat with your email agent in the terminal.

Usage:
    python main.py
"""

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage
from agent import get_agent


def print_banner():
    print("\n" + "=" * 60)
    print("  📧  Email AI Agent (LangGraph + Gmail)")
    print("=" * 60)
    print("  Commands:")
    print("    • Type your request in natural language")
    print("    • 'quit' or 'exit' to stop")
    print("=" * 60 + "\n")


def run_agent_stream(agent, user_input: str, thread_id: str = "default"):
    """Run the agent and stream its thinking + tool calls."""
    config = {"configurable": {"thread_id": thread_id}}

    print("\n🤖 Agent:")
    for event in agent.stream(
        {"messages": [HumanMessage(content=user_input)]},
        config=config,
        stream_mode="updates",
    ):
        for node_name, node_output in event.items():
            if node_name == "agent":
                # LLM response
                for msg in node_output.get("messages", []):
                    if hasattr(msg, "content") and msg.content and isinstance(msg.content, str):
                        print(f"  {msg.content}")
                    elif hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            print(f"  🔧 Calling: {tc['name']}({tc['args']})")
            elif node_name == "tools":
                # Tool responses
                for msg in node_output.get("messages", []):
                    content_preview = str(msg.content)[:300]
                    print(f"  📋 Result: {content_preview}...")

    print()


def main():
    print_banner()

    try:
        agent = get_agent()
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        print("   Make sure you have:")
        print("   1. Set up your .env file (copy from .env.example)")
        print("   2. Placed credentials.json in the project root")
        print("   3. Installed requirements: pip install -r requirements.txt")
        return

    print("✅ Agent ready! Start chatting.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("👋 Goodbye!")
            break

        try:
            run_agent_stream(agent, user_input)
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()
