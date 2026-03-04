import { cn } from "@/lib/utils";

const colorMap: Record<string, string> = {
  blue: "bg-blue-100 text-blue-700",
  green: "bg-emerald-100 text-emerald-700",
  yellow: "bg-amber-100 text-amber-700",
  red: "bg-red-100 text-red-700",
  gray: "bg-slate-100 text-slate-600",
  purple: "bg-violet-100 text-violet-700",
};

interface BadgeProps {
  children: React.ReactNode;
  color?: keyof typeof colorMap;
  className?: string;
}

export default function Badge({ children, color = "gray", className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        colorMap[color],
        className
      )}
    >
      {children}
    </span>
  );
}
