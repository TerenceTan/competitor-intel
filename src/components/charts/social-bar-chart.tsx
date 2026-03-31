"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface SocialBarChartProps {
  data: { platform: string; followers: number }[];
}

const COLORS = [
  "oklch(0.809 0.105 251.813)",  // chart-1
  "oklch(0.623 0.214 259.815)",  // chart-2
  "oklch(0.546 0.245 262.881)",  // chart-3
  "oklch(0.488 0.243 264.376)",  // chart-4
  "oklch(0.424 0.199 265.638)",  // chart-5
  "oklch(0.511 0.262 264)",      // primary
];

function formatFollowers(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return String(value);
}

export function SocialBarChart({ data }: SocialBarChartProps) {
  if (data.length === 0) return null;

  return (
    <div className="w-full h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 10, right: 30, top: 5, bottom: 5 }}>
          <XAxis
            type="number"
            tickFormatter={formatFollowers}
            tick={{ fontSize: 11, fill: "#9ca3af" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="platform"
            tick={{ fontSize: 12, fill: "#6b7280" }}
            axisLine={false}
            tickLine={false}
            width={80}
          />
          <Tooltip
            formatter={(value) => [Number(value).toLocaleString(), "Followers"]}
            contentStyle={{ borderRadius: "8px", border: "1px solid #e5e7eb", fontSize: "12px" }}
          />
          <Bar dataKey="followers" radius={[0, 4, 4, 0]} barSize={20}>
            {data.map((_, idx) => (
              <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
