"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { Email } from "@/types";

export function useEmails(query: string) {
  const [emails, setEmails] = useState<Email[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEmails = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listEmails(query);
      setEmails(data.emails);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch emails");
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    fetchEmails();
  }, [fetchEmails]);

  return { emails, loading, error, refetch: fetchEmails };
}
