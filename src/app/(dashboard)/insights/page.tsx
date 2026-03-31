import { db } from "@/db";
import { aiInsights, competitors } from "@/db/schema";
import { sql } from "drizzle-orm";
import { timeAgo, safeParseJson } from "@/lib/utils";
import { InsightModal } from "./insight-modal";
import { FileText, Lightbulb } from "lucide-react";
import { EmptyState } from "@/components/shared/empty-state";

export default async function InsightsPage() {
  const allCompetitors = await db.select().from(competitors);

  // Batch fetch latest insight per competitor in a single query
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

  return (
    <div className="space-y-8 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">AI Insights</h1>
        <p className="text-gray-500 text-sm mt-1">
          Latest AI-generated competitive analysis — click a card for full
          details
        </p>
      </div>

      {/* Insight cards */}
      {withInsights.length === 0 ? (
        <EmptyState
          icon={Lightbulb}
          title="No AI insights generated yet"
          description="Configure your Anthropic API key and run AI analysis to generate competitive insights."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {withInsights.map(({ competitor, insight }) => {
            if (!insight) return null;

            const keyFindings = safeParseJson<Array<{ finding: string; severity: string }>>(insight.keyFindingsJson, [], "keyFindingsJson");

            const topFinding = keyFindings[0];
            const severityColorMap: Record<string, string> = {
              critical: "border-l-red-400",
              high: "border-l-orange-400",
              medium: "border-l-amber-400",
              low: "border-l-blue-400",
            };
            const borderColor =
              severityColorMap[topFinding?.severity?.toLowerCase()] ??
              "border-l-gray-300";

            return (
              <InsightModal
                key={competitor.id}
                competitor={competitor}
                insight={insight}
                keyFindings={keyFindings}
              >
                <div
                  className={`rounded-xl border border-gray-200 border-l-4 ${borderColor} p-5 cursor-pointer hover:border-gray-300 hover:shadow-md active:shadow-sm transition-all bg-white`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="text-gray-900 font-semibold text-sm">
                        {competitor.name}
                      </p>
                      <p className="text-gray-500 text-xs mt-0.5">
                        Tier {competitor.tier}
                      </p>
                    </div>
                    <span className="text-gray-400 text-xs">
                      {timeAgo(insight.generatedAt)}
                    </span>
                  </div>

                  <p className="text-gray-700 text-sm line-clamp-3 leading-relaxed">
                    {insight.summary ?? "No summary available."}
                  </p>

                  {keyFindings.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-200">
                      <p className="text-gray-500 text-xs">
                        {keyFindings.length} key finding
                        {keyFindings.length !== 1 ? "s" : ""}
                      </p>
                    </div>
                  )}
                </div>
              </InsightModal>
            );
          })}

          {/* Competitors without insights */}
          {withoutInsights.map(({ competitor }) => (
            <div
              key={competitor.id}
              className="rounded-xl border border-gray-100 border-l-4 border-l-gray-200 p-5 bg-gray-50/50"
            >
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="text-gray-900 font-semibold text-sm">
                    {competitor.name}
                  </p>
                  <p className="text-gray-500 text-xs mt-0.5">
                    Tier {competitor.tier}
                  </p>
                </div>
              </div>
              <p className="text-gray-400 text-sm">No insights generated yet.</p>
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
            Configure email delivery in Admin → Notifications
          </p>
        </div>
      </section>
    </div>
  );
}
