"use client";

const features = [
  {
    title: "Smart Inbox",
    description: "Browse, search, and manage your Gmail inbox with a clean, responsive interface. Unread indicators, labels, and threaded conversations at a glance.",
    icon: (
      <svg className="h-6 w-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
      </svg>
    ),
  },
  {
    title: "AI Agent Chat",
    description: "Interact with your emails using natural language. The LangGraph ReAct agent can search, read, draft, send, and label emails on your behalf.",
    icon: (
      <svg className="h-6 w-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
  },
  {
    title: "Compose & Drafts",
    description: "Send emails and save drafts directly from the dashboard. Supports replies with proper threading and message references.",
    icon: (
      <svg className="h-6 w-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
      </svg>
    ),
  },
  {
    title: "Real-time Streaming",
    description: "Agent responses stream in real-time via Server-Sent Events (SSE). See tool calls, results, and messages as they happen.",
    icon: (
      <svg className="h-6 w-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    title: "Security Hardened",
    description: "Email validation prevents header injection attacks. OAuth tokens are stored with restrictive file permissions. Input fields are sanitized.",
    icon: (
      <svg className="h-6 w-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
  },
  {
    title: "Responsive Design",
    description: "Three-column desktop layout with sidebar, content, and chat panel. On mobile, a bottom tab navigation provides full access to all features.",
    icon: (
      <svg className="h-6 w-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    ),
  },
];

const techStack = [
  { name: "Next.js 14", category: "Frontend", description: "App Router with React Server Components" },
  { name: "Tailwind CSS", category: "Frontend", description: "Utility-first CSS framework" },
  { name: "TypeScript", category: "Frontend", description: "Type-safe development" },
  { name: "FastAPI", category: "Backend", description: "High-performance Python API framework" },
  { name: "LangGraph", category: "AI", description: "ReAct agent with tool calling and memory" },
  { name: "Gmail API", category: "Integration", description: "OAuth2 authentication and email operations" },
  { name: "SSE", category: "Streaming", description: "Server-Sent Events for real-time agent responses" },
];

const agentTools = [
  { name: "search_emails", description: "Search Gmail using native query syntax" },
  { name: "read_email", description: "Read full email content by message ID" },
  { name: "draft_email", description: "Create a draft saved for review" },
  { name: "send_email", description: "Send an email directly" },
  { name: "label_email", description: "Add or remove labels to classify emails" },
];

export default function AboutPage() {
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl px-6 py-10">
        {/* Header */}
        <div className="mb-10">
          <div className="flex items-center gap-3 mb-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-600">
              <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-slate-900">AgentPulse</h1>
          </div>
          <p className="text-base text-slate-600 leading-relaxed">
            A full-stack email management platform powered by a LangGraph ReAct AI agent.
            Manage your Gmail inbox, compose emails, and interact with an AI assistant that
            can search, read, draft, send, and label emails using natural language.
          </p>
        </div>

        {/* Architecture */}
        <section className="mb-10">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Architecture</h2>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-5 font-mono text-xs leading-relaxed text-slate-700 overflow-x-auto">
            <pre>{`Browser (Next.js)     FastAPI Server        External Services
┌──────────────┐  REST  ┌──────────────┐     ┌────────────┐
│  Inbox       │──────→ │ /api/emails  │────→│  Gmail API │
│  Compose     │──────→ │ /api/send    │────→│            │
│  Detail View │──────→ │ /api/labels  │────→│            │
│              │  SSE   │              │     └────────────┘
│  AI Chat     │◀━━━━━━ │ /api/chat    │────→┌────────────┐
└──────────────┘        │  LangGraph   │     │  LLM       │
                        │  + Memory    │────→│ Claude/GPT │
                        └──────────────┘     └────────────┘`}</pre>
          </div>
        </section>

        {/* Features */}
        <section className="mb-10">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Features</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="rounded-xl border border-slate-200 bg-white p-4 transition-shadow hover:shadow-sm"
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-50">
                    {feature.icon}
                  </div>
                  <h3 className="text-sm font-semibold text-slate-900">{feature.title}</h3>
                </div>
                <p className="text-sm text-slate-500 leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* AI Agent Tools */}
        <section className="mb-10">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">AI Agent Tools</h2>
          <p className="text-sm text-slate-600 mb-3">
            The LangGraph ReAct agent has access to these Gmail tools and decides which to use based on your request:
          </p>
          <div className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-100">
            {agentTools.map((tool) => (
              <div key={tool.name} className="flex items-start gap-3 px-4 py-3">
                <code className="mt-0.5 shrink-0 rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-primary-700">
                  {tool.name}
                </code>
                <span className="text-sm text-slate-600">{tool.description}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Tech Stack */}
        <section className="mb-10">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Tech Stack</h2>
          <div className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-100">
            {techStack.map((tech) => (
              <div key={tech.name} className="flex items-center gap-3 px-4 py-3">
                <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                  {tech.category}
                </span>
                <span className="text-sm font-medium text-slate-900">{tech.name}</span>
                <span className="text-sm text-slate-400">—</span>
                <span className="text-sm text-slate-500">{tech.description}</span>
              </div>
            ))}
          </div>
        </section>

        {/* API Endpoints */}
        <section className="mb-10">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">API Endpoints</h2>
          <div className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-100 text-sm">
            {[
              { method: "GET", path: "/api/emails", desc: "List emails with search" },
              { method: "GET", path: "/api/emails/:id", desc: "Read a single email" },
              { method: "POST", path: "/api/emails/send", desc: "Send an email" },
              { method: "POST", path: "/api/emails/draft", desc: "Save a draft" },
              { method: "GET", path: "/api/labels", desc: "List Gmail labels" },
              { method: "POST", path: "/api/emails/:id/labels", desc: "Modify email labels" },
              { method: "GET", path: "/api/chat", desc: "SSE stream — AI agent chat" },
            ].map((endpoint) => (
              <div key={endpoint.path + endpoint.method} className="flex items-center gap-3 px-4 py-2.5">
                <span className={`shrink-0 rounded px-2 py-0.5 text-xs font-bold ${endpoint.method === "GET" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                  {endpoint.method}
                </span>
                <code className="text-xs text-slate-700 font-medium">{endpoint.path}</code>
                <span className="text-slate-400">—</span>
                <span className="text-slate-500">{endpoint.desc}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-slate-200 pt-6 text-center text-sm text-slate-400">
          <p>Built with LangGraph, FastAPI, and Next.js</p>
        </footer>
      </div>
    </div>
  );
}
