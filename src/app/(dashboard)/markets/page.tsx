import { db } from "@/db";
import { markets } from "@/db/schema";
import Link from "next/link";
import { Globe } from "lucide-react";
import { EmptyState } from "@/components/shared/empty-state";
import { MARKET_FLAGS } from "@/lib/constants";

export default async function MarketsPage() {
  const allMarkets = await db.select().from(markets);

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
            const flag = MARKET_FLAGS[market.code?.toLowerCase()] ?? "🌐";
            return (
              <Link
                key={market.id}
                href={`/markets/${market.code}`}
                className="block"
              >
                <div
                  className="rounded-xl border border-gray-200 bg-white p-5 text-center hover:border-primary/30 hover:shadow-md active:shadow-sm transition-all cursor-pointer"
                >
                  <div className="text-4xl mb-3">{flag}</div>
                  <p className="text-gray-900 font-semibold text-sm">
                    {market.name}
                  </p>
                  <p className="text-gray-400 text-xs mt-1 uppercase tracking-wider">
                    {market.code}
                  </p>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
