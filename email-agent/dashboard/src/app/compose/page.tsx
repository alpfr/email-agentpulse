"use client";

import { useRouter } from "next/navigation";
import ComposeForm from "@/components/compose/ComposeForm";

export default function ComposePage() {
  const router = useRouter();

  return (
    <div id="main-content" className="h-full bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <h1 className="text-lg font-semibold text-slate-900">New Email</h1>
      </div>
      <div className="max-w-2xl mx-auto p-6">
        <ComposeForm onSuccess={() => router.push("/inbox")} />
      </div>
    </div>
  );
}
