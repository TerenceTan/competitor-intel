"use client";

import { useState } from "react";
import { timeAgo } from "@/lib/utils";
import { X } from "lucide-react";

interface Competitor {
  id: string;
  name: string;
  tier: number;
  website: string;
}

interface Insight {
  id: number;
  competitorId: string;
  generatedAt: string;
  summary: string | null;
  keyFindingsJson: string | null;
  implications: string | null;
  actionsJson: string | null;
}

interface KeyFinding {
  finding: string;
  severity: string;
}

function SeverityBadge({ severity }: { severity: string }) {
  const colorMap: Record<string, string> = {
    critical: "bg-red-50 text-red-700 border-red-200",
    high: "bg-orange-50 text-orange-700 border-orange-200",
    medium: "bg-amber-50 text-amber-700 border-amber-200",
    low: "bg-blue-50 text-blue-700 border-blue-200",
  };
  const cls =
    colorMap[severity?.toLowerCase()] ??
    "bg-gray-100 text-gray-600 border-gray-200";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}
    >
      {severity ?? "unknown"}
    </span>
  );
}

export function InsightModal({
  competitor,
  insight,
  keyFindings,
  children,
}: {
  competitor: Competitor;
  insight: Insight;
  keyFindings: KeyFinding[];
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);

  let actions: Array<{ action: string; urgency: string }> = [];
  try {
    actions = insight.actionsJson ? JSON.parse(insight.actionsJson) : [];
  } catch {}

  const urgencyColors: Record<string, string> = {
    high: "text-orange-600",
    medium: "text-amber-600",
    low: "text-blue-600",
  };

  return (
    <>
      <div onClick={() => setOpen(true)}>{children}</div>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ backgroundColor: "rgba(0,0,0,0.5)" }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpen(false);
          }}
        >
          <div
            className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-gray-200 bg-white shadow-xl"
          >
            {/* Modal header */}
            <div className="sticky top-0 flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
              <div>
                <h2 className="text-gray-900 font-bold text-lg">
                  {competitor.name}
                </h2>
                <p className="text-gray-500 text-xs">
                  AI analysis generated {timeAgo(insight.generatedAt)}
                </p>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="text-gray-400 hover:text-gray-700 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal body */}
            <div className="px-6 py-5 space-y-6">
              {/* Summary */}
              <div>
                <p className="text-gray-500 text-xs uppercase tracking-wider mb-2">
                  Summary
                </p>
                <p className="text-gray-700 text-sm leading-relaxed">
                  {insight.summary ?? "No summary available."}
                </p>
              </div>

              {/* Implications */}
              {insight.implications && (
                <div>
                  <p className="text-gray-500 text-xs uppercase tracking-wider mb-2">
                    Implications
                  </p>
                  <p className="text-gray-700 text-sm leading-relaxed">
                    {insight.implications}
                  </p>
                </div>
              )}

              {/* Key findings */}
              {keyFindings.length > 0 && (
                <div>
                  <p className="text-gray-500 text-xs uppercase tracking-wider mb-3">
                    Key Findings
                  </p>
                  <div className="space-y-2">
                    {keyFindings.map((f, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 p-3 rounded-lg bg-gray-50"
                      >
                        <SeverityBadge severity={f.severity} />
                        <p className="text-gray-700 text-sm flex-1">
                          {f.finding}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Actions */}
              {actions.length > 0 && (
                <div>
                  <p className="text-gray-500 text-xs uppercase tracking-wider mb-3">
                    Recommended Actions
                  </p>
                  <div className="space-y-2">
                    {actions.map((a, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 p-3 rounded-lg bg-gray-50"
                      >
                        <span
                          className={`text-xs font-semibold uppercase tracking-wider mt-0.5 ${
                            urgencyColors[a.urgency?.toLowerCase()] ??
                            "text-gray-500"
                          }`}
                        >
                          {a.urgency}
                        </span>
                        <p className="text-gray-700 text-sm flex-1">
                          {a.action}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
