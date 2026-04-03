"use client";

import { Card } from "@/components/ui/card";

interface HeatmapCell {
  competitorId: string;
  competitorName: string;
  domain: string;
  count: number;
  maxSeverity: string;
}

interface ActivityHeatmapProps {
  data: HeatmapCell[];
  competitors: { id: string; name: string }[];
  domains: string[];
}

function cellBg(count: number, maxSeverity: string): string {
  if (count === 0) return "bg-gray-50";
  const sev = maxSeverity || "low";
  if (sev === "critical") {
    return count >= 3 ? "bg-red-400" : count >= 2 ? "bg-red-300" : "bg-red-200";
  }
  if (sev === "high") {
    return count >= 3 ? "bg-orange-300" : count >= 2 ? "bg-orange-200" : "bg-orange-100";
  }
  if (sev === "medium") {
    return count >= 3 ? "bg-amber-300" : count >= 2 ? "bg-amber-200" : "bg-amber-100";
  }
  return count >= 3 ? "bg-blue-200" : count >= 2 ? "bg-blue-100" : "bg-blue-50";
}

function cellText(count: number, maxSeverity: string): string {
  if (count === 0) return "text-gray-300";
  const sev = maxSeverity || "low";
  if (sev === "critical") return "text-red-900";
  if (sev === "high") return "text-orange-900";
  if (sev === "medium") return "text-amber-900";
  return "text-blue-900";
}

const domainLabels: Record<string, string> = {
  pricing: "Pricing",
  reputation: "Reputation",
  social: "Social",
  promotions: "Promos",
  news: "News",
  account_types: "Accounts",
  wikifx: "WikiFX",
};

export function ActivityHeatmap({ data, competitors, domains }: ActivityHeatmapProps) {
  // Build lookup: competitorId-domain -> cell
  const cellMap = new Map<string, HeatmapCell>();
  for (const cell of data) {
    cellMap.set(`${cell.competitorId}-${cell.domain}`, cell);
  }

  if (!competitors.length || !domains.length) return null;

  return (
    <Card className="p-5 border-gray-200 bg-white overflow-x-auto relative">
      <div className="min-w-[500px]">
        {/* Header row */}
        <div
          className="grid gap-1 mb-1"
          style={{ gridTemplateColumns: `120px repeat(${domains.length}, 1fr)` }}
        >
          <div />
          {domains.map((d) => (
            <div
              key={d}
              className="text-xs text-gray-500 font-medium text-center uppercase tracking-wider px-1 truncate"
            >
              {domainLabels[d] || d}
            </div>
          ))}
        </div>

        {/* Data rows */}
        {competitors.map((comp) => (
          <div
            key={comp.id}
            className="grid gap-1 mb-1"
            style={{ gridTemplateColumns: `120px repeat(${domains.length}, 1fr)` }}
          >
            <div className="text-xs text-gray-700 font-medium truncate flex items-center pr-2">
              {comp.name}
            </div>
            {domains.map((domain) => {
              const cell = cellMap.get(`${comp.id}-${domain}`);
              const count = cell?.count ?? 0;
              const sev = cell?.maxSeverity ?? "low";
              return (
                <div
                  key={domain}
                  className={`rounded h-8 flex items-center justify-center cursor-default transition-colors ${cellBg(count, sev)}`}
                  title={count > 0 ? `${count} change${count !== 1 ? "s" : ""} (${sev})` : "No changes"}
                >
                  {count > 0 && (
                    <span className={`text-xs font-semibold ${cellText(count, sev)}`}>
                      {count}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-3 pt-3 border-t border-gray-100">
        <span className="text-xs text-gray-400">Severity:</span>
        {[
          { label: "Critical", color: "bg-red-300" },
          { label: "High", color: "bg-orange-200" },
          { label: "Medium", color: "bg-amber-200" },
          { label: "Low", color: "bg-blue-100" },
        ].map((s) => (
          <div key={s.label} className="flex items-center gap-1">
            <div className={`w-3 h-3 rounded ${s.color}`} />
            <span className="text-xs text-gray-500">{s.label}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
