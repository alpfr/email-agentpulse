"use client";

import { useEmail } from "@/hooks/useEmail";
import { extractName, formatDate } from "@/lib/utils";
import Avatar from "@/components/ui/Avatar";
import Button from "@/components/ui/Button";
import Spinner from "@/components/ui/Spinner";
import Badge from "@/components/ui/Badge";

interface EmailDetailProps {
  messageId: string | null;
  onReply?: (data: { messageId: string; to: string; subject: string }) => void;
  onBack?: () => void;
}

export default function EmailDetail({ messageId, onReply, onBack }: EmailDetailProps) {
  const { email, loading, error } = useEmail(messageId);

  if (!messageId) {
    return (
      <div className="flex h-full items-center justify-center text-slate-400">
        <div className="text-center">
          <svg className="mx-auto h-12 w-12 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <p className="text-sm">Select an email to read</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !email) {
    return (
      <div className="flex h-full items-center justify-center text-red-600">
        <p className="text-sm">{error || "Email not found"}</p>
      </div>
    );
  }

  const senderName = extractName(email.from);

  return (
    <article aria-label={`Email: ${email.subject}`} className="flex h-full flex-col">
      {/* Mobile back button */}
      {onBack && (
        <button
          onClick={onBack}
          className="flex items-center gap-1 px-4 py-2 text-sm text-primary-600 hover:bg-slate-50 lg:hidden"
          aria-label="Back to email list"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>
      )}

      {/* Header */}
      <header className="border-b border-slate-200 px-6 py-4">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">
          {email.subject || "(no subject)"}
        </h2>

        <div className="flex items-start gap-3">
          <Avatar name={senderName} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium text-slate-900">{senderName}</p>
              <time className="text-xs text-slate-400 shrink-0">{formatDate(email.date)}</time>
            </div>
            <p className="text-xs text-slate-500 truncate">{email.from}</p>
            <p className="text-xs text-slate-400 mt-0.5">To: {email.to}</p>
          </div>
        </div>

        {/* Labels */}
        {email.labelIds.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {email.labelIds.map((label) => (
              <Badge key={label} color="blue">{label}</Badge>
            ))}
          </div>
        )}
      </header>

      {/* Body */}
      <div role="document" aria-label="Email body" className="flex-1 overflow-y-auto px-6 py-4 custom-scrollbar">
        <div className="prose prose-sm prose-slate max-w-none">
          <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700 leading-relaxed">
            {email.body}
          </pre>
        </div>
      </div>

      {/* Actions */}
      <div className="border-t border-slate-200 px-6 py-3 flex gap-3">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onReply?.({ messageId: email.id, to: email.from, subject: email.subject })}
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
          </svg>
          Reply
        </Button>
        <Button variant="ghost" size="sm">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
          </svg>
          Forward
        </Button>
      </div>
    </article>
  );
}
