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

  const urgencyColors: Record<string, string> = {
    high: "text-orange-600",
    medium: "text-amber-600",
    low: "text-blue-600",
  };

  const handleEscape = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") setOpen(false);
  }, []);

  useEffect(() => {
    if (open) {
      document.addEventListener("keydown", handleEscape);
      // Focus the close button when modal opens
      closeButtonRef.current?.focus();
      return () => document.removeEventListener("keydown", handleEscape);
    }
  }, [open, handleEscape]);

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
            <div className="sticky top-0 flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white rounded-t-2xl">
              <div>
                <h2 className="text-gray-900 font-bold text-lg">
                  {competitor.name}
                </h2>
                <p className="text-gray-500 text-xs">
                  AI analysis generated {timeAgo(insight.generatedAt)}
                </p>
              </div>
              <button
                ref={closeButtonRef}
                onClick={() => setOpen(false)}
                className="text-gray-400 hover:text-gray-700 transition-colors"
                aria-label="Close dialog"
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
                        key={`finding-${i}-${f.severity}`}
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
                        key={`action-${i}-${a.urgency}`}
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
