"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface LeaderboardEntry {
  name: string;
  score: number;
  isSelf: boolean;
}

interface ReputationLeaderboardProps {
  data: LeaderboardEntry[];
}

export function ReputationLeaderboard({ data }: ReputationLeaderboardProps) {
  if (!data.length) return null;

  // Sort descending by score
  const sorted = [...data].sort((a, b) => b.score - a.score);

  return (
    <div className="w-full" style={{ height: Math.max(200, sorted.length * 36 + 40) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={sorted} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 0 }}>
          <XAxis
            type="number"
            domain={[0, 5]}
            ticks={[0, 1, 2, 3, 4, 5]}
            tick={{ fontSize: 12, fill: "#9ca3af" }}
            axisLine={{ stroke: "#e5e7eb" }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={100}
            tick={{ fontSize: 12, fill: "#6b7280" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{ fontSize: 14, borderRadius: 8 }}
          />
          <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={20}>
            {sorted.map((entry, idx) => (
              <Cell
                key={idx}
                fill={entry.isSelf ? "oklch(0.511 0.262 264)" : "#d1d5db"}
                fillOpacity={entry.isSelf ? 1 : 0.7}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
