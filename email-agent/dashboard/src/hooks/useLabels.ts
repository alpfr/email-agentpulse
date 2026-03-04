"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Label } from "@/types";

export function useLabels() {
  const [labels, setLabels] = useState<Label[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listLabels()
      .then((data) => setLabels(data.labels))
      .catch(() => setLabels([]))
      .finally(() => setLoading(false));
  }, []);

  return { labels, loading };
}
