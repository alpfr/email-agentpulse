import { Email } from "@/types";
import { cn, formatDate, extractName } from "@/lib/utils";
import Avatar from "@/components/ui/Avatar";

interface EmailListItemProps {
  email: Email;
  isSelected: boolean;
  onClick: () => void;
}

export default function EmailListItem({ email, isSelected, onClick }: EmailListItemProps) {
  const senderName = extractName(email.from);

  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full items-start gap-3 px-4 py-3 text-left transition-colors border-b border-slate-100",
        isSelected
          ? "bg-primary-50 border-l-2 border-l-primary-500"
          : "hover:bg-slate-50",
        email.isUnread && !isSelected && "bg-white"
      )}
      aria-selected={isSelected}
      aria-label={`Email from ${senderName}: ${email.subject}`}
    >
      {/* Unread dot */}
      <div className="flex items-center pt-1.5">
        {email.isUnread ? (
          <span className="h-2 w-2 rounded-full bg-primary-500" aria-label="Unread" />
        ) : (
          <span className="h-2 w-2" />
        )}
      </div>

      <Avatar name={senderName} size="sm" />

      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className={cn("text-sm truncate", email.isUnread ? "font-semibold text-slate-900" : "font-medium text-slate-700")}>
            {senderName}
          </span>
          <span className="text-xs text-slate-400 shrink-0">
            {formatDate(email.date)}
          </span>
        </div>
        <p className={cn("text-sm truncate", email.isUnread ? "font-semibold text-slate-800" : "text-slate-600")}>
          {email.subject || "(no subject)"}
        </p>
        <p className="text-xs text-slate-400 truncate mt-0.5">
          {email.snippet}
        </p>
      </div>
    </button>
  );
}
