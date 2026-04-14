import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { competitors, promoSnapshots } from "@/db/schema";
import { eq, or, isNull, sql, and, desc } from "drizzle-orm";
import { safeParseJson } from "@/lib/utils";

/**
 * GET /api/v1/promotions
 *
 * External API for retrieving competitor promotions.
 * Authenticated via Bearer API key (validated in middleware).
 *
 * Query parameters:
 *   - competitor: filter by competitor ID (e.g. ?competitor=icmarkets)
 *   - market:     filter by market code (e.g. ?market=global)
 *   - active:     if "true", only return promos marked as active (default: all)
 *   - limit:      max results per competitor (default: 1 = latest snapshot only)
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const competitorFilter = searchParams.get("competitor");
  const marketFilter = searchParams.get("market");
  const activeOnly = searchParams.get("active") === "true";
  const limit = Math.min(Math.max(parseInt(searchParams.get("limit") ?? "1", 10) || 1, 1), 50);

  // Fetch competitors (exclude Pepperstone self-benchmark unless specifically requested)
  const competitorConditions = competitorFilter
    ? [eq(competitors.id, competitorFilter)]
    : [or(eq(competitors.isSelf, 0), isNull(competitors.isSelf))];

  const allCompetitors = await db
    .select()
    .from(competitors)
    .where(and(...competitorConditions));

  if (allCompetitors.length === 0) {
    return NextResponse.json({ data: [], meta: { total: 0 } });
  }

  const competitorMap = Object.fromEntries(allCompetitors.map((c) => [c.id, c]));
  const competitorIds = allCompetitors.map((c) => c.id);

  // Build promo query — get latest N snapshots per competitor
  const promoConditions = [
    sql`${promoSnapshots.competitorId} IN (${sql.join(competitorIds.map((id) => sql`${id}`), sql`, `)})`,
  ];

  if (marketFilter) {
    promoConditions.push(eq(promoSnapshots.marketCode, marketFilter));
  }

  let promoRows;
  if (limit === 1) {
    // Optimized: single latest snapshot per competitor
    promoRows = await db
      .select()
      .from(promoSnapshots)
      .where(
        and(
          ...promoConditions,
          sql`${promoSnapshots.id} IN (
            SELECT MAX(id) FROM promo_snapshots
            WHERE competitor_id IN (${sql.join(competitorIds.map((id) => sql`${id}`), sql`, `)})
            ${marketFilter ? sql`AND market_code = ${marketFilter}` : sql``}
            GROUP BY competitor_id
          )`,
        )
      );
  } else {
    // Multiple snapshots: fetch recent ones and group in JS
    promoRows = await db
      .select()
      .from(promoSnapshots)
      .where(and(...promoConditions))
      .orderBy(desc(promoSnapshots.snapshotDate))
      .limit(limit * competitorIds.length);
  }

  // Parse and structure the response
  const results = promoRows.flatMap((row) => {
    const competitor = competitorMap[row.competitorId];
    if (!competitor) return [];

    const promotions = safeParseJson<Array<Record<string, unknown>>>(
      row.promotionsJson,
      [],
      "promotionsJson"
    );

    const filtered = activeOnly
      ? promotions.filter((p) => {
          const status = String(p.status ?? p.active ?? "").toLowerCase();
          return status === "active" || status === "true" || status === "1";
        })
      : promotions;

    return filtered.map((promo) => ({
      competitorId: row.competitorId,
      competitorName: competitor.name,
      market: row.marketCode,
      snapshotDate: row.snapshotDate,
      ...promo,
    }));
  });

  return NextResponse.json({
    data: results,
    meta: {
      total: results.length,
      competitors: [...new Set(results.map((r) => r.competitorId))].length,
      generatedAt: new Date().toISOString(),
    },
  });
}
