"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { EmailDetail } from "@/types";

export function useEmail(messageId: string | null) {
  const [email, setEmail] = useState<EmailDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!messageId) {
      setEmail(null);
      return;
    }

    setLoading(true);
    setError(null);

    api
      .readEmail(messageId)
      .then(setEmail)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to read email"))
      .finally(() => setLoading(false));
  }, [messageId]);

  return { email, loading, error };
}
