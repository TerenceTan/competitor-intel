import { AlertTriangle, AlertCircle, Info, Circle } from "lucide-react";
import { cn } from "@/lib/utils";

const config: Record<string, { classes: string; Icon: typeof AlertCircle }> = {
  critical: { classes: "bg-red-50 text-red-700 border-red-200", Icon: AlertTriangle },
  high:     { classes: "bg-orange-50 text-orange-700 border-orange-200", Icon: AlertCircle },
  medium:   { classes: "bg-amber-50 text-amber-700 border-amber-200", Icon: Info },
  low:      { classes: "bg-blue-50 text-blue-700 border-blue-200", Icon: Circle },
};

const fallback = { classes: "bg-gray-100 text-gray-600 border-gray-200", Icon: Circle };

export function SeverityBadge({ severity }: { severity: string | null | undefined }) {
  const key = severity?.toLowerCase() ?? "";
  const { classes, Icon } = config[key] ?? fallback;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border",
        classes,
      )}
    >
      <Icon className="w-3 h-3" />
      {severity ?? "unknown"}
    </span>
  );
}
