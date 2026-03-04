"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import EmailList from "@/components/inbox/EmailList";
import EmailDetail from "@/components/inbox/EmailDetail";
import ComposeModal from "@/components/compose/ComposeModal";
import { cn } from "@/lib/utils";
import Spinner from "@/components/ui/Spinner";

function InboxContent() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") || "in:inbox";

  const [query, setQuery] = useState(initialQuery);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [replyData, setReplyData] = useState<{ messageId: string; to: string; subject: string } | null>(null);

  return (
    <div id="main-content" className="flex h-full">
      {/* Email list */}
      <div className={cn(
        "w-full lg:w-[380px] shrink-0 border-r border-slate-200",
        selectedId ? "hidden lg:block" : "block"
      )}>
        <EmailList
          query={query}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onQueryChange={setQuery}
        />
      </div>

      {/* Email detail */}
      <div className={cn(
        "flex-1 bg-white min-w-0",
        selectedId ? "block" : "hidden lg:block"
      )}>
        <EmailDetail
          messageId={selectedId}
          onReply={(data) => setReplyData(data)}
          onBack={() => setSelectedId(null)}
        />
      </div>

      {/* Reply modal */}
      <ComposeModal
        open={!!replyData}
        onClose={() => setReplyData(null)}
        replyTo={replyData || undefined}
      />
    </div>
  );
}

export default function InboxPage() {
  return (
    <Suspense fallback={<div className="flex h-full items-center justify-center"><Spinner size="lg" /></div>}>
      <InboxContent />
    </Suspense>
  );
}
