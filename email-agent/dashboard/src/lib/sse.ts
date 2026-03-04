const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type SSEEvent =
  | { type: "thread_id"; thread_id: string }
  | { type: "agent_message"; content: string }
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; content: string }
  | { type: "error"; error: string }
  | { type: "done" };

export function streamChat(
  message: string,
  threadId: string | null,
  onEvent: (event: SSEEvent) => void
): () => void {
  const params = new URLSearchParams({ message });
  if (threadId) params.set("thread_id", threadId);

  const eventSource = new EventSource(`${API_BASE}/api/chat?${params}`);

  const handlers: Record<string, (e: MessageEvent) => void> = {
    thread_id: (e) => onEvent({ type: "thread_id", ...JSON.parse(e.data) }),
    agent_message: (e) => onEvent({ type: "agent_message", ...JSON.parse(e.data) }),
    tool_call: (e) => onEvent({ type: "tool_call", ...JSON.parse(e.data) }),
    tool_result: (e) => onEvent({ type: "tool_result", ...JSON.parse(e.data) }),
    error: (e) => {
      onEvent({ type: "error", error: JSON.parse(e.data).error });
      eventSource.close();
    },
    done: () => {
      onEvent({ type: "done" });
      eventSource.close();
    },
  };

  for (const [event, handler] of Object.entries(handlers)) {
    eventSource.addEventListener(event, handler as EventListener);
  }

  return () => eventSource.close();
}
