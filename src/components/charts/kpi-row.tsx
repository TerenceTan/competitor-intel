"use client";

import { Building2, Activity, Star, Megaphone } from "lucide-react";
import { StatCard } from "./stat-card";

interface KpiRowProps {
  competitorCount: number;
  changesThisWeek: number;
  changesByDay: { value: number }[];
  avgTrustpilot: number | null;
  activePromos: number;
}

export function KpiRow({ competitorCount, changesThisWeek, changesByDay, avgTrustpilot, activePromos }: KpiRowProps) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard
        title="Competitors Tracked"
        value={competitorCount}
        icon={Building2}
      />
      <StatCard
        title="Changes This Week"
        value={changesThisWeek}
        icon={Activity}
        sparklineData={changesByDay}
        subtitle="Last 14 days"
      />
      <StatCard
        title="Avg Trustpilot"
        value={avgTrustpilot != null ? avgTrustpilot.toFixed(1) : "—"}
        icon={Star}
      />
      <StatCard
        title="Active Promos"
        value={activePromos}
        icon={Megaphone}
      />
    </div>
  );
}
