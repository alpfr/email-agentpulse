"use client";

import { useState } from "react";
import { ToolCall } from "@/types";
import { cn } from "@/lib/utils";
import Badge from "@/components/ui/Badge";

export default function ToolCallBadge({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="my-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-xs"
        aria-expanded={expanded}
        aria-label={`Tool ${toolCall.name} — ${toolCall.status}`}
      >
        <svg className={cn("h-3.5 w-3.5", toolCall.status === "pending" ? "text-amber-500 animate-spin" : "text-emerald-500")} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {toolCall.status === "pending" ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          )}
        </svg>
        <Badge color={toolCall.status === "pending" ? "yellow" : "green"}>
          {toolCall.name}
        </Badge>
        <svg className={cn("h-3 w-3 text-slate-400 transition-transform", expanded && "rotate-180")} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="mt-1 rounded-md bg-slate-800 p-2 text-xs text-slate-200 font-mono overflow-x-auto">
          <div className="text-slate-400 mb-1">Args:</div>
          <pre className="whitespace-pre-wrap">{JSON.stringify(toolCall.args, null, 2)}</pre>
          {toolCall.result && (
            <>
              <div className="text-slate-400 mt-2 mb-1">Result:</div>
              <pre className="whitespace-pre-wrap">{toolCall.result}</pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}
