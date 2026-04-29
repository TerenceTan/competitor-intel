import { db } from "@/db";
import {
  aiInsights,
  aiPortfolioInsights,
  changeEvents,
  competitors,
  pricingSnapshots,
  promoSnapshots,
  reputationSnapshots,
  scraperRuns,
  socialSnapshots,
} from "@/db/schema";
import { desc, eq, gte, sql, and, inArray } from "drizzle-orm";
import { Card } from "@/components/ui/card";
import { safeParseJson } from "@/lib/utils";
import Link from "next/link";
import { AlertCircle, Calendar, Clock, TrendingUp, Zap, ArrowRight } from "lucide-react";
import { TimeAgo } from "@/components/ui/time-ago";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { KpiRow } from "@/components/charts/kpi-row";
import { CompetitivePosition } from "@/components/charts/competitive-position";
import { ActivityHeatmap } from "@/components/charts/activity-heatmap";
import { MorningBrief } from "@/components/charts/morning-brief";
import { ReputationLeaderboard } from "@/components/charts/reputation-leaderboard";
import { SeverityDonut } from "@/components/charts/severity-donut";
import { SCRAPERS } from "@/lib/constants";
import { parseMarketParam, MARKET_NAMES } from "@/lib/markets";

export default async function ExecutiveSummaryPage({
  searchParams,
}: {
  searchParams: Promise<{ market?: string }>;
}) {
  const sp = await searchParams;
  const market = parseMarketParam(sp.market);
  // Promo & social queries respect the selected market when one is set;
  // social falls back to the global row when no per-market handle exists.
  const promoMarketSql = market
    ? sql`AND market_code = ${market}`
    : sql``;
  const now = Date.now();
  const weekAgo = new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString();
  const twoWeeksAgo = new Date(now - 14 * 24 * 60 * 60 * 1000).toISOString();
  const prevWeekStart = new Date(now - 14 * 24 * 60 * 60 * 1000).toISOString();
  const prevWeekEnd = new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString();
  const thirtyDaysAgo = new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString();

  // --- Parallel data fetching ---
  const [
    allCompetitors,
    latestPortfolio,
    allInsights,
    recentChanges,
    highSevThisWeek,
    highSevLastWeek,
    changesByDayRaw,
    changeSeverityCounts,
    changesByCompDomain,
    allLatestRep,
    allLatestSocial,
    allLatestPromos,
    allLatestPricing,
    latestRuns,
    trustpilotTrend,
    promoTrend,
    socialTrend,
  ] = await Promise.all([
    // All competitors
    db.select().from(competitors),
    // Latest portfolio AI summary
    db.select().from(aiPortfolioInsights).orderBy(desc(aiPortfolioInsights.generatedAt)).limit(1).then((r) => r[0] ?? null),
    // All AI insights (we'll sort by severity client-side)
    db.select().from(aiInsights).orderBy(desc(aiInsights.generatedAt), desc(aiInsights.id)).limit(20),
    // Recent changes (10 for the feed)
    db.select().from(changeEvents).orderBy(desc(changeEvents.detectedAt)).limit(10),
    // High-severity changes this week
    db.select({ count: sql<number>`count(*)` }).from(changeEvents)
      .where(and(gte(changeEvents.detectedAt, weekAgo), inArray(changeEvents.severity, ["critical", "high"]))),
    // High-severity changes last week (for WoW delta)
    db.select({ count: sql<number>`count(*)` }).from(changeEvents)
      .where(and(gte(changeEvents.detectedAt, prevWeekStart), sql`${changeEvents.detectedAt} < ${prevWeekEnd}`, inArray(changeEvents.severity, ["critical", "high"]))),
    // Changes by day (14d, for sparkline)
    db.select({ day: sql<string>`date(detected_at)`, count: sql<number>`count(*)` }).from(changeEvents)
      .where(gte(changeEvents.detectedAt, twoWeeksAgo)).groupBy(sql`date(detected_at)`).orderBy(sql`date(detected_at)`),
    // Change severity counts this week (for donut)
    db.select({ severity: changeEvents.severity, count: sql<number>`count(*)` }).from(changeEvents)
      .where(gte(changeEvents.detectedAt, weekAgo)).groupBy(changeEvents.severity),
    // Changes by competitor x domain (7d, for heatmap)
    db.select({
      competitorId: changeEvents.competitorId,
      domain: changeEvents.domain,
      count: sql<number>`count(*)`,
      maxSeverity: sql<string>`max(CASE severity WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END)`,
    }).from(changeEvents)
      .where(gte(changeEvents.detectedAt, weekAgo))
      .groupBy(changeEvents.competitorId, changeEvents.domain),
    // Latest reputation per competitor
    db.select().from(reputationSnapshots)
      .where(sql`${reputationSnapshots.id} IN (SELECT MAX(id) FROM reputation_snapshots GROUP BY competitor_id)`),
    // Latest social per (competitor, platform). When a market is selected we
    // fetch BOTH the latest per-market and latest global rows, then dedup in JS
    // (prefer per-market) — that way a brand with no per-market profile still
    // shows up via its global handle.
    market
      ? db.select().from(socialSnapshots).where(sql`${socialSnapshots.id} IN (
          SELECT MAX(id) FROM social_snapshots
          WHERE market_code = ${market}
          GROUP BY competitor_id, platform
        ) OR ${socialSnapshots.id} IN (
          SELECT MAX(id) FROM social_snapshots
          WHERE market_code = 'global'
          GROUP BY competitor_id, platform
        )`)
      : db.select().from(socialSnapshots).where(sql`${socialSnapshots.id} IN (
          SELECT MAX(id) FROM social_snapshots WHERE market_code = 'global' GROUP BY competitor_id, platform
        )`),
    // Latest promos per competitor (filtered by market when selected)
    db.select().from(promoSnapshots)
      .where(sql`${promoSnapshots.id} IN (SELECT MAX(id) FROM promo_snapshots WHERE 1=1 ${promoMarketSql} GROUP BY competitor_id)`),
    // Latest pricing per competitor
    db.select().from(pricingSnapshots)
      .where(sql`${pricingSnapshots.id} IN (SELECT MAX(id) FROM pricing_snapshots GROUP BY competitor_id)`),
    // Scraper runs
    Promise.all(
      SCRAPERS.map(async (s) => {
        const [run] = await db.select().from(scraperRuns).where(eq(scraperRuns.scraperName, s.dbName)).orderBy(desc(scraperRuns.startedAt)).limit(1);
        return { label: s.label, domain: s.domain, run: run ?? null };
      })
    ),
    // Sparkline: Pepperstone Trustpilot score over last 30 days
    db.select({ date: reputationSnapshots.snapshotDate, score: reputationSnapshots.trustpilotScore })
      .from(reputationSnapshots)
      .where(and(
        sql`${reputationSnapshots.competitorId} = (SELECT id FROM competitors WHERE is_self = 1 LIMIT 1)`,
        gte(reputationSnapshots.snapshotDate, thirtyDaysAgo.split("T")[0]),
      ))
      .orderBy(reputationSnapshots.snapshotDate),
    // Sparkline: total competitor promos per snapshot date (30 days)
    db.select({
      date: promoSnapshots.snapshotDate,
      count: sql<number>`SUM(json_array_length(${promoSnapshots.promotionsJson}))`,
    })
      .from(promoSnapshots)
      .where(and(
        gte(promoSnapshots.snapshotDate, thirtyDaysAgo.split("T")[0]),
        ...(market ? [eq(promoSnapshots.marketCode, market)] : []),
      ))
      .groupBy(promoSnapshots.snapshotDate)
      .orderBy(promoSnapshots.snapshotDate),
    // Sparkline: Pepperstone total followers over last 30 days.
    // When a market is selected, prefer per-market rows; else global only.
    db.select({
      date: socialSnapshots.snapshotDate,
      total: sql<number>`SUM(${socialSnapshots.followers})`,
    })
      .from(socialSnapshots)
      .where(and(
        sql`${socialSnapshots.competitorId} = (SELECT id FROM competitors WHERE is_self = 1 LIMIT 1)`,
        gte(socialSnapshots.snapshotDate, thirtyDaysAgo.split("T")[0]),
        market
          ? sql`${socialSnapshots.marketCode} IN (${market}, 'global')`
          : eq(socialSnapshots.marketCode, "global"),
      ))
      .groupBy(socialSnapshots.snapshotDate)
      .orderBy(socialSnapshots.snapshotDate),
  ]);

  // --- Derived data ---
  const competitorMap = Object.fromEntries(allCompetitors.map((c) => [c.id, c]));
  const nonSelfCompetitors = allCompetitors.filter((c) => !c.isSelf);
  const pepperstone = allCompetitors.find((c) => c.isSelf);

  // KPI: Trustpilot — ours vs field avg
  const repMap = new Map(allLatestRep.map((r) => [r.competitorId, r]));
  const ourTp = pepperstone ? repMap.get(pepperstone.id)?.trustpilotScore ?? null : null;
  const fieldScores = nonSelfCompetitors.map((c) => repMap.get(c.id)?.trustpilotScore).filter((s): s is number => s != null);
  const fieldAvgTp = fieldScores.length > 0 ? +(fieldScores.reduce((a, b) => a + b, 0) / fieldScores.length).toFixed(2) : null;

  // KPI: High-severity changes
  const highSevCount = highSevThisWeek[0]?.count ?? 0;
  const highSevPrev = highSevLastWeek[0]?.count ?? 0;
  const changesByDay = changesByDayRaw.map((r) => ({ value: r.count }));

  // Sparkline data for KPI cards
  const trustpilotSparkline = trustpilotTrend
    .filter((r) => r.score != null)
    .map((r) => ({ value: r.score! }));
  const promoSparkline = promoTrend.map((r) => ({ value: r.count ?? 0 }));
  const socialSparkline = socialTrend.map((r) => ({ value: r.total ?? 0 }));

  // KPI: Promo pressure
  let currentPromoCount = 0;
  for (const p of allLatestPromos) {
    if (competitorMap[p.competitorId]?.isSelf) continue;
    const promos = safeParseJson<unknown[]>(p.promotionsJson, [], "promotionsJson");
    currentPromoCount += Array.isArray(promos) ? promos.length : 0;
  }
  // Approximate previous week promo count (use current as baseline, delta from change events)
  const promoChangesThisWeek = changesByCompDomain.filter((c) => c.domain === "promotions").reduce((sum, c) => sum + c.count, 0);
  const prevPromoCount = Math.max(0, currentPromoCount - promoChangesThisWeek);

  // KPI: Social share of voice. With per-market + global rows in the result
  // set, dedup per (competitor, platform) preferring the per-market row.
  const socialPerKey = new Map<string, typeof allLatestSocial[number]>();
  for (const s of allLatestSocial) {
    const key = `${s.competitorId}|${s.platform}`;
    const existing = socialPerKey.get(key);
    if (!existing) {
      socialPerKey.set(key, s);
      continue;
    }
    // Prefer per-market over global
    if (existing.marketCode === "global" && s.marketCode !== "global") {
      socialPerKey.set(key, s);
    }
  }
  const socialByCompetitor = new Map<string, number>();
  for (const s of socialPerKey.values()) {
    socialByCompetitor.set(s.competitorId, (socialByCompetitor.get(s.competitorId) ?? 0) + (s.followers ?? 0));
  }
  const totalSocialAll = Array.from(socialByCompetitor.values()).reduce((a, b) => a + b, 0);
  const ourSocial = pepperstone ? (socialByCompetitor.get(pepperstone.id) ?? 0) : 0;
  const socialSov = totalSocialAll > 0 ? Math.round((ourSocial / totalSocialAll) * 100) : null;

  // Competitive position ranks
  type RankEntry = { id: string; value: number };
  function computeRank(entries: RankEntry[], selfId: string | undefined): { rank: number; total: number } {
    if (!selfId) return { rank: 0, total: 0 };
    const sorted = [...entries].sort((a, b) => b.value - a.value);
    const idx = sorted.findIndex((e) => e.id === selfId);
    return { rank: idx >= 0 ? idx + 1 : sorted.length + 1, total: sorted.length };
  }

  const selfId = pepperstone?.id;
  const tpRankEntries: RankEntry[] = allLatestRep.filter((r) => r.trustpilotScore != null).map((r) => ({ id: r.competitorId, value: r.trustpilotScore! }));
  const appRankEntries: RankEntry[] = allLatestRep.filter((r) => r.iosRating != null || r.androidRating != null).map((r) => ({
    id: r.competitorId,
    value: Math.max(r.iosRating ?? 0, r.androidRating ?? 0),
  }));
  const socialRankEntries: RankEntry[] = Array.from(socialByCompetitor.entries()).map(([id, total]) => ({ id, value: total }));
  const promoRankEntries: RankEntry[] = allLatestPromos.map((p) => ({
    id: p.competitorId,
    value: safeParseJson<unknown[]>(p.promotionsJson, [], "promotionsJson").length,
  }));
  const spreadRankEntries: RankEntry[] = allLatestPricing
    .filter((p) => p.spreadJson)
    .map((p) => {
      const spreads = safeParseJson<Array<{ spread_from?: string | number }>>(p.spreadJson, [], "spreadJson");
      const nums = spreads.map((s) => parseFloat(String(s.spread_from))).filter((n) => !isNaN(n) && n > 0);
      return { id: p.competitorId, value: nums.length > 0 ? Math.min(...nums) : 999 };
    })
    .filter((e) => e.value < 999);
  // For spreads, lower is better — invert for ranking
  const spreadRankInverted = spreadRankEntries.map((e) => ({ ...e, value: -e.value }));

  const positionDimensions = [
    { label: "Trustpilot", ...computeRank(tpRankEntries, selfId) },
    { label: "App Rating", ...computeRank(appRankEntries, selfId) },
    { label: "Social Reach", ...computeRank(socialRankEntries, selfId) },
    { label: "Best Spreads", ...computeRank(spreadRankInverted, selfId) },
    { label: "Promos", ...computeRank(promoRankEntries, selfId) },
  ].filter((d) => d.total > 0);

  // Heatmap data
  const sevNumToLabel: Record<string, string> = { "4": "critical", "3": "high", "2": "medium", "1": "low" };
  const heatmapDomains = [...new Set(changesByCompDomain.map((c) => c.domain))].sort();
  const heatmapData = changesByCompDomain.map((c) => ({
    competitorId: c.competitorId,
    competitorName: competitorMap[c.competitorId]?.name ?? c.competitorId,
    domain: c.domain,
    count: c.count,
    maxSeverity: sevNumToLabel[String(c.maxSeverity)] ?? "low",
  }));
  const heatmapCompetitors = nonSelfCompetitors.map((c) => ({ id: c.id, name: c.name }));

  // Severity donut data for this week
  const sevMap = Object.fromEntries((changeSeverityCounts ?? []).map((s) => [s.severity, s.count]));
  const donutData = [
    { label: "Critical", count: sevMap["critical"] ?? 0, color: "#ef4444" },
    { label: "High", count: sevMap["high"] ?? 0, color: "#f97316" },
    { label: "Medium", count: sevMap["medium"] ?? 0, color: "#f59e0b" },
    { label: "Low", count: sevMap["low"] ?? 0, color: "#3b82f6" },
  ];
  const totalChangesWeek = donutData.reduce((a, d) => a + d.count, 0);

  // Reputation leaderboard
  const leaderboardData = allLatestRep
    .filter((r) => r.trustpilotScore != null)
    .map((r) => ({
      name: competitorMap[r.competitorId]?.name ?? r.competitorId,
      score: r.trustpilotScore!,
      isSelf: competitorMap[r.competitorId]?.isSelf === 1,
    }));

  // Top insights — sort by severity count, not recency
  const scoredInsights = allInsights.map((insight) => {
    const findings = safeParseJson<Array<{ finding: string; severity: string }>>(insight.keyFindingsJson, [], "keyFindingsJson");
    const sevScore = findings.reduce((acc, f) => {
      if (f.severity === "critical") return acc + 100;
      if (f.severity === "high") return acc + 10;
      if (f.severity === "medium") return acc + 1;
      return acc;
    }, 0);
    return { insight, findings, sevScore };
  });
  // Deduplicate by competitorId (keep highest severity per competitor)
  const seenCompetitors = new Set<string>();
  const topInsights = scoredInsights
    .sort((a, b) => b.sevScore - a.sevScore)
    .filter(({ insight }) => {
      if (seenCompetitors.has(insight.competitorId)) return false;
      seenCompetitors.add(insight.competitorId);
      return true;
    })
    .slice(0, 3);

  // Scraper freshness
  const now24h = new Date(now - 24 * 60 * 60 * 1000).toISOString();
  const staleScrapers = latestRuns.filter(
    (s) => !s.run || s.run.status === "error" || (s.run.finishedAt && s.run.finishedAt < now24h)
  );
  const allFresh = staleScrapers.length === 0;

  return (
    <div className="space-y-8 max-w-7xl">
      {/* Page title */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Executive Summary</h1>
        <p className="text-gray-500 text-sm mt-1">
          Morning brief — competitive intelligence overview for APAC markets
        </p>
        {market && (
          <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            Promos & social: {MARKET_NAMES[market]}
            <span className="text-primary/60">— Trustpilot remains global</span>
          </div>
        )}
      </div>

      {/* ===== ACT 1: WHAT HAPPENED? ===== */}

      {/* Morning Brief */}
      {latestPortfolio?.summary ? (
        <MorningBrief summary={latestPortfolio.summary} generatedAt={latestPortfolio.generatedAt} />
      ) : (
        <Card className="p-5 border-gray-200 bg-white text-center text-gray-400 text-sm">
          No AI brief yet — run the AI analysis to generate a morning headline.
        </Card>
      )}

      {/* KPI Cards */}
      <KpiRow
        trustpilot={{ ours: ourTp, fieldAvg: fieldAvgTp }}
        highSeverityChanges={{ count: highSevCount, prevCount: highSevPrev }}
        changesByDay={changesByDay}
        promosPressure={{ count: currentPromoCount, prevCount: prevPromoCount }}
        socialShareOfVoice={socialSov}
        trustpilotSparkline={trustpilotSparkline}
        promoSparkline={promoSparkline}
        socialSparkline={socialSparkline}
      />

      {/* Competitive Position Scorecard */}
      {positionDimensions.length > 0 && (
        <CompetitivePosition dimensions={positionDimensions} />
      )}

      {/* ===== ACT 2: WHAT SHOULD WE DO? ===== */}

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
        ) : <ActionsSection actionsJson={latestPortfolio.actionsJson} />}
      </section>

      {/* Competitor Activity Heatmap */}
      {heatmapData.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold text-gray-900">Competitor Activity This Week</h2>
          </div>
          <ActivityHeatmap
            data={heatmapData}
            competitors={heatmapCompetitors}
            domains={heatmapDomains}
          />
        </section>
      )}

      {/* ===== ACT 3: SHOW ME THE DETAILS ===== */}

      {/* Top Insights */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold text-gray-900">Top Insights</h2>
        </div>

        {topInsights.length === 0 ? (
          <div className="rounded-xl border border-gray-200 p-8 text-center text-gray-500 bg-white">
            All clear — no high-priority competitor changes detected.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {topInsights.map(({ insight, findings }) => {
              const competitor = competitorMap[insight.competitorId];
              const topFinding = findings[0];
              return (
                <Link key={insight.id} href={`/competitors/${insight.competitorId}`} className="block">
                  <Card className="p-5 border-gray-200 hover:border-primary/25 hover:shadow-md active:shadow-sm transition-all cursor-pointer bg-white h-full">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                          {competitor?.name ?? insight.competitorId}
                        </p>
                        {topFinding && <SeverityBadge severity={topFinding.severity} />}
                      </div>
                      <span className="text-gray-400 text-xs">
                        <TimeAgo dateStr={insight.generatedAt} />
                      </span>
                    </div>
                    <p className="text-gray-700 text-sm leading-relaxed line-clamp-3">
                      {insight.summary ?? "No summary available."}
                    </p>
                    {topFinding && (
                      <p className="text-gray-500 text-xs mt-3 line-clamp-2">{topFinding.finding}</p>
                    )}
                  </Card>
                </Link>
              );
            })}
          </div>
        )}
      </section>

      {/* Reputation Leaderboard + Severity Donut side by side */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Reputation Leaderboard */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold text-gray-900">Trustpilot Leaderboard</h2>
          </div>
          <Card className="p-5 border-gray-200 bg-white">
            {leaderboardData.length > 0 ? (
              <ReputationLeaderboard data={leaderboardData} />
            ) : (
              <p className="text-sm text-gray-400 text-center py-8">No reputation data yet.</p>
            )}
          </Card>
        </div>

        {/* Severity Donut */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <AlertCircle className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold text-gray-900">Change Severity This Week</h2>
          </div>
          <Card className="p-5 border-gray-200 bg-white flex items-center justify-center">
            <SeverityDonut data={donutData} centerLabel="Changes" centerValue={totalChangesWeek} />
          </Card>
        </div>
      </section>

      {/* Recent Changes Feed */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold text-gray-900">Recent Changes</h2>
          </div>
          <Link href="/changes" className="text-sm text-primary hover:text-primary/80 flex items-center gap-1">
            View all <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {recentChanges.length === 0 ? (
          <div className="rounded-xl border border-gray-200 p-8 text-center text-gray-500 bg-white">
            No change events detected yet.
          </div>
        ) : (
          <div className="rounded-xl border border-gray-200 overflow-hidden bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50/80">
                  <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">When</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Competitor</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Domain</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">What Changed</th>
                  <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Severity</th>
                </tr>
              </thead>
              <tbody>
                {recentChanges.map((event, idx) => {
                  const competitor = competitorMap[event.competitorId];
                  return (
                    <tr
                      key={event.id}
                      className={`border-b border-gray-100 hover:bg-primary/[0.03] transition-colors ${idx === recentChanges.length - 1 ? "border-b-0" : ""}`}
                    >
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                        <TimeAgo dateStr={event.detectedAt} />
                      </td>
                      <td className="px-4 py-3">
                        <Link href={`/competitors/${event.competitorId}`} className="font-medium text-primary hover:text-primary/80 transition-colors">
                          {competitor?.name ?? event.competitorId}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-gray-500 capitalize">{event.domain}</td>
                      <td className="px-4 py-3 text-gray-700 max-w-xs">
                        <span className="font-medium">{event.fieldName}</span>
                        {event.oldValue && event.newValue && (
                          <span className="text-gray-500 text-xs block truncate">
                            {String(event.oldValue).slice(0, 40)} → {String(event.newValue).slice(0, 40)}
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

      {/* Data Freshness — compact pill row */}
      <section className="flex items-center gap-3 text-sm">
        <Clock className="w-4 h-4 text-gray-400" />
        <span className="text-gray-500">Data freshness:</span>
        {allFresh ? (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border bg-green-50 text-green-700 border-green-200">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
            All scrapers fresh
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border bg-amber-50 text-amber-700 border-amber-200">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            {staleScrapers.length} scraper{staleScrapers.length !== 1 ? "s" : ""} stale
          </span>
        )}
        <Link href="/admin" className="text-xs text-primary hover:text-primary/80 ml-auto">
          View details →
        </Link>
      </section>
    </div>
  );
}

// --- Sub-components (server-safe) ---

function ActionsSection({ actionsJson }: { actionsJson: string | null }) {
  type PortfolioAction = { action: string; urgency: string; rationale?: string };
  const actions = safeParseJson<PortfolioAction[]>(actionsJson, [], "actionsJson");

  type UrgencyKey = "immediate" | "this_week" | "this_month";
  const urgencyConfig: Record<UrgencyKey, { label: string; border: string; badge: string; icon: React.ElementType; iconColor: string }> = {
    immediate: { label: "Immediate", border: "border-l-red-400", badge: "bg-red-50 text-red-700 border-red-200", icon: AlertCircle, iconColor: "text-red-400" },
    this_week: { label: "This Week", border: "border-l-amber-400", badge: "bg-amber-50 text-amber-700 border-amber-200", icon: Clock, iconColor: "text-amber-400" },
    this_month: { label: "This Month", border: "border-l-blue-400", badge: "bg-blue-50 text-blue-700 border-blue-200", icon: Calendar, iconColor: "text-blue-400" },
  };

  // Show max 5 actions
  const allActions: Array<PortfolioAction & { urgencyKey: UrgencyKey }> = [];
  for (const urgency of ["immediate", "this_week", "this_month"] as UrgencyKey[]) {
    for (const a of actions.filter((a) => a.urgency === urgency)) {
      allActions.push({ ...a, urgencyKey: urgency });
    }
  }
  const visibleActions = allActions.slice(0, 5);
  const hasMore = allActions.length > 5;

  let globalIdx = 0;

  return (
    <div className="space-y-5">
      {(["immediate", "this_week", "this_month"] as UrgencyKey[]).map((urgency) => {
        const group = visibleActions.filter((a) => a.urgencyKey === urgency);
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
              <span className="text-xs text-gray-400">
                {actions.filter((a) => a.urgency === urgency).length} action{actions.filter((a) => a.urgency === urgency).length !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="space-y-2.5">
              {group.map((a) => {
                globalIdx += 1;
                return (
                  <div
                    key={globalIdx}
                    className={`flex gap-3 px-4 py-4 rounded-lg border border-gray-100 border-l-4 bg-white shadow-sm ${cfg.border}`}
                  >
                    <span className="flex-shrink-0 text-xs font-mono font-bold text-gray-300 mt-0.5 w-5 select-none">
                      {String(globalIdx).padStart(2, "0")}
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
      {hasMore && (
        <p className="text-sm text-gray-400 text-center pt-2">
          Showing 5 of {allActions.length} actions — run AI analysis to refresh
        </p>
      )}
    </div>
  );
}

function Activity({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}

function Shield({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
    </svg>
  );
}
