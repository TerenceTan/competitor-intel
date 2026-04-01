"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { timeAgo } from "@/lib/utils";
import { X } from "lucide-react";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { safeParseJson } from "@/lib/utils";

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

const severityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

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
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const actions = safeParseJson<Array<{ action: string; urgency: string }>>(insight.actionsJson, [], "actionsJson");

  const sortedFindings = [...keyFindings].sort(
    (a, b) => (severityOrder[a.severity?.toLowerCase()] ?? 4) - (severityOrder[b.severity?.toLowerCase()] ?? 4)
  );

  const handleEscape = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") setOpen(false);
  }, []);

  useEffect(() => {
    if (open) {
      document.addEventListener("keydown", handleEscape);
      closeButtonRef.current?.focus();
      return () => document.removeEventListener("keydown", handleEscape);
    }
  }, [open, handleEscape]);

  const borderColors: Record<string, string> = {
    critical: "border-l-red-400",
    high: "border-l-orange-400",
    medium: "border-l-amber-400",
    low: "border-l-blue-400",
  };

  const bgColors: Record<string, string> = {
    critical: "bg-red-50/50",
    high: "bg-orange-50/40",
    medium: "bg-amber-50/30",
    low: "bg-white",
  };

  const urgencyPill: Record<string, string> = {
    high: "bg-orange-100 text-orange-700",
    medium: "bg-amber-100 text-amber-700",
    low: "bg-blue-100 text-blue-700",
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-left w-full"
        aria-haspopup="dialog"
      >
        {children}
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`AI insight for ${competitor.name}`}
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ backgroundColor: "rgba(0,0,0,0.5)" }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpen(false);
          }}
        >
          <div
            className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-gray-200 bg-white shadow-xl animate-in fade-in zoom-in-95 duration-200"
          >
            {/* Modal header */}
            <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white rounded-t-2xl">
              <div>
                <h2 className="text-gray-900 font-bold text-lg">
                  {competitor.name}
                </h2>
                <p className="text-gray-400 text-xs">
                  Generated {timeAgo(insight.generatedAt)}
                </p>
              </div>
              <button
                ref={closeButtonRef}
                onClick={() => setOpen(false)}
                className="text-gray-400 hover:text-gray-700 transition-colors p-1 rounded-lg hover:bg-gray-100"
                aria-label="Close dialog"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal body */}
            <div className="px-6 py-5 space-y-6">
              {/* Severity counts bar */}
              {keyFindings.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  {(["critical", "high", "medium", "low"] as const).map((sev) => {
                    const count = keyFindings.filter((f) => f.severity?.toLowerCase() === sev).length;
                    if (count === 0) return null;
                    const colors: Record<string, string> = {
                      critical: "bg-red-50 text-red-700 border-red-200",
                      high: "bg-orange-50 text-orange-700 border-orange-200",
                      medium: "bg-amber-50 text-amber-700 border-amber-200",
                      low: "bg-blue-50 text-blue-700 border-blue-200",
                    };
                    return (
                      <span key={sev} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${colors[sev]}`}>
                        <span className="font-bold">{count}</span> {sev}
                      </span>
                    );
                  })}
                </div>
              )}

              {/* Summary */}
              <div>
                <p className="text-gray-500 text-xs font-medium uppercase tracking-wider mb-2">
                  Summary
                </p>
                <p className="text-gray-700 text-sm leading-relaxed">
                  {insight.summary ?? "No summary available."}
                </p>
              </div>

              {/* Implications — highlighted callout */}
              {insight.implications && (
                <div className="p-3.5 rounded-lg bg-primary/5 border border-primary/15">
                  <p className="text-primary text-xs font-semibold uppercase tracking-wider mb-1.5">
                    Implications for Pepperstone
                  </p>
                  <p className="text-gray-700 text-sm leading-relaxed">
                    {insight.implications}
                  </p>
                </div>
              )}

              {/* Key findings — severity-sorted with colored borders */}
              {sortedFindings.length > 0 && (
                <div>
                  <p className="text-gray-500 text-xs font-medium uppercase tracking-wider mb-3">
                    Key Findings
                  </p>
                  <div className="space-y-2.5">
                    {sortedFindings.map((f, i) => {
                      const sev = f.severity?.toLowerCase() ?? "low";
                      return (
                        <div
                          key={`finding-${i}-${f.severity}`}
                          className={`flex items-start gap-3 p-3.5 rounded-lg border border-gray-100 border-l-[3px] ${borderColors[sev] ?? "border-l-gray-300"} ${bgColors[sev] ?? "bg-white"}`}
                        >
                          <SeverityBadge severity={f.severity} />
                          <p className="text-gray-700 text-sm flex-1 leading-relaxed">
                            {f.finding}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Actions — numbered with urgency pills */}
              {actions.length > 0 && (
                <div>
                  <p className="text-gray-500 text-xs font-medium uppercase tracking-wider mb-3">
                    Recommended Actions
                  </p>
                  <div className="space-y-2.5">
                    {actions.map((a, i) => {
                      const pillCls = urgencyPill[a.urgency?.toLowerCase()] ?? "bg-gray-100 text-gray-600";
                      return (
                        <div
                          key={`action-${i}-${a.urgency}`}
                          className="flex items-start gap-3 p-3.5 rounded-lg border border-gray-100 bg-white"
                        >
                          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-gray-100 text-gray-500 text-xs font-bold shrink-0 mt-0.5">
                            {i + 1}
                          </span>
                          <p className="text-gray-700 text-sm flex-1 leading-relaxed">
                            {a.action}
                          </p>
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium shrink-0 ${pillCls}`}>
                            {a.urgency}
                          </span>
                        </div>
                      );
                    })}
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
