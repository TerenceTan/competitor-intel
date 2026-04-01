"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

interface DonutSegment {
  label: string;
  count: number;
  color: string;
}

interface SeverityDonutProps {
  data: DonutSegment[];
  centerLabel: string;
  centerValue: number;
}

export function SeverityDonut({ data, centerLabel, centerValue }: SeverityDonutProps) {
  const filtered = data.filter((d) => d.count > 0);

  if (filtered.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-gray-400">
        No data
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-44 h-44">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={filtered}
              dataKey="count"
              nameKey="label"
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={72}
              paddingAngle={3}
              strokeWidth={0}
            >
              {filtered.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{ fontSize: 14, borderRadius: 8, border: "1px solid #e5e7eb" }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-2xl font-bold text-gray-900">{centerValue}</span>
          <span className="text-xs text-gray-400 uppercase tracking-wider">{centerLabel}</span>
        </div>
      </div>
      <div className="flex items-center gap-3 flex-wrap justify-center">
        {filtered.map((d) => (
          <span key={d.label} className="flex items-center gap-1.5 text-xs text-gray-600">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: d.color }} />
            {d.label} ({d.count})
          </span>
        ))}
      </div>
    </div>
  );
}
