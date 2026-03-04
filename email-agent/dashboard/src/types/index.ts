export interface Email {
  id: string;
  threadId: string;
  subject: string;
  from: string;
  date: string;
  snippet: string;
  labelIds: string[];
  isUnread: boolean;
}

export interface EmailDetail extends Email {
  to: string;
  body: string;
}

export interface ComposeData {
  to: string;
  subject: string;
  body: string;
  reply_to_message_id?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  toolCalls?: ToolCall[];
}

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  result?: string;
  status: "pending" | "complete";
}

export interface Label {
  id: string;
  name: string;
  type: string;
}
