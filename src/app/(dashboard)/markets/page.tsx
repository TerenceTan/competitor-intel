import { db } from "@/db";
import { markets, pricingSnapshots, competitors } from "@/db/schema";
import { sql } from "drizzle-orm";
import Link from "next/link";
import { Globe } from "lucide-react";
import { EmptyState } from "@/components/shared/empty-state";
import { MARKET_FLAGS } from "@/lib/constants";

export default async function MarketsPage() {
  const [allMarkets, allCompetitors, marketCoverage] = await Promise.all([
    db.select().from(markets),
    db.select().from(competitors),
    // Count distinct competitors with market-specific pricing data per market_code
    db
      .select({
        marketCode: pricingSnapshots.marketCode,
        competitorCount: sql<number>`COUNT(DISTINCT ${pricingSnapshots.competitorId})`,
      })
      .from(pricingSnapshots)
      .where(sql`${pricingSnapshots.marketCode} != 'global'`)
      .groupBy(pricingSnapshots.marketCode),
  ]);

  const totalCompetitors = allCompetitors.length;
  const coverageMap = new Map(
    marketCoverage.map((r) => [r.marketCode, r.competitorCount])
  );

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Markets</h1>
        <p className="text-gray-500 text-sm mt-1">
          APAC and global markets tracked by Pepperstone — click a market to
          see competitor activity
        </p>
      </div>

      {allMarkets.length === 0 ? (
        <EmptyState
          icon={Globe}
          title="No markets configured"
          description="Markets will appear here once configured in the database."
        />
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {allMarkets.map((market) => {
            const flag = MARKET_FLAGS[market.code?.toLowerCase()] ?? "\u{1F310}";
            const coverage = coverageMap.get(market.code?.toLowerCase()) ?? 0;
            const pct = totalCompetitors > 0 ? (coverage / totalCompetitors) * 100 : 0;
            const coverageColor =
              pct >= 70
                ? "text-emerald-600 bg-emerald-50"
                : pct >= 30
                  ? "text-amber-600 bg-amber-50"
                  : "text-gray-400 bg-gray-50";

            return (
              <Link
                key={market.id}
                href={`/markets/${market.code}`}
                className="block"
              >
                <div className="rounded-xl border border-gray-200 bg-white p-5 text-center hover:border-primary/30 hover:shadow-md active:shadow-sm transition-all cursor-pointer">
                  <div className="text-4xl mb-3">{flag}</div>
                  <p className="text-gray-900 font-semibold text-sm">
                    {market.name}
                  </p>
                  <p className="text-gray-400 text-xs mt-1 uppercase tracking-wider">
                    {market.code}
                  </p>
                  {/* Coverage indicator */}
                  <div className="mt-2.5">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${coverageColor}`}
                    >
                      {coverage}/{totalCompetitors} scraped
                    </span>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
