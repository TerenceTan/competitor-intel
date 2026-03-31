"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface DayData {
  day: string;
  count: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

interface ChangesTimelineProps {
  data: DayData[];
}

export function ChangesTimeline({ data }: ChangesTimelineProps) {
  if (data.length === 0) return null;

  return (
    <div className="w-full h-48">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ left: 0, right: 0, top: 5, bottom: 5 }}>
          <XAxis
            dataKey="day"
            tickFormatter={(d: string) => {
              const date = new Date(d + "T00:00:00");
              return `${date.getMonth() + 1}/${date.getDate()}`;
            }}
            tick={{ fontSize: 10, fill: "#9ca3af" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 10, fill: "#9ca3af" }}
            axisLine={false}
            tickLine={false}
            width={30}
          />
          <Tooltip
            labelFormatter={(d) => {
              const date = new Date(String(d) + "T00:00:00");
              return date.toLocaleDateString("en-AU", { month: "short", day: "numeric" });
            }}
            contentStyle={{ borderRadius: "8px", border: "1px solid #e5e7eb", fontSize: "12px" }}
          />
          <Bar dataKey="count" radius={[3, 3, 0, 0]} barSize={16}>
            {data.map((entry, idx) => {
              const color = entry.critical > 0
                ? "#ef4444"
                : entry.high > 0
                ? "#f97316"
                : entry.medium > 0
                ? "#f59e0b"
                : "#3b82f6";
              return <Cell key={idx} fill={color} fillOpacity={0.8} />;
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
