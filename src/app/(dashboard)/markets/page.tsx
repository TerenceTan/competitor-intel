import { db } from "@/db";
import { markets } from "@/db/schema";
import Link from "next/link";

const MARKET_FLAGS: Record<string, string> = {
  sg: "🇸🇬",
  hk: "🇭🇰",
  th: "🇹🇭",
  vn: "🇻🇳",
  id: "🇮🇩",
  my: "🇲🇾",
  jp: "🇯🇵",
  mn: "🇲🇳",
  in: "🇮🇳",
  ph: "🇵🇭",
  tw: "🇹🇼",
  cn: "🇨🇳",
};

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
        <div
          className="rounded-xl border border-gray-200 p-8 text-center text-gray-500 bg-white"
        >
          No markets configured yet.
        </div>
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
                  className="rounded-xl border border-gray-200 bg-white p-5 text-center hover:border-blue-300 hover:shadow-sm transition-all cursor-pointer"
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
