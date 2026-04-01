"use client";

import { useState } from "react";
import { AlertTriangle, AlertCircle, Info, Circle, ChevronDown } from "lucide-react";

const iconMap: Record<string, { Icon: typeof AlertCircle; color: string; bg: string }> = {
  critical: { Icon: AlertTriangle, color: "text-red-600", bg: "bg-red-100" },
  high: { Icon: AlertCircle, color: "text-orange-600", bg: "bg-orange-100" },
  medium: { Icon: Info, color: "text-amber-600", bg: "bg-amber-100" },
  low: { Icon: Circle, color: "text-blue-500", bg: "bg-blue-100" },
};

const fallbackIcon = { Icon: Circle, color: "text-gray-500", bg: "bg-gray-100" };

const borderColors: Record<string, string> = {
  critical: "border-l-red-400",
  high: "border-l-orange-400",
  medium: "border-l-amber-400",
  low: "border-l-blue-400",
};

export function FindingRow({
  finding,
  severity,
  evidence,
}: {
  finding: string;
  severity: string;
  evidence?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const sev = severity?.toLowerCase() ?? "low";
  const { Icon, color, bg } = iconMap[sev] ?? fallbackIcon;
  const border = borderColors[sev] ?? "border-l-gray-300";

  return (
    <div className={`border-l-[3px] ${border} rounded-r-lg`}>
      <button
        type="button"
        onClick={() => evidence && setExpanded(!expanded)}
        className={`flex items-start gap-3 w-full px-3.5 py-3 text-left ${evidence ? "cursor-pointer hover:bg-gray-50" : "cursor-default"} transition-colors`}
      >
        <span className={`flex items-center justify-center w-6 h-6 rounded-full ${bg} shrink-0`}>
          <Icon className={`w-3.5 h-3.5 ${color}`} />
        </span>
        <span className="text-sm text-gray-700 flex-1 line-clamp-2">{finding}</span>
        {evidence && (
          <ChevronDown
            className={`w-4 h-4 text-gray-400 shrink-0 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
          />
        )}
      </button>
      {expanded && evidence && (
        <div className="px-3.5 pb-3 pl-12">
          <p className="text-sm text-gray-500 italic leading-relaxed">{evidence}</p>
        </div>
      )}
    </div>
  );
}
