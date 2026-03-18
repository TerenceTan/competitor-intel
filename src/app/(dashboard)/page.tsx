import { db } from "@/db";
import {
  aiInsights,
  changeEvents,
  competitors,
  scraperRuns,
} from "@/db/schema";
import { desc, eq } from "drizzle-orm";
import { Card } from "@/components/ui/card";
import { formatDateTime } from "@/lib/utils";
import Link from "next/link";
import { Clock, TrendingUp } from "lucide-react";
import { TimeAgo } from "@/components/ui/time-ago";

function SeverityBadge({ severity }: { severity: string }) {
  const colorMap: Record<string, string> = {
    critical: "bg-red-50 text-red-700 border-red-200",
    high: "bg-orange-50 text-orange-700 border-orange-200",
    medium: "bg-amber-50 text-amber-700 border-amber-200",
    low: "bg-blue-50 text-blue-700 border-blue-200",
  };
  const cls = colorMap[severity?.toLowerCase()] ?? "bg-gray-100 text-gray-600 border-gray-200";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}
    >
      {severity ?? "unknown"}
    </span>
  );
}

export default async function ExecutiveSummaryPage() {
  // Fetch all competitors for lookup
  const allCompetitors = await db.select().from(competitors);
  const competitorMap = Object.fromEntries(allCompetitors.map((c) => [c.id, c]));

  // Top 3 latest AI insights
  const topInsights = await db
    .select()
    .from(aiInsights)
    .orderBy(desc(aiInsights.generatedAt), desc(aiInsights.id))
    .limit(3);

  // Last 20 change events
  const recentChanges = await db
    .select()
    .from(changeEvents)
    .orderBy(desc(changeEvents.detectedAt))
    .limit(20);

  const SCRAPER_DEFS = [
    { name: "Pricing Scraper", dbName: "pricing_scraper", domain: "pricing" },
    { name: "Promo Scraper", dbName: "promo_scraper", domain: "promotions" },
    { name: "Social Scraper", dbName: "social_scraper", domain: "social" },
    { name: "Reputation Scraper", dbName: "reputation_scraper", domain: "reputation" },
    { name: "News Scraper", dbName: "news_scraper", domain: "news" },
    { name: "AI Analysis", dbName: "ai_analyzer", domain: "insights" },
  ];

  const latestRuns = await Promise.all(
    SCRAPER_DEFS.map(async (s) => {
      const [run] = await db
        .select()
        .from(scraperRuns)
        .where(eq(scraperRuns.scraperName, s.dbName))
        .orderBy(desc(scraperRuns.startedAt))
        .limit(1);
      return { ...s, run: run ?? null };
    })
  );

  return (
    <div className="space-y-8 max-w-7xl">
      {/* Page title */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Executive Summary</h1>
        <p className="text-gray-500 text-sm mt-1">
          Daily morning brief — competitor intelligence overview for APAC markets
        </p>
      </div>

      {/* Top Things to Know Today */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-5 h-5" style={{ color: "#0064FA" }} />
          <h2 className="text-lg font-semibold text-gray-900">
            Top Things to Know Today
          </h2>
        </div>

        {topInsights.length === 0 ? (
          <div className="rounded-xl border border-gray-200 p-8 text-center text-gray-500 bg-white">
            No AI insights yet — run the AI analysis to generate insights.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {topInsights.map((insight) => {
              const competitor = competitorMap[insight.competitorId];
              let keyFindings: Array<{ finding: string; severity: string }> = [];
              try {
                keyFindings = insight.keyFindingsJson
                  ? JSON.parse(insight.keyFindingsJson)
                  : [];
              } catch {}
              const topFinding = keyFindings[0];

              return (
                <Link
                  key={insight.id}
                  href={`/competitors/${insight.competitorId}`}
                  className="block"
                >
                  <Card
                    className="p-5 border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-colors cursor-pointer bg-white"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                          {competitor?.name ?? insight.competitorId}
                        </p>
                        {topFinding && (
                          <SeverityBadge severity={topFinding.severity} />
                        )}
                      </div>
                      <span className="text-gray-400 text-xs">
                        <TimeAgo dateStr={insight.generatedAt} />
                      </span>
                    </div>
                    <p className="text-gray-700 text-sm leading-relaxed line-clamp-3">
                      {insight.summary ?? "No summary available."}
                    </p>
                    {topFinding && (
                      <p className="text-gray-500 text-xs mt-3 line-clamp-2">
                        {topFinding.finding}
                      </p>
                    )}
                  </Card>
                </Link>
              );
            })}
          </div>
        )}
      </section>

      {/* Recent Changes Feed */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-5 h-5" style={{ color: "#0064FA" }} />
          <h2 className="text-lg font-semibold text-gray-900">
            Recent Changes Feed
          </h2>
          <span className="text-gray-500 text-sm">— last 20 events</span>
        </div>

        {recentChanges.length === 0 ? (
          <div className="rounded-xl border border-gray-200 p-8 text-center text-gray-500 bg-white">
            No change events detected yet.
          </div>
        ) : (
          <div
            className="rounded-xl border border-gray-200 overflow-hidden bg-white"
          >
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                    When
                  </th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                    Competitor
                  </th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                    Domain
                  </th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                    What Changed
                  </th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                    Severity
                  </th>
                </tr>
              </thead>
              <tbody>
                {recentChanges.map((event, idx) => {
                  const competitor = competitorMap[event.competitorId];
                  return (
                    <tr
                      key={event.id}
                      className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${
                        idx === recentChanges.length - 1 ? "border-b-0" : ""
                      }`}
                    >
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                        <TimeAgo dateStr={event.detectedAt} />
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          href={`/competitors/${event.competitorId}`}
                          className="hover:underline font-medium"
                          style={{ color: "#0064FA" }}
                        >
                          {competitor?.name ?? event.competitorId}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-gray-500 capitalize">
                        {event.domain}
                      </td>
                      <td className="px-4 py-3 text-gray-700 max-w-xs">
                        <span className="font-medium">{event.fieldName}</span>
                        {event.oldValue && event.newValue && (
                          <span className="text-gray-500 text-xs block truncate">
                            {String(event.oldValue).slice(0, 40)} →{" "}
                            {String(event.newValue).slice(0, 40)}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <SeverityBadge severity={event.severity} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Data Freshness Grid */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Clock className="w-5 h-5" style={{ color: "#0064FA" }} />
          <h2 className="text-lg font-semibold text-gray-900">
            Data Freshness / Scraper Status
          </h2>
        </div>

        <div
          className="rounded-xl border border-gray-200 overflow-hidden bg-white"
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Scraper
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Domain
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Status
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Last Run
                </th>
              </tr>
            </thead>
            <tbody>
              {latestRuns.map((scraper, idx) => {
                const status = scraper.run?.status ?? "never_run";
                const statusStyle =
                  status === "success"
                    ? "bg-green-50 text-green-700 border-green-200"
                    : status === "partial"
                    ? "bg-yellow-50 text-yellow-700 border-yellow-200"
                    : status === "running"
                    ? "bg-blue-50 text-blue-700 border-blue-200"
                    : status === "error"
                    ? "bg-red-50 text-red-700 border-red-200"
                    : "bg-gray-100 text-gray-500 border-gray-200";
                const dotStyle =
                  status === "success" ? "bg-green-400"
                  : status === "partial" ? "bg-yellow-400"
                  : status === "running" ? "bg-blue-400"
                  : status === "error" ? "bg-red-400"
                  : "bg-gray-400";
                const label =
                  status === "never_run" ? "Never run" :
                  status === "partial" ? "Partial" :
                  status.charAt(0).toUpperCase() + status.slice(1);
                return (
                  <tr
                    key={scraper.name}
                    className={`border-b border-gray-100 ${
                      idx === latestRuns.length - 1 ? "border-b-0" : ""
                    }`}
                  >
                    <td className="px-4 py-3 text-gray-700 font-medium">{scraper.name}</td>
                    <td className="px-4 py-3 text-gray-500 capitalize">{scraper.domain}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${statusStyle}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${dotStyle}`} />
                        {label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {scraper.run ? formatDateTime(scraper.run.startedAt) : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Activity({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
    >
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}
