"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import Input from "@/components/ui/Input";
import Textarea from "@/components/ui/Textarea";
import Button from "@/components/ui/Button";

interface ComposeFormProps {
  replyTo?: { messageId: string; to: string; subject: string };
  onSuccess?: () => void;
}

export default function ComposeForm({ replyTo, onSuccess }: ComposeFormProps) {
  const [to, setTo] = useState(replyTo?.to || "");
  const [subject, setSubject] = useState(replyTo ? `Re: ${replyTo.subject}` : "");
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleSubmit = async (action: "send" | "draft") => {
    if (!to.trim() || !subject.trim()) {
      setError("To and Subject are required");
      return;
    }

    setSending(true);
    setError(null);
    setSuccess(null);

    try {
      const data = {
        to: to.trim(),
        subject: subject.trim(),
        body: body.trim(),
        reply_to_message_id: replyTo?.messageId,
      };

      if (action === "send") {
        await api.sendEmail(data);
        setSuccess("Email sent successfully");
      } else {
        await api.draftEmail(data);
        setSuccess("Draft saved successfully");
      }

      setTimeout(() => {
        onSuccess?.();
      }, 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send");
    } finally {
      setSending(false);
    }
  };

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); handleSubmit("send"); }}
      className="flex flex-col gap-4"
      aria-label="Email compose form"
    >
      <Input
        label="To"
        type="email"
        value={to}
        onChange={(e) => setTo(e.target.value)}
        placeholder="recipient@example.com"
        required
        aria-required="true"
        disabled={sending}
      />

      <Input
        label="Subject"
        value={subject}
        onChange={(e) => setSubject(e.target.value)}
        placeholder="Email subject"
        required
        aria-required="true"
        disabled={sending}
      />

      <Textarea
        label="Message"
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Write your message..."
        rows={8}
        disabled={sending}
      />

      {error && (
        <p className="text-sm text-red-600" role="alert">{error}</p>
      )}

      {success && (
        <p className="text-sm text-emerald-600" role="status">{success}</p>
      )}

      <div className="flex gap-3 justify-end">
        <Button
          type="button"
          variant="secondary"
          onClick={() => handleSubmit("draft")}
          disabled={sending}
        >
          Save Draft
        </Button>
        <Button type="submit" disabled={sending}>
          {sending ? "Sending..." : "Send"}
        </Button>
      </div>
    </form>
  );
}
