import { db } from "@/db";
import {
  markets,
  competitors,
  pricingSnapshots,
  promoSnapshots,
} from "@/db/schema";
import { desc, eq } from "drizzle-orm";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { AlertTriangle } from "lucide-react";

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

export default async function MarketDetailPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;

  const [market] = await db
    .select()
    .from(markets)
    .where(eq(markets.code, code.toLowerCase()))
    .limit(1);

  if (!market) notFound();

  const allCompetitors = await db.select().from(competitors);

  // Get latest pricing for each competitor
  const pricingData = await Promise.all(
    allCompetitors.map(async (c) => {
      const [pricing] = await db
        .select()
        .from(pricingSnapshots)
        .where(eq(pricingSnapshots.competitorId, c.id))
        .orderBy(desc(pricingSnapshots.snapshotDate), desc(pricingSnapshots.id))
        .limit(1);

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
        competitor: c,
        minDepositUsd: pricing?.minDepositUsd ?? null,
        maxLeverage,
      };
    })
  );

  // Get latest promo snapshot per competitor and collect all promotions
  type PromoItem = { competitorId: string; promo: Record<string, unknown> };
  const marketPromos: PromoItem[] = [];

  await Promise.all(
    allCompetitors.map(async (c) => {
      const [snap] = await db
        .select()
        .from(promoSnapshots)
        .where(eq(promoSnapshots.competitorId, c.id))
        .orderBy(desc(promoSnapshots.snapshotDate), desc(promoSnapshots.id))
        .limit(1);
      if (!snap?.promotionsJson) return;
      try {
        const promos: Array<Record<string, unknown>> = JSON.parse(snap.promotionsJson);
        for (const promo of promos) {
          marketPromos.push({ competitorId: c.id, promo });
        }
      } catch {}
    })
  );

  const competitorMap = Object.fromEntries(allCompetitors.map((c) => [c.id, c]));
  const flag = MARKET_FLAGS[code.toLowerCase()] ?? "🌐";
  const isChina = code.toLowerCase() === "cn";

  return (
    <div className="space-y-8 max-w-6xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <span className="text-5xl">{flag}</span>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{market.name}</h1>
          <p className="text-gray-500 text-sm uppercase tracking-wider mt-1">
            {market.code}
          </p>
        </div>
      </div>

      {/* China warning */}
      {isChina && (
        <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-200 bg-amber-50">
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-amber-800 font-medium text-sm">
              Manual monitoring required
            </p>
            <p className="text-amber-700 text-sm mt-0.5">
              Great Firewall restrictions may prevent automated scraping of
              Chinese platforms. Data must be collected manually or via VPN.
            </p>
          </div>
        </div>
      )}

      {/* Market overview */}
      {(market.characteristics || market.platforms) && (
        <Card
          className="p-6 border-gray-200 bg-white"
        >
          <h2 className="text-gray-900 font-semibold mb-4">Market Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {market.characteristics && (
              <div>
                <p className="text-gray-500 text-xs uppercase tracking-wider mb-2">
                  Characteristics
                </p>
                <p className="text-gray-700 text-sm leading-relaxed">
                  {market.characteristics}
                </p>
              </div>
            )}
            {market.platforms && (
              <div>
                <p className="text-gray-500 text-xs uppercase tracking-wider mb-2">
                  Key Platforms
                </p>
                <p className="text-gray-700 text-sm leading-relaxed">
                  {market.platforms}
                </p>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Pricing comparison */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Competitor Pricing Comparison
        </h2>
        <div
          className="rounded-xl border border-gray-200 overflow-x-auto bg-white"
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Competitor
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Tier
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Min Deposit
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Max Leverage
                </th>
              </tr>
            </thead>
            <tbody>
              {pricingData.map(({ competitor, minDepositUsd, maxLeverage }, idx) => (
                <tr
                  key={competitor.id}
                  className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${
                    idx === pricingData.length - 1 ? "border-b-0" : ""
                  }`}
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/competitors/${competitor.id}`}
                      className="hover:underline font-medium"
                      style={{ color: "#0064FA" }}
                    >
                      {competitor.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    Tier {competitor.tier}
                  </td>
                  <td className="px-4 py-3 text-gray-700 font-mono">
                    {minDepositUsd != null
                      ? `$${minDepositUsd.toLocaleString()}`
                      : <span className="text-gray-400">—</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-700 font-mono">
                    {maxLeverage != null
                      ? `1:${maxLeverage}`
                      : <span className="text-gray-400">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Active promotions */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Active Promotions
          {marketPromos.length > 0 && (
            <span className="text-gray-500 font-normal text-sm ml-2">
              ({marketPromos.length} found)
            </span>
          )}
        </h2>

        {marketPromos.length === 0 ? (
          <div
            className="rounded-xl border border-gray-200 p-6 text-center text-gray-500 bg-white"
          >
            No promotions found. Run the promo scraper to populate data.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {marketPromos.slice(0, 12).map(({ competitorId, promo }, i) => {
              const competitor = competitorMap[competitorId];
              const title = String(promo.title ?? promo.name ?? `Promo ${i + 1}`);
              const offerValue = promo.offer_value ?? promo.value ?? null;
              const expiry = promo.expiry ?? null;
              const sourceUrl = promo.source_url ? String(promo.source_url) : null;

              return (
                <Card
                  key={i}
                  className="p-5 border-gray-200 bg-white"
                >
                  <div className="flex items-start justify-between mb-2">
                    <Link
                      href={`/competitors/${competitorId}`}
                      className="text-sm font-semibold hover:underline"
                      style={{ color: "#0064FA" }}
                    >
                      {competitor?.name ?? competitorId}
                    </Link>
                    {offerValue != null && (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-200">
                        {String(offerValue)}
                      </span>
                    )}
                  </div>
                  <p className="text-gray-900 font-medium text-sm">{title}</p>
                  {expiry != null && (
                    <p className="text-gray-500 text-xs mt-1">Expires: {String(expiry)}</p>
                  )}
                  {sourceUrl && (
                    <a
                      href={sourceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs mt-2 inline-block hover:underline"
                      style={{ color: "#0064FA" }}
                    >
                      View source →
                    </a>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
