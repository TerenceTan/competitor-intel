import { NextResponse } from "next/server";
import { safeParseJson } from "@/lib/utils";
import { db } from "@/db";
import {
  competitors,
  pricingSnapshots,
  reputationSnapshots,
  promoSnapshots,
  aiInsights,
} from "@/db/schema";
import { eq, or, isNull, sql } from "drizzle-orm";

export async function GET() {
  const allCompetitors = await db
    .select()
    .from(competitors)
    .where(or(eq(competitors.isSelf, 0), isNull(competitors.isSelf)));

  // Batch fetch latest snapshots for all competitors in 4 queries (not N*4)
  const [latestPricing, latestReputation, latestPromos, latestInsights] = await Promise.all([
    db
      .select()
      .from(pricingSnapshots)
      .where(sql`${pricingSnapshots.id} IN (SELECT MAX(id) FROM pricing_snapshots GROUP BY competitor_id)`),
    db
      .select()
      .from(reputationSnapshots)
      .where(sql`${reputationSnapshots.id} IN (SELECT MAX(id) FROM reputation_snapshots GROUP BY competitor_id)`),
    db
      .select()
      .from(promoSnapshots)
      .where(sql`${promoSnapshots.id} IN (SELECT MAX(id) FROM promo_snapshots GROUP BY competitor_id)`),
    db
      .select()
      .from(aiInsights)
      .where(sql`${aiInsights.id} IN (SELECT MAX(id) FROM ai_insights GROUP BY competitor_id)`),
  ]);

  // Index by competitor ID for O(1) lookup
  const pricingMap = Object.fromEntries(latestPricing.map((p) => [p.competitorId, p]));
  const reputationMap = Object.fromEntries(latestReputation.map((r) => [r.competitorId, r]));
  const promoMap = Object.fromEntries(latestPromos.map((p) => [p.competitorId, p]));
  const insightMap = Object.fromEntries(latestInsights.map((i) => [i.competitorId, i]));

  const results = allCompetitors.map((competitor) => {
    const pricing = pricingMap[competitor.id];
    const reputation = reputationMap[competitor.id];
    const promo = promoMap[competitor.id];
    const insight = insightMap[competitor.id];

    const parsedPromos = safeParseJson<unknown[]>(promo?.promotionsJson, [], "promotionsJson");
    const promoCount = Array.isArray(parsedPromos) ? parsedPromos.length : 0;

    // Max leverage from latest pricing
    let maxLeverage: number | null = null;
    const lev = safeParseJson<Record<string, unknown> | null>(pricing?.leverageJson, null, "leverageJson");
    if (typeof lev === "object" && lev !== null) {
      const vals = (Object.values(lev) as unknown[])
        .map((v) => {
          if (typeof v === "number") return v;
          if (typeof v === "string" && v.includes(":")) return parseInt(v.split(":")[1], 10);
          return NaN;
        })
        .filter((v) => !isNaN(v as number)) as number[];
      maxLeverage = vals.length > 0 ? Math.max(...vals) : null;
    }

    // Spread from — extract lowest spread across all account types
    let spreadFrom: string | null = null;
    const spreadData = safeParseJson<Array<{ spread_from?: string; account_type?: string }>>(
      pricing?.spreadJson, [], "spreadJson"
    );
    if (spreadData.length > 0) {
      // Find the lowest numeric spread
      let lowestSpread = Infinity;
      let lowestText = "";
      for (const s of spreadData) {
        const raw = s.spread_from ?? "";
        const numMatch = raw.match(/[\d.]+/);
        if (numMatch) {
          const num = parseFloat(numMatch[0]);
          if (num < lowestSpread) {
            lowestSpread = num;
            lowestText = raw;
          }
        }
      }
      if (lowestSpread < Infinity) {
        spreadFrom = lowestText;
      }
    }

    // Account types count
    const accountTypes = safeParseJson<unknown[]>(pricing?.accountTypesJson, [], "accountTypesJson");
    const accountTypesCount = accountTypes.length;

    // AI findings severity breakdown
    const keyFindings = safeParseJson<Array<{ severity: string }>>(
      insight?.keyFindingsJson, [], "keyFindingsJson"
    );
    const findingCounts: Record<string, number> = {};
    for (const f of keyFindings) {
      const sev = f.severity?.toLowerCase() ?? "low";
      findingCounts[sev] = (findingCounts[sev] || 0) + 1;
    }

    return {
      id: competitor.id,
      name: competitor.name,
      tier: competitor.tier,
      website: competitor.website,
      maxLeverage,
      minDepositUsd: pricing?.minDepositUsd ?? null,
      instrumentsCount: pricing?.instrumentsCount ?? null,
      spreadFrom,
      accountTypesCount,
      promoCount,
      trustpilotScore: reputation?.trustpilotScore ?? null,
      findingCounts,
      lastUpdated: [
        pricing?.snapshotDate,
        reputation?.snapshotDate,
        promo?.snapshotDate,
      ]
        .filter(Boolean)
        .sort()
        .pop() ?? null,
    };
  });

  return NextResponse.json(results);
}
