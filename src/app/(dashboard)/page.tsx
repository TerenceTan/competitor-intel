import { db } from "@/db";
import {
  aiInsights,
  aiPortfolioInsights,
  changeEvents,
  competitors,
  promoSnapshots,
  reputationSnapshots,
  scraperRuns,
} from "@/db/schema";
import { desc, eq, gte, sql } from "drizzle-orm";
import { Card } from "@/components/ui/card";
import { formatDateTime, safeParseJson } from "@/lib/utils";
import Link from "next/link";
import { AlertCircle, Calendar, Clock, TrendingUp, Zap } from "lucide-react";
import { TimeAgo } from "@/components/ui/time-ago";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { KpiRow } from "@/components/charts/kpi-row";
import { SCRAPERS } from "@/lib/constants";

export default async function ExecutiveSummaryPage() {
  // Fetch all competitors for lookup
  const allCompetitors = await db.select().from(competitors);
  const competitorMap = Object.fromEntries(allCompetitors.map((c) => [c.id, c]));

  // Latest portfolio-level recommended actions
  const [latestPortfolio] = await db
    .select()
    .from(aiPortfolioInsights)
    .orderBy(desc(aiPortfolioInsights.generatedAt))
    .limit(1);

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

  // KPI data: changes this week + last 14 days by day
  const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
  const twoWeeksAgo = new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString();
  const changesThisWeek = await db
    .select({ count: sql<number>`count(*)` })
    .from(changeEvents)
    .where(gte(changeEvents.detectedAt, weekAgo));
  const changesByDayRaw = await db
    .select({ day: sql<string>`date(detected_at)`, count: sql<number>`count(*)` })
    .from(changeEvents)
    .where(gte(changeEvents.detectedAt, twoWeeksAgo))
    .groupBy(sql`date(detected_at)`)
    .orderBy(sql`date(detected_at)`);
  const changesByDay = changesByDayRaw.map((r) => ({ value: r.count }));

  // KPI: avg trustpilot across latest reputation snapshots per competitor
  const latestRepScores = await db
    .select({ score: reputationSnapshots.trustpilotScore })
    .from(reputationSnapshots)
    .where(sql`${reputationSnapshots.id} IN (
      SELECT MAX(id) FROM reputation_snapshots GROUP BY competitor_id
    )`)
    .all();
  const validScores = latestRepScores.filter((r) => r.score != null).map((r) => r.score!);
  const avgTrustpilot = validScores.length > 0 ? validScores.reduce((a, b) => a + b, 0) / validScores.length : null;

  // KPI: active promos count (from latest promo snapshots)
  const latestPromos = await db
    .select({ promotionsJson: promoSnapshots.promotionsJson })
    .from(promoSnapshots)
    .where(sql`${promoSnapshots.id} IN (
      SELECT MAX(id) FROM promo_snapshots GROUP BY competitor_id
    )`)
    .all();
  let activePromoCount = 0;
  for (const p of latestPromos) {
    const promos = safeParseJson<unknown[]>(p.promotionsJson, [], "promotionsJson");
    activePromoCount += Array.isArray(promos) ? promos.length : 0;
  }

  const latestRuns = await Promise.all(
    SCRAPERS.map(async (s) => {
      const [run] = await db
        .select()
        .from(scraperRuns)
        .where(eq(scraperRuns.scraperName, s.dbName))
        .orderBy(desc(scraperRuns.startedAt))
        .limit(1);
      return { label: s.label, domain: s.domain, run: run ?? null };
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

      {/* KPI Stats */}
      <KpiRow
        competitorCount={allCompetitors.filter((c) => !c.isSelf).length}
        changesThisWeek={changesThisWeek[0]?.count ?? 0}
        changesByDay={changesByDay}
        avgTrustpilot={avgTrustpilot}
        activePromos={activePromoCount}
      />

      {/* Recommended Actions */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Zap className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold text-gray-900">Recommended Actions</h2>
          {latestPortfolio && (
            <span className="text-gray-500 text-sm">
              — <TimeAgo dateStr={latestPortfolio.generatedAt} />
            </span>
          )}
        </div>

        {!latestPortfolio ? (
          <div className="rounded-xl border border-gray-200 p-8 text-center text-gray-500 bg-white">
            No recommendations yet — run AI analysis to generate consolidated actions.
          </div>
        ) : (() => {
          type PortfolioAction = { action: string; urgency: string; rationale?: string };
          const actions = safeParseJson<PortfolioAction[]>(latestPortfolio.actionsJson, [], "actionsJson");

          type UrgencyKey = "immediate" | "this_week" | "this_month";
          const urgencyConfig: Record<UrgencyKey, { label: string; border: string; badge: string; icon: React.ElementType; iconColor: string }> = {
            immediate: { label: "Immediate",  border: "border-l-red-400",   badge: "bg-red-50 text-red-700 border-red-200",   icon: AlertCircle, iconColor: "text-red-400" },
            this_week: { label: "This Week",  border: "border-l-amber-400", badge: "bg-amber-50 text-amber-700 border-amber-200", icon: Clock,        iconColor: "text-amber-400" },
            this_month: { label: "This Month", border: "border-l-blue-400",  badge: "bg-blue-50 text-blue-700 border-blue-200",  icon: Calendar,     iconColor: "text-blue-400" },
          };

          // Running counter across all groups for sequential numbering
          let globalIdx = 0;

          return (
            <div className="space-y-5">
              {latestPortfolio.summary && (
                <p className="text-gray-600 text-sm leading-relaxed border-l-4 border-gray-200 pl-3 italic">{latestPortfolio.summary}</p>
              )}
              {(["immediate", "this_week", "this_month"] as UrgencyKey[]).map((urgency) => {
                const group = actions.filter((a) => a.urgency === urgency);
                if (!group.length) return null;
                const cfg = urgencyConfig[urgency];
                const Icon = cfg.icon;
                return (
                  <div key={urgency}>
                    <div className="flex items-center gap-2 mb-3">
                      <Icon className={`w-3.5 h-3.5 ${cfg.iconColor}`} />
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${cfg.badge}`}>
                        {cfg.label}
                      </span>
                      <span className="text-xs text-gray-400">{group.length} action{group.length !== 1 ? "s" : ""}</span>
                    </div>
                    <div className="space-y-2.5">
                      {group.map((a) => {
                        globalIdx += 1;
                        const num = globalIdx;
                        return (
                          <div
                            key={num}
                            className={`flex gap-3 px-4 py-4 rounded-lg border border-gray-100 border-l-4 bg-white shadow-sm ${cfg.border}`}
                          >
                            <span className="flex-shrink-0 text-xs font-mono font-bold text-gray-300 mt-0.5 w-5 select-none">
                              {String(num).padStart(2, "0")}
                            </span>
                            <div className="flex flex-col gap-1.5 min-w-0">
                              <p className="text-sm font-semibold text-gray-800 leading-snug">{a.action}</p>
                              {a.rationale && (
                                <p className="text-xs text-gray-500 italic border-l-2 border-gray-200 pl-2 leading-relaxed">{a.rationale}</p>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })()}
      </section>

      {/* Top Things to Know Today */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-5 h-5 text-primary" />
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
              const keyFindings = safeParseJson<Array<{ finding: string; severity: string }>>(insight.keyFindingsJson, [], "keyFindingsJson");
              const topFinding = keyFindings[0];

              return (
                <Link
                  key={insight.id}
                  href={`/competitors/${insight.competitorId}`}
                  className="block"
                >
                  <Card
                    className="p-5 border-gray-200 hover:border-primary/25 hover:shadow-md active:shadow-sm transition-all cursor-pointer bg-white"
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
          <Activity className="w-5 h-5 text-primary" />
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
                <tr className="border-b border-gray-200 bg-gray-50/80">
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
                      className={`border-b border-gray-100 hover:bg-primary/[0.03] transition-colors ${
                        idx === recentChanges.length - 1 ? "border-b-0" : ""
                      }`}
                    >
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                        <TimeAgo dateStr={event.detectedAt} />
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          href={`/competitors/${event.competitorId}`}
                          className="font-medium text-primary hover:text-primary/80 transition-colors"
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
          <Clock className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold text-gray-900">
            Data Freshness / Scraper Status
          </h2>
        </div>

        <div
          className="rounded-xl border border-gray-200 overflow-hidden bg-white"
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50/80">
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
                    key={scraper.label}
                    className={`border-b border-gray-100 ${
                      idx === latestRuns.length - 1 ? "border-b-0" : ""
                    }`}
                  >
                    <td className="px-4 py-3 text-gray-700 font-medium">{scraper.label}</td>
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
