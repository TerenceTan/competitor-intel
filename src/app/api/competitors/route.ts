import { NextResponse } from "next/server";
import { db } from "@/db";
import {
  competitors,
  pricingSnapshots,
  reputationSnapshots,
  promoSnapshots,
  aiInsights,
} from "@/db/schema";
import { desc, eq, ne, or, isNull } from "drizzle-orm";

export async function GET() {
  const allCompetitors = await db
    .select()
    .from(competitors)
    .where(or(eq(competitors.isSelf, 0), isNull(competitors.isSelf)));

  const results = await Promise.all(
    allCompetitors.map(async (competitor) => {
      // Latest pricing snapshot
      const [pricing] = await db
        .select()
        .from(pricingSnapshots)
        .where(eq(pricingSnapshots.competitorId, competitor.id))
        .orderBy(desc(pricingSnapshots.snapshotDate), desc(pricingSnapshots.id))
        .limit(1);

      // Latest reputation snapshot
      const [reputation] = await db
        .select()
        .from(reputationSnapshots)
        .where(eq(reputationSnapshots.competitorId, competitor.id))
        .orderBy(desc(reputationSnapshots.snapshotDate), desc(reputationSnapshots.id))
        .limit(1);

      // Latest promo snapshot — count promos
      const [promo] = await db
        .select()
        .from(promoSnapshots)
        .where(eq(promoSnapshots.competitorId, competitor.id))
        .orderBy(desc(promoSnapshots.snapshotDate), desc(promoSnapshots.id))
        .limit(1);

      let promoCount = 0;
      if (promo?.promotionsJson) {
        try {
          const parsed = JSON.parse(promo.promotionsJson);
          promoCount = Array.isArray(parsed) ? parsed.length : 0;
        } catch {}
      }

      // Latest AI insight
      const [insight] = await db
        .select()
        .from(aiInsights)
        .where(eq(aiInsights.competitorId, competitor.id))
        .orderBy(desc(aiInsights.generatedAt))
        .limit(1);

      // Max leverage from latest pricing — values stored as "1:1000" strings
      let maxLeverage: number | null = null;
      if (pricing?.leverageJson) {
        try {
          const lev = JSON.parse(pricing.leverageJson);
          if (typeof lev === "object" && lev !== null) {
            const vals = Object.values(lev)
              .map((v) => {
                if (typeof v === "number") return v;
                if (typeof v === "string" && v.includes(":")) return parseInt(v.split(":")[1], 10);
                return NaN;
              })
              .filter((v) => !isNaN(v));
            maxLeverage = vals.length > 0 ? Math.max(...vals) : null;
          }
        } catch {}
      }

      return {
        id: competitor.id,
        name: competitor.name,
        tier: competitor.tier,
        website: competitor.website,
        maxLeverage,
        minDepositUsd: pricing?.minDepositUsd ?? null,
        instrumentsCount: pricing?.instrumentsCount ?? null,
        promoCount,
        trustpilotScore: reputation?.trustpilotScore ?? null,
        latestInsightSummary: insight?.summary ?? null,
        latestInsightDate: insight?.generatedAt ?? null,
        lastUpdated: [
          pricing?.snapshotDate,
          reputation?.snapshotDate,
          promo?.snapshotDate,
        ]
          .filter(Boolean)
          .sort()
          .pop() ?? null,
      };
    })
  );

  return NextResponse.json(results);
}
