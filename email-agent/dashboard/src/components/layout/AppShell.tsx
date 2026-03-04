"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import MobileNav from "./MobileNav";
import ChatPanel from "@/components/chat/ChatPanel";
import ComposeModal from "@/components/compose/ComposeModal";
import { cn } from "@/lib/utils";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [chatOpen, setChatOpen] = useState(true);
  const [composeOpen, setComposeOpen] = useState(false);

  // Hide sidebar chat panel when the main content is already the chat page
  const hideSidebarChat = pathname === "/chat";

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* Sidebar — desktop only */}
      <aside className="hidden lg:flex lg:w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
        <Sidebar onCompose={() => setComposeOpen(true)} />
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0 pb-14 lg:pb-0">
        {children}
      </main>

      {/* Chat panel — desktop only, hidden on /chat route */}
      {!hideSidebarChat && (
        <aside
          className={cn(
            "hidden lg:flex flex-col border-l border-slate-200 bg-white transition-all duration-200 shrink-0",
            chatOpen ? "w-[380px]" : "w-12"
          )}
        >
          <ChatPanel
            collapsed={!chatOpen}
            onToggle={() => setChatOpen(!chatOpen)}
          />
        </aside>
      )}

      {/* Mobile bottom nav */}
      <MobileNav />

      {/* Compose modal */}
      <ComposeModal open={composeOpen} onClose={() => setComposeOpen(false)} />
    </div>
  );
}
