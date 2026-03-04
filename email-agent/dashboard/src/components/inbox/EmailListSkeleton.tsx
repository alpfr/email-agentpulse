export default function EmailListSkeleton() {
  return (
    <div role="status" aria-label="Loading emails" className="animate-pulse">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex items-start gap-3 px-4 py-3 border-b border-slate-100">
          <div className="h-2 w-2 mt-1.5 rounded-full bg-slate-200" />
          <div className="h-8 w-8 rounded-full bg-slate-200 shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="flex justify-between">
              <div className="h-3.5 w-24 rounded bg-slate-200" />
              <div className="h-3 w-12 rounded bg-slate-200" />
            </div>
            <div className="h-3.5 w-48 rounded bg-slate-200" />
            <div className="h-3 w-64 rounded bg-slate-100" />
          </div>
        </div>
      ))}
      <span className="sr-only">Loading...</span>
    </div>
  );
}
