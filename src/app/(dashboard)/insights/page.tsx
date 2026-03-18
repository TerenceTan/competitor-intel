import { db } from "@/db";
import { aiInsights, competitors } from "@/db/schema";
import { desc, eq } from "drizzle-orm";
import { timeAgo } from "@/lib/utils";
import { InsightModal } from "./insight-modal";
import { FileText } from "lucide-react";

export default async function InsightsPage() {
  const allCompetitors = await db.select().from(competitors);

  // Latest insight per competitor
  const latestInsights = await Promise.all(
    allCompetitors.map(async (c) => {
      const [insight] = await db
        .select()
        .from(aiInsights)
        .where(eq(aiInsights.competitorId, c.id))
        .orderBy(desc(aiInsights.generatedAt))
        .limit(1);
      return { competitor: c, insight: insight ?? null };
    })
  );

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
        <div
          className="rounded-xl border border-gray-200 p-12 text-center text-gray-500 bg-white"
        >
          No AI insights generated yet. Configure your Anthropic API key to
          enable AI analysis.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {withInsights.map(({ competitor, insight }) => {
            if (!insight) return null;

            let keyFindings: Array<{ finding: string; severity: string }> = [];
            try {
              keyFindings = insight.keyFindingsJson
                ? JSON.parse(insight.keyFindingsJson)
                : [];
            } catch {}

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
                  className={`rounded-xl border border-gray-200 border-l-4 ${borderColor} p-5 cursor-pointer hover:bg-gray-50 transition-colors bg-white`}
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
              className="rounded-xl border border-gray-200 border-l-4 border-l-gray-300 p-5 opacity-40 bg-white"
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
