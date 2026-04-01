"use client";

import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer } from "recharts";

interface ReputationRadarProps {
  trustpilot: number | null;
  myfxbook: number | null;
  ios: number | null;
  android: number | null;
  wikifx: number | null;
}

export function ReputationRadar({ trustpilot, myfxbook, ios, android, wikifx }: ReputationRadarProps) {
  // Normalize all scores to 0-10 scale
  const data = [
    { metric: "Trustpilot", value: trustpilot != null ? trustpilot * 2 : 0 },     // /5 → /10
    { metric: "MyFXBook", value: myfxbook ?? 0 },                                  // already /10
    { metric: "iOS", value: ios != null ? ios * 2 : 0 },                           // /5 → /10
    { metric: "Android", value: android != null ? android * 2 : 0 },               // /5 → /10
    { metric: "WikiFX", value: wikifx ?? 0 },                                       // already /10
  ];

  const hasData = data.some((d) => d.value > 0);
  if (!hasData) return null;

  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
          <PolarGrid stroke="#e5e7eb" />
          <PolarAngleAxis
            dataKey="metric"
            tick={{ fontSize: 14, fill: "#6b7280" }}
          />
          <Radar
            dataKey="value"
            stroke="oklch(0.511 0.262 264)"
            fill="oklch(0.511 0.262 264)"
            fillOpacity={0.15}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
