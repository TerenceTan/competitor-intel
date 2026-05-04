import type { LucideIcon } from "lucide-react";
import { AlertOctagon, AlertCircle, Inbox } from "lucide-react";
import { cn } from "@/lib/utils";

type EmptyStateReason = "scraper-failed" | "scraper-empty" | "no-activity" | undefined;

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  reason?: EmptyStateReason;
}

// Visual presets per reason. 'scraper-failed' uses the same red palette as
// stale-data-banner.tsx for cross-component consistency (PATTERNS.md visual ref):
// the dashboard already trains users that red == data trust problem.
const REASON_PRESETS: Record<NonNullable<EmptyStateReason>, { icon: LucideIcon; bg: string; iconColor: string }> = {
  "scraper-failed": { icon: AlertOctagon, bg: "bg-red-50 border-red-200", iconColor: "text-red-500" },
  "scraper-empty": { icon: AlertCircle, bg: "bg-amber-50 border-amber-200", iconColor: "text-amber-500" },
  "no-activity": { icon: Inbox, bg: "bg-white border-gray-200", iconColor: "text-gray-400" },
};

export function EmptyState({ icon: Icon, title, description, action, reason }: EmptyStateProps) {
  const preset = reason ? REASON_PRESETS[reason] : null;
  const ResolvedIcon = Icon ?? preset?.icon;

  return (
    <div className={cn("rounded-xl border p-10 text-center", preset?.bg ?? "bg-white border-gray-200")}>
      {ResolvedIcon && (
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-white">
          <ResolvedIcon className={cn("h-6 w-6", preset?.iconColor ?? "text-gray-400")} />
        </div>
      )}
      <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      {description && (
        <p className="mt-1 text-sm text-gray-500">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
