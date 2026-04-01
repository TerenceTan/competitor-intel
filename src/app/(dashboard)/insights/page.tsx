import { db } from "@/db";
import { aiInsights, competitors } from "@/db/schema";
import { sql } from "drizzle-orm";
import { timeAgo, safeParseJson } from "@/lib/utils";
import { InsightModal } from "./insight-modal";
import { FileText, Lightbulb } from "lucide-react";
import { EmptyState } from "@/components/shared/empty-state";

const severityColors: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-orange-400",
  medium: "bg-amber-400",
  low: "bg-blue-400",
};

const severityTextColors: Record<string, string> = {
  critical: "text-red-700",
  high: "text-orange-600",
  medium: "text-amber-600",
  low: "text-blue-600",
};

function SeverityCounts({ findings }: { findings: Array<{ severity: string }> }) {
  const counts: Record<string, number> = {};
  for (const f of findings) {
    const sev = f.severity?.toLowerCase() ?? "low";
    counts[sev] = (counts[sev] || 0) + 1;
  }

  return (
    <div className="flex items-center gap-1.5">
      {(["critical", "high", "medium", "low"] as const).map((sev) => {
        const count = counts[sev] || 0;
        if (count === 0) return null;
        return (
          <span
            key={sev}
            className="flex items-center gap-1"
            title={`${count} ${sev}`}
          >
            <span className={`w-2 h-2 rounded-full ${severityColors[sev]}`} />
            <span className={`text-xs font-semibold ${severityTextColors[sev]}`}>{count}</span>
          </span>
        );
      })}
    </div>
  );
}

export default async function InsightsPage() {
  const allCompetitors = await db.select().from(competitors);

  const latestInsightRows = await db
    .select()
    .from(aiInsights)
    .where(sql`${aiInsights.id} IN (SELECT MAX(id) FROM ai_insights GROUP BY competitor_id)`);

  const insightMap = Object.fromEntries(latestInsightRows.map((i) => [i.competitorId, i]));

  const latestInsights = allCompetitors.map((c) => ({
    competitor: c,
    insight: insightMap[c.id] ?? null,
  }));

  const withInsights = latestInsights.filter((i) => i.insight !== null);
  const withoutInsights = latestInsights.filter((i) => i.insight === null);

  // Sort: highest severity findings first
  const severityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
  withInsights.sort((a, b) => {
    const aFindings = safeParseJson<Array<{ severity: string }>>(a.insight?.keyFindingsJson, [], "keyFindingsJson");
    const bFindings = safeParseJson<Array<{ severity: string }>>(b.insight?.keyFindingsJson, [], "keyFindingsJson");
    const aTop = Math.min(...aFindings.map((f) => severityOrder[f.severity?.toLowerCase()] ?? 4), 4);
    const bTop = Math.min(...bFindings.map((f) => severityOrder[f.severity?.toLowerCase()] ?? 4), 4);
    return aTop - bTop;
  });

  return (
    <div className="space-y-8 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">AI Insights</h1>
        <p className="text-gray-500 text-sm mt-1">
          AI-generated competitive analysis — click a card to expand
        </p>
      </div>

      {withInsights.length === 0 ? (
        <EmptyState
          icon={Lightbulb}
          title="No AI insights generated yet"
          description="Configure your Anthropic API key and run AI analysis to generate competitive insights."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {withInsights.map(({ competitor, insight }) => {
            if (!insight) return null;

            const keyFindings = safeParseJson<Array<{ finding: string; severity: string }>>(insight.keyFindingsJson, [], "keyFindingsJson");
            const actions = safeParseJson<Array<{ action: string; urgency: string }>>(insight.actionsJson, [], "actionsJson");

            // Get the highest severity finding for the border color
            const topSeverity = keyFindings.reduce((top, f) => {
              const order = severityOrder[f.severity?.toLowerCase()] ?? 4;
              const topOrder = severityOrder[top] ?? 4;
              return order < topOrder ? f.severity?.toLowerCase() : top;
            }, "low");

            const borderColor: Record<string, string> = {
              critical: "border-l-red-400",
              high: "border-l-orange-400",
              medium: "border-l-amber-400",
              low: "border-l-blue-400",
            };

            // Extract first sentence of summary for a snappy preview
            const summary = insight.summary ?? "";
            const firstSentence = summary.split(/[.!?]\s/)[0] + (summary.includes(".") ? "." : "");
            const hasMoreText = summary.length > firstSentence.length + 5;

            return (
              <InsightModal
                key={competitor.id}
                competitor={competitor}
                insight={insight}
                keyFindings={keyFindings}
              >
                <div
                  className={`rounded-xl border border-gray-200 border-l-4 ${borderColor[topSeverity] ?? "border-l-gray-300"} p-6 cursor-pointer hover:border-gray-300 hover:shadow-md active:shadow-sm transition-all bg-white h-full flex flex-col`}
                >
                  {/* Card header */}
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <p className="text-gray-900 font-semibold text-sm">
                        {competitor.name}
                      </p>
                      <p className="text-gray-400 text-xs mt-0.5">
                        {timeAgo(insight.generatedAt)}
                      </p>
                    </div>
                    <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500 border border-gray-200">
                      Tier {competitor.tier}
                    </span>
                  </div>

                  {/* Summary preview — first sentence only */}
                  <p className="text-gray-600 text-sm leading-relaxed mb-4 flex-1">
                    {firstSentence}
                    {hasMoreText && <span className="text-gray-400"> ...</span>}
                  </p>

                  {/* Bottom bar: severity dots + action count */}
                  <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                    {keyFindings.length > 0 ? (
                      <SeverityCounts findings={keyFindings} />
                    ) : (
                      <span className="text-gray-400 text-xs">No findings</span>
                    )}
                    {actions.length > 0 && (
                      <span className="text-gray-400 text-xs">
                        {actions.length} action{actions.length !== 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                </div>
              </InsightModal>
            );
          })}

          {/* Competitors without insights */}
          {withoutInsights.map(({ competitor }) => (
            <div
              key={competitor.id}
              className="rounded-xl border border-gray-100 border-l-4 border-l-gray-200 p-5 bg-gray-50/50 flex flex-col"
            >
              <div className="flex items-start justify-between mb-2.5">
                <div>
                  <p className="text-gray-500 font-semibold text-sm">
                    {competitor.name}
                  </p>
                </div>
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-400 border border-gray-200">
                  Tier {competitor.tier}
                </span>
              </div>
              <p className="text-gray-400 text-sm flex-1">Pending analysis</p>
            </div>
          ))}
        </div>
      )}

      {/* Weekly digest placeholder */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <FileText className="w-5 h-5 text-gray-400" />
          <h2 className="text-lg font-semibold text-gray-900">Weekly Digest</h2>
          <span className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-500 border border-gray-200">
            Coming soon
          </span>
        </div>
        <div
          className="rounded-xl border border-gray-200 p-8 text-center bg-white"
        >
          <p className="text-gray-500 text-sm">
            Weekly digest will automatically compile all AI insights into a
            single briefing document.
          </p>
          <p className="text-gray-400 text-xs mt-2">
            Configure email delivery in Admin
          </p>
        </div>
      </section>
    </div>
  );
}
