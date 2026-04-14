"use client";

import { Shield, AlertTriangle, Megaphone, Share2 } from "lucide-react";
import { StatCard } from "./stat-card";

interface KpiRowProps {
  trustpilot: { ours: number | null; fieldAvg: number | null };
  highSeverityChanges: { count: number; prevCount: number };
  changesByDay: { value: number }[];
  promosPressure: { count: number; prevCount: number };
  socialShareOfVoice: number | null; // percentage 0-100
  trustpilotSparkline?: { value: number }[];
  promoSparkline?: { value: number }[];
  socialSparkline?: { value: number }[];
}

export function KpiRow({
  trustpilot,
  highSeverityChanges,
  changesByDay,
  promosPressure,
  socialShareOfVoice,
  trustpilotSparkline,
  promoSparkline,
  socialSparkline,
}: KpiRowProps) {
  const tpDelta =
    trustpilot.ours != null && trustpilot.fieldAvg != null
      ? +(trustpilot.ours - trustpilot.fieldAvg).toFixed(1)
      : null;

  const changeDelta = highSeverityChanges.count - highSeverityChanges.prevCount;
  const promoDelta = promosPressure.count - promosPressure.prevCount;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard
        title="Our Trustpilot vs Field"
        value={trustpilot.ours != null ? trustpilot.ours.toFixed(1) : "—"}
        icon={Shield}
        sparklineData={trustpilotSparkline}
        subtitle={trustpilot.fieldAvg != null ? `Field avg: ${trustpilot.fieldAvg.toFixed(1)}` : undefined}
        delta={tpDelta != null ? { value: tpDelta, label: "vs avg" } : undefined}
        iconBgClassName={tpDelta != null && tpDelta >= 0 ? "bg-emerald-50" : "bg-red-50"}
        iconClassName={tpDelta != null && tpDelta >= 0 ? "text-emerald-600" : "text-red-600"}
      />
      <StatCard
        title="High-Severity Changes"
        value={highSeverityChanges.count}
        icon={AlertTriangle}
        sparklineData={changesByDay}
        delta={{ value: changeDelta, label: "vs last week" }}
        iconBgClassName="bg-orange-50"
        iconClassName="text-orange-600"
      />
      <StatCard
        title="Competitor Promos"
        value={promosPressure.count}
        icon={Megaphone}
        sparklineData={promoSparkline}
        delta={{ value: promoDelta, label: "vs last week" }}
        iconBgClassName="bg-amber-50"
        iconClassName="text-amber-600"
      />
      <StatCard
        title="Social Share of Voice"
        value={socialShareOfVoice != null ? `${socialShareOfVoice}%` : "—"}
        icon={Share2}
        sparklineData={socialSparkline}
        subtitle="Pepperstone % of total followers"
        iconBgClassName="bg-blue-50"
        iconClassName="text-blue-600"
      />
    </div>
  );
}
