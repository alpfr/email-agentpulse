"use client";

import { useState, useCallback, useRef } from "react";
import { streamChat, SSEEvent } from "@/lib/sse";
import { ChatMessage, ToolCall } from "@/types";

let msgIdCounter = 0;

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const closeRef = useRef<(() => void) | null>(null);

  const sendMessage = useCallback(
    (text: string) => {
      if (!text.trim() || isStreaming) return;

      const userMsg: ChatMessage = {
        id: `msg-${++msgIdCounter}`,
        role: "user",
        content: text,
      };

      const agentMsgId = `msg-${++msgIdCounter}`;

      setMessages((prev) => [
        ...prev,
        userMsg,
        { id: agentMsgId, role: "agent", content: "", toolCalls: [] },
      ]);

      setIsStreaming(true);

      const onEvent = (event: SSEEvent) => {
        switch (event.type) {
          case "thread_id":
            setThreadId(event.thread_id);
            break;

          case "agent_message":
            setMessages((prev) =>
              prev.map((m) =>
                m.id === agentMsgId
                  ? { ...m, content: m.content + event.content }
                  : m
              )
            );
            break;

          case "tool_call":
            setMessages((prev) =>
              prev.map((m) => {
                if (m.id !== agentMsgId) return m;
                const tc: ToolCall = {
                  name: event.name,
                  args: event.args,
                  status: "pending",
                };
                return { ...m, toolCalls: [...(m.toolCalls || []), tc] };
              })
            );
            break;

          case "tool_result":
            setMessages((prev) =>
              prev.map((m) => {
                if (m.id !== agentMsgId || !m.toolCalls?.length) return m;
                const toolCalls = [...m.toolCalls];
                const lastPending = toolCalls.findLastIndex(
                  (tc) => tc.status === "pending"
                );
                if (lastPending >= 0) {
                  toolCalls[lastPending] = {
                    ...toolCalls[lastPending],
                    result: event.content,
                    status: "complete",
                  };
                }
                return { ...m, toolCalls };
              })
            );
            break;

          case "error":
            setMessages((prev) =>
              prev.map((m) =>
                m.id === agentMsgId
                  ? { ...m, content: m.content || `Error: ${event.error}` }
                  : m
              )
            );
            setIsStreaming(false);
            break;

          case "done":
            setIsStreaming(false);
            break;
        }
      };

      closeRef.current = streamChat(text, threadId, onEvent);
    },
    [isStreaming, threadId]
  );

  const stopStreaming = useCallback(() => {
    closeRef.current?.();
    setIsStreaming(false);
  }, []);

  return { messages, isStreaming, sendMessage, stopStreaming };
}
