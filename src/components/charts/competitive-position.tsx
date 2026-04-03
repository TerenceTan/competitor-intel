"use client";

import { Card } from "@/components/ui/card";

interface RankDimension {
  label: string;
  rank: number;
  total: number;
}

interface CompetitivePositionProps {
  dimensions: RankDimension[];
}

function rankColor(rank: number, total: number): string {
  const pct = rank / total;
  if (pct <= 0.3) return "text-emerald-700 bg-emerald-50 border-emerald-200";
  if (pct <= 0.6) return "text-amber-700 bg-amber-50 border-amber-200";
  return "text-red-700 bg-red-50 border-red-200";
}

function rankDotColor(rank: number, total: number): string {
  const pct = rank / total;
  if (pct <= 0.3) return "bg-emerald-400";
  if (pct <= 0.6) return "bg-amber-400";
  return "bg-red-400";
}

export function CompetitivePosition({ dimensions }: CompetitivePositionProps) {
  if (!dimensions.length) return null;

  return (
    <Card className="p-5 border-gray-200 bg-white">
      <p className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-4">
        Pepperstone Competitive Position
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {dimensions.map((d) => (
          <div
            key={d.label}
            className={`flex flex-col items-center gap-1.5 rounded-lg border px-3 py-3 ${rankColor(d.rank, d.total)}`}
          >
            <span className="text-2xl font-bold">#{d.rank}</span>
            <span className="text-xs font-medium text-center leading-tight">{d.label}</span>
            <div className="flex gap-0.5 mt-1">
              {Array.from({ length: d.total }, (_, i) => (
                <div
                  key={i}
                  className={`w-1.5 h-1.5 rounded-full ${i < d.rank ? rankDotColor(d.rank, d.total) : "bg-gray-200"}`}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
