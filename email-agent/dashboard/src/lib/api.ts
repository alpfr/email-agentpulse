import { Email, EmailDetail, ComposeData, Label } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export const api = {
  listEmails: (q = "in:inbox", maxResults = 20) =>
    apiFetch<{ emails: Email[]; query: string }>(
      `/api/emails?q=${encodeURIComponent(q)}&max_results=${maxResults}`
    ),

  readEmail: (id: string) =>
    apiFetch<EmailDetail>(`/api/emails/${encodeURIComponent(id)}`),

  sendEmail: (data: ComposeData) =>
    apiFetch<{ message: string; id: string }>("/api/emails/send", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  draftEmail: (data: ComposeData) =>
    apiFetch<{ message: string; id: string }>("/api/emails/draft", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listLabels: () =>
    apiFetch<{ labels: Label[] }>("/api/labels"),

  modifyLabels: (id: string, data: { add_labels?: string[]; remove_labels?: string[] }) =>
    apiFetch<{ message: string }>(`/api/emails/${encodeURIComponent(id)}/labels`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
