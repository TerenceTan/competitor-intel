"use client";

import { Card } from "@/components/ui/card";
import { AreaChart, Area, ResponsiveContainer } from "recharts";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  sparklineData?: { value: number }[];
  subtitle?: string;
  delta?: { value: number; label: string };
  iconBgClassName?: string;
  iconClassName?: string;
}

export function StatCard({ title, value, icon: Icon, sparklineData, subtitle, delta, iconBgClassName, iconClassName }: StatCardProps) {
  return (
    <Card className="p-5 border-gray-200 bg-white hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1.5">{value}</p>
          {delta && (
            <p className={`text-xs font-medium mt-1 flex items-center gap-1 ${delta.value > 0 ? "text-emerald-600" : delta.value < 0 ? "text-red-600" : "text-gray-500"}`}>
              <span>{delta.value > 0 ? "▲" : delta.value < 0 ? "▼" : "—"}</span>
              <span>{delta.value > 0 ? "+" : ""}{delta.value}</span>
              <span className="text-gray-400 font-normal">{delta.label}</span>
            </p>
          )}
          {subtitle && !delta && (
            <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${iconBgClassName ?? "bg-primary/10"}`}>
            <Icon className={`w-[18px] h-[18px] ${iconClassName ?? "text-primary"}`} />
          </div>
          {sparklineData && sparklineData.length > 1 && (
            <div className="w-20 h-8">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={sparklineData}>
                  <defs>
                    <linearGradient id="sparkGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="oklch(0.511 0.262 264)" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="oklch(0.511 0.262 264)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="oklch(0.511 0.262 264)"
                    strokeWidth={1.5}
                    fill="url(#sparkGradient)"
                    dot={false}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
