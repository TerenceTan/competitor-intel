"use client";

import { Card } from "@/components/ui/card";
import { AlertTriangle, AlertCircle, Info, Circle } from "lucide-react";

const config = [
  { key: "critical", label: "Critical", Icon: AlertTriangle, iconBg: "bg-red-100", iconColor: "text-red-600" },
  { key: "high", label: "High", Icon: AlertCircle, iconBg: "bg-orange-100", iconColor: "text-orange-600" },
  { key: "medium", label: "Medium", Icon: Info, iconBg: "bg-amber-100", iconColor: "text-amber-600" },
  { key: "low", label: "Low", Icon: Circle, iconBg: "bg-blue-100", iconColor: "text-blue-500" },
] as const;

export function SeverityCards({ counts }: { counts: Record<string, number> }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {config.map(({ key, label, Icon, iconBg, iconColor }) => (
        <Card key={key} className="p-5 border-gray-200 bg-white hover:shadow-sm transition-shadow">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">{label}</p>
              <p className="text-2xl font-bold text-gray-900 mt-1.5">{counts[key] ?? 0}</p>
            </div>
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${iconBg}`}>
              <Icon className={`w-[18px] h-[18px] ${iconColor}`} />
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
