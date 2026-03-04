"use client";

import { useState } from "react";
import { useEmails } from "@/hooks/useEmails";
import EmailListItem from "./EmailListItem";
import EmailListSkeleton from "./EmailListSkeleton";

interface EmailListProps {
  query: string;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onQueryChange: (q: string) => void;
}

export default function EmailList({ query, selectedId, onSelect, onQueryChange }: EmailListProps) {
  const { emails, loading, error, refetch } = useEmails(query);
  const [search, setSearch] = useState("");

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (search.trim()) {
      onQueryChange(search.trim());
    }
  };

  return (
    <div className="flex h-full flex-col bg-white">
      {/* Header */}
      <div className="border-b border-slate-200 px-4 py-3">
        <div className="flex items-center justify-between mb-3">
          <h1 className="text-lg font-semibold text-slate-900">Inbox</h1>
          <button
            onClick={refetch}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
            aria-label="Refresh emails"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSearch} className="relative">
          <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search emails..."
            className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
            aria-label="Search emails"
          />
        </form>
      </div>

      {/* Email list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {loading ? (
          <EmailListSkeleton />
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <p className="text-sm text-red-600">{error}</p>
            <button onClick={refetch} className="mt-2 text-sm text-primary-600 hover:text-primary-700">
              Try again
            </button>
          </div>
        ) : emails.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center text-slate-400">
            <svg className="h-10 w-10 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
            </svg>
            <p className="text-sm">No emails found</p>
          </div>
        ) : (
          <ul role="list" aria-label="Email messages">
            {emails.map((email) => (
              <li key={email.id} role="listitem">
                <EmailListItem
                  email={email}
                  isSelected={selectedId === email.id}
                  onClick={() => onSelect(email.id)}
                />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
