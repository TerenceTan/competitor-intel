import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import {
  competitors,
  promoSnapshots,
  pricingSnapshots,
  reputationSnapshots,
  changeEvents,
  aiPortfolioInsights,
} from "@/db/schema";
import { sql, and, gte, or, isNull, eq, desc } from "drizzle-orm";
import { safeParseJson } from "@/lib/utils";

/**
 * GET /api/v1/trends
 *
 * Aggregated market trends without competitor names.
 * Returns promo activity, spread direction, reputation moves,
 * high-severity changes, and the latest AI morning brief summary.
 *
 * Query parameters:
 *   - days:   lookback window in days (default: 7, max: 90)
 *   - market: filter by market code (e.g. ?market=th)
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const days = Math.min(Math.max(parseInt(searchParams.get("days") ?? "7", 10) || 7, 1), 90);
  const marketFilter = searchParams.get("market");

  const now = new Date();
  const cutoff = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
  const cutoffStr = cutoff.toISOString().split("T")[0];
  const prevCutoff = new Date(cutoff.getTime() - days * 24 * 60 * 60 * 1000);
  const prevCutoffStr = prevCutoff.toISOString().split("T")[0];

  // Exclude Pepperstone self-benchmark from competitor aggregations
  const nonSelfCondition = sql`competitor_id IN (
    SELECT id FROM competitors WHERE is_self = 0 OR is_self IS NULL
  )`;

  // --- Promo trends ---
  const promoConditions = [
    nonSelfCondition,
    gte(promoSnapshots.snapshotDate, cutoffStr),
  ];
  if (marketFilter) {
    promoConditions.push(eq(promoSnapshots.marketCode, marketFilter));
  }

  const promoRows = await db
    .select({
      marketCode: promoSnapshots.marketCode,
      promotionsJson: promoSnapshots.promotionsJson,
    })
    .from(promoSnapshots)
    .where(and(...promoConditions));

  // Count promos by market and compute types
  const promoByMarket: Record<string, number> = {};
  const promoTypes: Record<string, number> = {};
  let totalPromos = 0;
  let activePromos = 0;
  const bonusValues: number[] = [];

  for (const row of promoRows) {
    const promos = safeParseJson<Array<Record<string, unknown>>>(row.promotionsJson, []);
    const market = row.marketCode ?? "global";
    promoByMarket[market] = (promoByMarket[market] ?? 0) + promos.length;
    totalPromos += promos.length;

    for (const p of promos) {
      const type = String(p.type ?? "other").toLowerCase();
      promoTypes[type] = (promoTypes[type] ?? 0) + 1;

      const status = String(p.status ?? p.active ?? "").toLowerCase();
      if (status === "active" || status === "true") activePromos++;

      // Extract numeric bonus value if present
      const valStr = String(p.value ?? "");
      const valMatch = valStr.match(/[\d,.]+/);
      if (valMatch) {
        const num = parseFloat(valMatch[0].replace(/,/g, ""));
        if (!isNaN(num) && num > 0 && num < 100000) bonusValues.push(num);
      }
    }
  }

  // Previous period promo count for trend
  const prevPromoConditions = [
    nonSelfCondition,
    gte(promoSnapshots.snapshotDate, prevCutoffStr),
    sql`${promoSnapshots.snapshotDate} < ${cutoffStr}`,
  ];
  if (marketFilter) {
    prevPromoConditions.push(eq(promoSnapshots.marketCode, marketFilter));
  }

  const prevPromoRows = await db
    .select({
      promotionsJson: promoSnapshots.promotionsJson,
    })
    .from(promoSnapshots)
    .where(and(...prevPromoConditions));

  let prevTotalPromos = 0;
  for (const row of prevPromoRows) {
    const promos = safeParseJson<Array<Record<string, unknown>>>(row.promotionsJson, []);
    prevTotalPromos += promos.length;
  }

  const promoTrend = prevTotalPromos === 0
    ? (totalPromos > 0 ? "up" : "flat")
    : totalPromos > prevTotalPromos * 1.1 ? "up"
    : totalPromos < prevTotalPromos * 0.9 ? "down"
    : "flat";

  // --- Spread trends ---
  const spreadConditions = [
    nonSelfCondition,
    gte(pricingSnapshots.snapshotDate, cutoffStr),
  ];
  if (marketFilter) {
    spreadConditions.push(eq(pricingSnapshots.marketCode, marketFilter));
  }

  const spreadRows = await db
    .select({
      spreadJson: pricingSnapshots.spreadJson,
      minDepositUsd: pricingSnapshots.minDepositUsd,
    })
    .from(pricingSnapshots)
    .where(and(...spreadConditions));

  const spreadValues: number[] = [];
  const deposits: number[] = [];

  for (const row of spreadRows) {
    if (row.minDepositUsd !== null) deposits.push(row.minDepositUsd);
    const spreads = safeParseJson<Array<Record<string, string>>>(row.spreadJson, []);
    for (const s of spreads) {
      const raw = String(s.spread_from ?? "");
      const match = raw.match(/[\d.]+/);
      if (match) {
        const val = parseFloat(match[0]);
        if (!isNaN(val) && val >= 0 && val < 100) spreadValues.push(val);
      }
    }
  }

  // Previous period spreads for direction
  const prevSpreadConditions = [
    nonSelfCondition,
    gte(pricingSnapshots.snapshotDate, prevCutoffStr),
    sql`${pricingSnapshots.snapshotDate} < ${cutoffStr}`,
  ];
  if (marketFilter) {
    prevSpreadConditions.push(eq(pricingSnapshots.marketCode, marketFilter));
  }

  const prevSpreadRows = await db
    .select({ spreadJson: pricingSnapshots.spreadJson })
    .from(pricingSnapshots)
    .where(and(...prevSpreadConditions));

  const prevSpreadValues: number[] = [];
  for (const row of prevSpreadRows) {
    const spreads = safeParseJson<Array<Record<string, string>>>(row.spreadJson, []);
    for (const s of spreads) {
      const match = String(s.spread_from ?? "").match(/[\d.]+/);
      if (match) {
        const val = parseFloat(match[0]);
        if (!isNaN(val) && val >= 0 && val < 100) prevSpreadValues.push(val);
      }
    }
  }

  const avgSpread = spreadValues.length > 0
    ? spreadValues.reduce((a, b) => a + b, 0) / spreadValues.length
    : null;
  const prevAvgSpread = prevSpreadValues.length > 0
    ? prevSpreadValues.reduce((a, b) => a + b, 0) / prevSpreadValues.length
    : null;

  const spreadDirection =
    avgSpread !== null && prevAvgSpread !== null
      ? avgSpread < prevAvgSpread * 0.95 ? "tightening"
      : avgSpread > prevAvgSpread * 1.05 ? "widening"
      : "stable"
      : "insufficient_data";

  const spreadChangePct =
    avgSpread !== null && prevAvgSpread !== null && prevAvgSpread > 0
      ? Math.round(((avgSpread - prevAvgSpread) / prevAvgSpread) * 1000) / 10
      : null;

  // --- Reputation trends ---
  const repRows = await db
    .select({
      trustpilotScore: reputationSnapshots.trustpilotScore,
    })
    .from(reputationSnapshots)
    .where(and(
      nonSelfCondition,
      gte(reputationSnapshots.snapshotDate, cutoffStr),
    ));

  const prevRepRows = await db
    .select({
      trustpilotScore: reputationSnapshots.trustpilotScore,
    })
    .from(reputationSnapshots)
    .where(and(
      nonSelfCondition,
      gte(reputationSnapshots.snapshotDate, prevCutoffStr),
      sql`${reputationSnapshots.snapshotDate} < ${cutoffStr}`,
    ));

  const avgTrustpilot = repRows.filter(r => r.trustpilotScore !== null).length > 0
    ? repRows.reduce((sum, r) => sum + (r.trustpilotScore ?? 0), 0) /
      repRows.filter(r => r.trustpilotScore !== null).length
    : null;

  const prevAvgTrustpilot = prevRepRows.filter(r => r.trustpilotScore !== null).length > 0
    ? prevRepRows.reduce((sum, r) => sum + (r.trustpilotScore ?? 0), 0) /
      prevRepRows.filter(r => r.trustpilotScore !== null).length
    : null;

  const trustpilotChange =
    avgTrustpilot !== null && prevAvgTrustpilot !== null
      ? Math.round((avgTrustpilot - prevAvgTrustpilot) * 100) / 100
      : null;

  // --- High-severity changes ---
  const changeConditions = [
    nonSelfCondition,
    gte(changeEvents.detectedAt, cutoff.toISOString()),
  ];
  if (marketFilter) {
    changeConditions.push(eq(changeEvents.marketCode, marketFilter));
  }

  const highChanges = await db
    .select({ count: sql<number>`COUNT(*)` })
    .from(changeEvents)
    .where(and(
      ...changeConditions,
      sql`${changeEvents.severity} IN ('high', 'critical')`,
    ));

  const totalChanges = await db
    .select({ count: sql<number>`COUNT(*)` })
    .from(changeEvents)
    .where(and(...changeConditions));

  // --- AI summary (latest morning brief) ---
  const latestBrief = await db
    .select({
      summary: aiPortfolioInsights.summary,
      generatedAt: aiPortfolioInsights.generatedAt,
    })
    .from(aiPortfolioInsights)
    .orderBy(desc(aiPortfolioInsights.generatedAt))
    .limit(1);

  const periodStart = cutoffStr;
  const periodEnd = now.toISOString().split("T")[0];

  return NextResponse.json({
    period: `${periodStart} to ${periodEnd}`,
    days,
    promos: {
      total: totalPromos,
      active: activePromos,
      by_market: promoByMarket,
      by_type: promoTypes,
      avg_bonus_value: bonusValues.length > 0
        ? `$${Math.round(bonusValues.reduce((a, b) => a + b, 0) / bonusValues.length)}`
        : null,
      trend: promoTrend,
      vs_previous_period: { current: totalPromos, previous: prevTotalPromos },
    },
    spreads: {
      direction: spreadDirection,
      avg_spread_pips: avgSpread !== null ? Math.round(avgSpread * 100) / 100 : null,
      change_pct: spreadChangePct,
      avg_min_deposit: deposits.length > 0
        ? Math.round(deposits.reduce((a, b) => a + b, 0) / deposits.length)
        : null,
      brokers_reporting: spreadRows.length,
    },
    reputation: {
      avg_trustpilot: avgTrustpilot !== null ? Math.round(avgTrustpilot * 100) / 100 : null,
      trustpilot_change: trustpilotChange,
      snapshots_in_period: repRows.length,
    },
    changes: {
      high_severity: highChanges[0]?.count ?? 0,
      total: totalChanges[0]?.count ?? 0,
    },
    summary: latestBrief[0]?.summary ?? null,
    summary_generated_at: latestBrief[0]?.generatedAt ?? null,
    meta: {
      market_filter: marketFilter ?? "all",
      generated_at: now.toISOString(),
    },
  });
}
