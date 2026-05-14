import { db } from "@/db";
import {
  markets,
  competitors,
  pricingSnapshots,
  promoSnapshots,
  accountTypeSnapshots,
  changeEvents,
  socialSnapshots,
  competitorMarkets,
} from "@/db/schema";
import { eq, sql, desc, and, gte, inArray } from "drizzle-orm";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import {
  AlertTriangle,
  Globe,
  MapPin,
  ArrowLeft,
  TrendingUp,
  Tag,
  LayoutList,
  Activity,
  Shield,
  Users,
} from "lucide-react";
import { MARKET_FLAGS } from "@/lib/constants";
import { safeParseJson } from "@/lib/utils";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { TimeAgo } from "@/components/ui/time-ago";
import { AccountAccordion } from "@/components/shared/account-accordion";
import { EmptyState } from "@/components/shared/empty-state";

/* ------------------------------------------------------------------ */
/*  Sanitise scraper junk values to null                               */
/* ------------------------------------------------------------------ */

const JUNK_RE = /unable to determine|not available|not specified|n\/a/i;

function sanitiseAccounts(accounts: Array<Record<string, unknown>>): Array<Record<string, unknown>> {
  return accounts.map((acc) => {
    const cleaned = { ...acc };
    for (const key of Object.keys(cleaned)) {
      const val = cleaned[key];
      if (typeof val === "string" && JUNK_RE.test(val)) {
        cleaned[key] = null;
      }
    }
    return cleaned;
  });
}

/* ------------------------------------------------------------------ */
/*  Data source badge                                                  */
/* ------------------------------------------------------------------ */

function DataSourceBadge({ isMarketSpecific }: { isMarketSpecific: boolean }) {
  if (isMarketSpecific) {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
        <MapPin className="w-2.5 h-2.5" />
        Market
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-50 text-gray-500 border border-gray-200">
      <Globe className="w-2.5 h-2.5" />
      Global
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Leverage bar — visual bar relative to max across all competitors   */
/* ------------------------------------------------------------------ */

function LeverageBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.max(Math.min((value / max) * 100, 100), 0) : 0;
  return (
    <div className="flex items-center gap-2.5 min-w-[140px]">
      <span className="text-sm font-semibold text-gray-900 font-mono w-12 shrink-0">
        1:{value}
      </span>
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-primary/70"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  KPI mini card for the header row                                   */
/* ------------------------------------------------------------------ */

function MiniKpi({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string | number;
  icon: typeof TrendingUp;
  color: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3">
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${color}`}>
        <Icon className="w-4 h-4" />
      </div>
      <div>
        <p className="text-[11px] text-gray-500 font-medium uppercase tracking-wider leading-tight">
          {label}
        </p>
        <p className="text-lg font-bold text-gray-900 leading-tight mt-0.5">{value}</p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Follower count formatter (Phase 2 Digital Presence section)       */
/* ------------------------------------------------------------------ */

function formatFollowers(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default async function MarketDetailPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const marketCode = code.toLowerCase();

  // Validate market code: alphanumeric only, max 5 chars
  if (!/^[a-z]{2,5}$/.test(marketCode)) notFound();

  const [market] = await db
    .select()
    .from(markets)
    .where(eq(markets.code, marketCode))
    .limit(1);

  if (!market) notFound();

  const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();

  const allCompetitors = await db.select().from(competitors);

  // Fetch all data in parallel
  const [
    marketPricingRows,
    globalPricingRows,
    marketPromoRows,
    globalPromoRows,
    marketAccountRows,
    globalAccountRows,
    recentMarketChanges,
    marketSocialRows,
    globalSocialRows,
    socialZeroResultRows,
    curatedMarketRows,
  ] = await Promise.all([
    db
      .select()
      .from(pricingSnapshots)
      .where(
        sql`${pricingSnapshots.marketCode} = ${marketCode} AND ${pricingSnapshots.id} IN (SELECT MAX(id) FROM pricing_snapshots WHERE market_code = ${marketCode} GROUP BY competitor_id)`
      ),
    db
      .select()
      .from(pricingSnapshots)
      .where(
        sql`${pricingSnapshots.marketCode} = 'global' AND ${pricingSnapshots.id} IN (SELECT MAX(id) FROM pricing_snapshots WHERE market_code = 'global' GROUP BY competitor_id)`
      ),
    db
      .select()
      .from(promoSnapshots)
      .where(
        sql`${promoSnapshots.marketCode} = ${marketCode} AND ${promoSnapshots.id} IN (SELECT MAX(id) FROM promo_snapshots WHERE market_code = ${marketCode} GROUP BY competitor_id)`
      ),
    db
      .select()
      .from(promoSnapshots)
      .where(
        sql`${promoSnapshots.marketCode} = 'global' AND ${promoSnapshots.id} IN (SELECT MAX(id) FROM promo_snapshots WHERE market_code = 'global' GROUP BY competitor_id)`
      ),
    db
      .select()
      .from(accountTypeSnapshots)
      .where(
        sql`${accountTypeSnapshots.marketCode} = ${marketCode} AND ${accountTypeSnapshots.id} IN (SELECT MAX(id) FROM account_type_snapshots WHERE market_code = ${marketCode} GROUP BY competitor_id)`
      ),
    db
      .select()
      .from(accountTypeSnapshots)
      .where(
        sql`${accountTypeSnapshots.marketCode} = 'global' AND ${accountTypeSnapshots.id} IN (SELECT MAX(id) FROM account_type_snapshots WHERE market_code = 'global' GROUP BY competitor_id)`
      ),
    // Recent changes for this market (last 7 days)
    db
      .select()
      .from(changeEvents)
      .where(
        and(
          eq(changeEvents.marketCode, marketCode),
          gte(changeEvents.detectedAt, weekAgo)
        )
      )
      .orderBy(desc(changeEvents.detectedAt))
      .limit(10),
    // Phase 2 — Digital Presence: latest market-specific social snapshot per (competitor, platform)
    // for FB/IG/X only. Mirrors the MAX(id) GROUP BY pattern used for pricing/promos/accounts above.
    db
      .select()
      .from(socialSnapshots)
      .where(
        sql`${socialSnapshots.marketCode} = ${marketCode}
            AND ${socialSnapshots.platform} IN ('facebook','instagram','x')
            AND ${socialSnapshots.id} IN (
              SELECT MAX(id) FROM social_snapshots
              WHERE market_code = ${marketCode}
                AND platform IN ('facebook','instagram','x')
              GROUP BY competitor_id, platform
            )`
      ),
    // Phase 2 — Digital Presence: global fallback pool (RESEARCH.md Pattern 4 / D2-10).
    db
      .select()
      .from(socialSnapshots)
      .where(
        sql`${socialSnapshots.marketCode} = 'global'
            AND ${socialSnapshots.platform} IN ('facebook','instagram','x')
            AND ${socialSnapshots.id} IN (
              SELECT MAX(id) FROM social_snapshots
              WHERE market_code = 'global'
                AND platform IN ('facebook','instagram','x')
              GROUP BY competitor_id, platform
            )`
      ),
    // Phase 2 — Digital Presence: scraper_zero_results within last 7 days for FB/IG/X on THIS
    // market. Used to render the inline "scraper failed" indicator (D2-14 / TRUST-04 carry-forward).
    db
      .select()
      .from(changeEvents)
      .where(
        and(
          eq(changeEvents.fieldName, "scraper_zero_results"),
          eq(changeEvents.marketCode, marketCode),
          gte(changeEvents.detectedAt, weekAgo),
          inArray(changeEvents.domain, ["social_facebook", "social_instagram", "social_x"])
        )
      )
      .orderBy(desc(changeEvents.detectedAt))
      .limit(500),
    // Phase 2.1 — operator-curated SHOW/HIDE list for the current market.
    // Plan 02.1-01 created the table; Plan 02.1-02 (import) and Plan 02.1-04
    // (admin UI) write rows. Default-safe per D2.1-04 / D2.1-05: an empty
    // result here means "marketing has not curated this market yet" — the
    // filter logic below falls back to Phase 2 behavior (show all).
    db
      .select({
        competitorId: competitorMarkets.competitorId,
        status: competitorMarkets.status,
      })
      .from(competitorMarkets)
      .where(eq(competitorMarkets.marketCode, marketCode)),
  ]);

  // Build lookup maps
  const marketPricingMap = new Map(marketPricingRows.map((p) => [p.competitorId, p]));
  const globalPricingMap = new Map(globalPricingRows.map((p) => [p.competitorId, p]));
  const marketAccountMap = new Map(marketAccountRows.map((a) => [a.competitorId, a]));
  const globalAccountMap = new Map(globalAccountRows.map((a) => [a.competitorId, a]));

  // === Phase 2: Social fanout fallback resolution (RESEARCH.md Pattern 4 / D2-10) ===
  type SocialPlatform = "facebook" | "instagram" | "x";
  type SocialCell = {
    followers: number | null;
    postsLast7d: number | null;
    isMarketSpecific: boolean;
  };
  type SocialKey = `${string}|${SocialPlatform}`;

  const socialMap = new Map<SocialKey, SocialCell>();

  // Pass 1: market-specific rows take precedence.
  for (const snap of marketSocialRows) {
    const platform = snap.platform as SocialPlatform;
    if (platform !== "facebook" && platform !== "instagram" && platform !== "x") continue;
    const k: SocialKey = `${snap.competitorId}|${platform}`;
    if (!socialMap.has(k)) {
      socialMap.set(k, {
        followers: snap.followers,
        postsLast7d: snap.postsLast7d,
        isMarketSpecific: true,
      });
    }
  }

  // Pass 2: global fallback — only fill keys NOT already set.
  for (const snap of globalSocialRows) {
    const platform = snap.platform as SocialPlatform;
    if (platform !== "facebook" && platform !== "instagram" && platform !== "x") continue;
    const k: SocialKey = `${snap.competitorId}|${platform}`;
    if (!socialMap.has(k)) {
      socialMap.set(k, {
        followers: snap.followers,
        postsLast7d: snap.postsLast7d,
        isMarketSpecific: false,
      });
    }
  }

  // Per-(competitor, platform) zero-result lookup: a Set of "competitorId|platform"
  // keys for which a scraper_zero_results event was logged for the CURRENT marketCode
  // in the last 7 days. Used to render the inline "scraper failed" indicator.
  const zeroResultKeys = new Set<SocialKey>();
  for (const ev of socialZeroResultRows) {
    // domain shape: 'social_facebook' / 'social_instagram' / 'social_x' (per apify_social.py)
    const platform = ev.domain.replace(/^social_/, "") as SocialPlatform;
    if (platform !== "facebook" && platform !== "instagram" && platform !== "x") continue;
    zeroResultKeys.add(`${ev.competitorId}|${platform}`);
  }

  // Build the table rows: filter to competitors that have ANY data at all
  // (snapshot in either pass OR a recent zero-result event on any platform).
  const socialRows = allCompetitors
    .map((c) => {
      const cells: Record<SocialPlatform, SocialCell | "scraper-failed" | null> = {
        facebook: null,
        instagram: null,
        x: null,
      };
      let hasAnyData = false;
      let anyMarketSpecific = false;
      for (const platform of ["facebook", "instagram", "x"] as const) {
        const k: SocialKey = `${c.id}|${platform}`;
        const cell = socialMap.get(k);
        if (cell) {
          cells[platform] = cell;
          hasAnyData = true;
          if (cell.isMarketSpecific) anyMarketSpecific = true;
        } else if (zeroResultKeys.has(k)) {
          cells[platform] = "scraper-failed";
          hasAnyData = true;
        }
      }
      return { competitor: c, cells, hasAnyData, anyMarketSpecific };
    })
    .filter((r) => r.hasAnyData);

  // Sort: self first, then competitors with any market-specific cell, then tier.
  socialRows.sort((a, b) => {
    const selfA = a.competitor.isSelf ? 1 : 0;
    const selfB = b.competitor.isSelf ? 1 : 0;
    if (selfA !== selfB) return selfB - selfA;
    if (a.anyMarketSpecific !== b.anyMarketSpecific) return a.anyMarketSpecific ? -1 : 1;
    return a.competitor.tier - b.competitor.tier;
  });

  // === Phase 2.1: Operator-curated SHOW/HIDE filter (D2.1-04 / D2.1-05) ===
  // Default-safe rollout: when competitor_markets is EMPTY for this market,
  // the filter is a no-op and behavior matches Phase 2 exactly (show all
  // competitors with social data). When the table has rows for this market,
  // narrow to status='active' — non-active and uncurated competitors hide.
  const curatedActiveIds = new Set(
    curatedMarketRows
      .filter((r) => r.status === "active")
      .map((r) => r.competitorId),
  );
  const hasCuration = curatedMarketRows.length > 0;
  const filteredSocialRows = hasCuration
    ? socialRows.filter((r) => curatedActiveIds.has(r.competitor.id))
    : socialRows;

  // Merge pricing: market-specific takes priority, fallback to global
  const pricingData = allCompetitors.map((c) => {
    const marketSnap = marketPricingMap.get(c.id);
    const globalSnap = globalPricingMap.get(c.id);
    const pricing = marketSnap ?? globalSnap;
    const isMarketSpecific = !!marketSnap;

    let maxLeverage: number | null = null;
    const levRaw = pricing?.leverageJson;
    if (levRaw) {
      const lev = safeParseJson<unknown>(levRaw, null, "leverageJson");
      if (Array.isArray(lev)) {
        const vals = lev
          .map((v: unknown) => {
            if (typeof v === "number") return v;
            if (typeof v === "string" && v.includes(":"))
              return parseInt(v.split(":")[1], 10);
            return NaN;
          })
          .filter((v: number) => !isNaN(v));
        maxLeverage = vals.length > 0 ? Math.max(...vals) : null;
      } else if (typeof lev === "object" && lev !== null) {
        const vals = Object.values(lev)
          .map((v) => {
            if (typeof v === "number") return v;
            if (typeof v === "string" && v.includes(":"))
              return parseInt(v.split(":")[1], 10);
            return NaN;
          })
          .filter((v) => !isNaN(v));
        maxLeverage = vals.length > 0 ? Math.max(...vals) : null;
      }
    }

    const spreadData = safeParseJson<Array<{ account_type?: string; spread_from?: string }>>(
      pricing?.spreadJson,
      [],
      "spreadJson"
    );

    return {
      competitor: c,
      minDepositUsd: pricing?.minDepositUsd ?? null,
      maxLeverage,
      spreadData,
      isMarketSpecific,
      instrumentsCount: pricing?.instrumentsCount ?? null,
    };
  });

  // Sort: Pepperstone (is_self) first, then market-specific, then by tier
  pricingData.sort((a, b) => {
    const selfA = a.competitor.isSelf ? 1 : 0;
    const selfB = b.competitor.isSelf ? 1 : 0;
    if (selfA !== selfB) return selfB - selfA;
    if (a.isMarketSpecific !== b.isMarketSpecific) return a.isMarketSpecific ? -1 : 1;
    return a.competitor.tier - b.competitor.tier;
  });

  // Max leverage for bar scaling
  const allLeverages = pricingData.map((d) => d.maxLeverage ?? 0);
  const globalMaxLev = Math.max(...allLeverages, 1);

  // Promos: market-specific first, then global fallback
  type PromoItem = { competitorId: string; promo: Record<string, unknown>; isMarketSpecific: boolean };
  const marketPromos: PromoItem[] = [];
  const seenPromoCompetitors = new Set<string>();

  for (const snap of marketPromoRows) {
    if (!snap.promotionsJson) continue;
    seenPromoCompetitors.add(snap.competitorId);
    const promos = safeParseJson<Array<Record<string, unknown>>>(snap.promotionsJson, [], "promotionsJson");
    for (const promo of promos) {
      marketPromos.push({ competitorId: snap.competitorId, promo, isMarketSpecific: true });
    }
  }
  for (const snap of globalPromoRows) {
    if (!snap.promotionsJson || seenPromoCompetitors.has(snap.competitorId)) continue;
    const promos = safeParseJson<Array<Record<string, unknown>>>(snap.promotionsJson, [], "promotionsJson");
    for (const promo of promos) {
      marketPromos.push({ competitorId: snap.competitorId, promo, isMarketSpecific: false });
    }
  }

  // Account types: merge market + global, sanitise junk values
  const accountData = allCompetitors
    .map((c) => {
      const marketSnap = marketAccountMap.get(c.id);
      const globalSnap = globalAccountMap.get(c.id);
      const snap = marketSnap ?? globalSnap;
      const isMarketSpecific = !!marketSnap;
      const accounts = sanitiseAccounts(
        safeParseJson<Array<Record<string, unknown>>>(
          snap?.accountsDetailedJson,
          [],
          "accountsDetailedJson"
        )
      );
      return { competitor: c, accounts, isMarketSpecific };
    })
    .filter((d) => d.accounts.length > 0);

  const competitorMap = Object.fromEntries(allCompetitors.map((c) => [c.id, c]));
  const flag = MARKET_FLAGS[marketCode] ?? "\u{1F310}";
  const isChina = marketCode === "cn";

  // Stats
  const marketSpecificCount = pricingData.filter((d) => d.isMarketSpecific).length;
  const totalCompetitors = allCompetitors.length;
  const promoCount = marketPromos.length;
  const changeCount = recentMarketChanges.length;

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Breadcrumb + Back */}
      <div className="flex items-center gap-2 text-sm">
        <Link
          href="/markets"
          className="inline-flex items-center gap-1 text-gray-500 hover:text-primary transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Markets
        </Link>
        <span className="text-gray-300">/</span>
        <span className="text-gray-700 font-medium">{market.name}</span>
      </div>

      {/* Header */}
      <div className="flex items-center gap-4">
        <span className="text-5xl">{flag}</span>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{market.name}</h1>
          <p className="text-gray-500 text-sm mt-0.5 uppercase tracking-wider">
            {market.code}
          </p>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MiniKpi
          label="Data Coverage"
          value={`${marketSpecificCount}/${totalCompetitors}`}
          icon={Shield}
          color={
            totalCompetitors > 0 && marketSpecificCount / totalCompetitors >= 0.7
              ? "bg-emerald-50 text-emerald-600"
              : totalCompetitors > 0 && marketSpecificCount / totalCompetitors >= 0.3
                ? "bg-amber-50 text-amber-600"
                : "bg-gray-100 text-gray-500"
          }
        />
        <MiniKpi
          label="Active Promos"
          value={promoCount}
          icon={Tag}
          color="bg-violet-50 text-violet-600"
        />
        <MiniKpi
          label="Account Types"
          value={accountData.reduce((sum, d) => sum + d.accounts.length, 0)}
          icon={LayoutList}
          color="bg-blue-50 text-blue-600"
        />
        <MiniKpi
          label="Changes (7d)"
          value={changeCount}
          icon={Activity}
          color={changeCount > 0 ? "bg-orange-50 text-orange-600" : "bg-gray-100 text-gray-500"}
        />
      </div>

      {/* China warning */}
      {isChina && (
        <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-200 bg-amber-50">
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-amber-800 font-medium text-sm">Manual monitoring required</p>
            <p className="text-amber-700 text-sm mt-0.5">
              Great Firewall restrictions may prevent automated scraping of Chinese platforms.
            </p>
          </div>
        </div>
      )}

      {/* Market overview */}
      {(market.characteristics || market.platforms) && (
        <Card className="p-5 border-gray-200 bg-white">
          <h2 className="text-sm font-semibold text-gray-900 mb-3">Market Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {market.characteristics && (
              <div>
                <p className="text-gray-500 text-[11px] uppercase tracking-wider mb-1.5 font-medium">
                  Characteristics
                </p>
                <p className="text-gray-700 text-sm leading-relaxed">
                  {market.characteristics}
                </p>
              </div>
            )}
            {market.platforms && (
              <div>
                <p className="text-gray-500 text-[11px] uppercase tracking-wider mb-1.5 font-medium">
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

      {/* Pricing comparison — leverage as visual bar */}
      <section>
        <h2 className="text-base font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-gray-400" />
          Pricing Comparison
        </h2>
        <div className="rounded-xl border border-gray-200 overflow-x-auto bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50/80">
                <th className="text-left px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider">
                  Broker
                </th>
                <th className="text-left px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider w-10">
                  Source
                </th>
                <th className="text-left px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider">
                  Max Leverage
                </th>
                <th className="text-left px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider">
                  Min Deposit
                </th>
                <th className="text-left px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider">
                  Spread From
                </th>
                <th className="text-right px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider">
                  Instruments
                </th>
              </tr>
            </thead>
            <tbody>
              {pricingData.map(
                ({ competitor, minDepositUsd, maxLeverage, spreadData, isMarketSpecific, instrumentsCount }, idx) => {
                  const lowestSpread =
                    spreadData.length > 0
                      ? spreadData
                          .map((s) => s.spread_from)
                          .filter(Boolean)
                          .sort()[0]
                      : null;

                  const isSelf = !!competitor.isSelf;

                  return (
                    <tr
                      key={competitor.id}
                      className={`border-b border-gray-100 transition-colors ${
                        idx === pricingData.length - 1 ? "border-b-0" : ""
                      } ${isSelf ? "bg-primary/[0.03]" : "hover:bg-gray-50/60"}`}
                    >
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/competitors/${competitor.id}`}
                            className={`font-medium transition-colors ${
                              isSelf
                                ? "text-primary font-semibold"
                                : "text-gray-900 hover:text-primary"
                            }`}
                          >
                            {competitor.name}
                          </Link>
                          {isSelf && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-primary/10 text-primary">
                              US
                            </span>
                          )}
                          <span className="text-gray-400 text-[11px]">T{competitor.tier}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5">
                        <DataSourceBadge isMarketSpecific={isMarketSpecific} />
                      </td>
                      <td className="px-4 py-2.5">
                        {maxLeverage != null ? (
                          <LeverageBar value={maxLeverage} max={globalMaxLev} />
                        ) : (
                          <span className="text-gray-300 text-xs">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-sm">
                        {minDepositUsd != null ? (
                          minDepositUsd === 0 ? (
                            <span className="text-emerald-600 font-medium">$0</span>
                          ) : (
                            <span className="text-gray-700">${minDepositUsd.toLocaleString()}</span>
                          )
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-gray-700 font-mono text-xs">
                        {lowestSpread ?? <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-2.5 text-right text-gray-700 font-mono text-sm">
                        {instrumentsCount != null ? (
                          instrumentsCount.toLocaleString()
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                    </tr>
                  );
                }
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* === Phase 2: Digital Presence === */}
      {/* Phase 2.1 (D2.1-04 / D2.1-05): filteredSocialRows narrows the Phase 2
          resolver output (socialRows) by the operator-curated active list.
          When competitor_markets is empty for this market, filteredSocialRows
          === socialRows (default-safe). Both consts remain visible to make
          the filter explicitly additive. */}
      <section>
        <h2 className="text-base font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Users className="w-4 h-4 text-gray-400" />
          Digital Presence
          {filteredSocialRows.length > 0 && (
            <span className="text-xs font-normal text-gray-400">
              {filteredSocialRows.length} {filteredSocialRows.length === 1 ? "broker" : "brokers"}
            </span>
          )}
        </h2>

        {filteredSocialRows.length === 0 ? (
          <EmptyState
            title="No social data yet for this market"
            description="Check back after the next Apify run, or use the global view from the broker profile."
          />
        ) : (
          <div className="rounded-xl border border-gray-200 bg-white overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50/60 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider">Broker</th>
                  <th className="text-left px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider w-10">Source</th>
                  <th className="text-left px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider">Facebook</th>
                  <th className="text-left px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider">Instagram</th>
                  <th className="text-left px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider">X</th>
                </tr>
              </thead>
              <tbody>
                {filteredSocialRows.map(({ competitor, cells, anyMarketSpecific }, idx) => {
                  const isSelf = !!competitor.isSelf;
                  return (
                    <tr
                      key={competitor.id}
                      className={`border-b border-gray-100 transition-colors ${
                        idx === filteredSocialRows.length - 1 ? "border-b-0" : ""
                      } ${isSelf ? "bg-primary/[0.03]" : "hover:bg-gray-50/60"}`}
                    >
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/competitors/${competitor.id}?market=${marketCode}`}
                            className={`font-medium transition-colors ${
                              isSelf ? "text-primary font-semibold" : "text-gray-900 hover:text-primary"
                            }`}
                          >
                            {competitor.name}
                          </Link>
                          {isSelf && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-primary/10 text-primary">
                              US
                            </span>
                          )}
                          <span className="text-gray-400 text-[11px]">T{competitor.tier}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5">
                        <DataSourceBadge isMarketSpecific={anyMarketSpecific} />
                      </td>
                      {(["facebook", "instagram", "x"] as const).map((platform) => {
                        const cell = cells[platform];
                        return (
                          <td key={platform} className="px-4 py-2.5 font-mono text-xs">
                            {cell === "scraper-failed" ? (
                              <span className="inline-flex items-center gap-1 text-red-600 text-[11px]">
                                <span className="w-1.5 h-1.5 rounded-full bg-red-500" aria-hidden />
                                scraper failed
                              </span>
                            ) : cell == null ? (
                              <span className="text-gray-300">—</span>
                            ) : (
                              <span className="text-gray-700">
                                {formatFollowers(cell.followers)}
                                {cell.postsLast7d != null && (
                                  <span className="text-gray-400"> · {cell.postsLast7d}p</span>
                                )}
                              </span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Two-column: Account Types + Recent Changes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Account types — collapsible accordion */}
        {accountData.length > 0 && (
          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <LayoutList className="w-4 h-4 text-gray-400" />
              Account Types
            </h2>
            <AccountAccordion
              items={accountData.map(({ competitor, accounts, isMarketSpecific }) => ({
                competitorId: competitor.id,
                competitorName: competitor.name,
                accounts,
                isMarketSpecific,
                badge: <DataSourceBadge isMarketSpecific={isMarketSpecific} />,
              }))}
            />
          </section>
        )}

        {/* Recent changes */}
        <section>
          <h2 className="text-base font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-gray-400" />
            Recent Changes
            {changeCount > 0 && (
              <span className="text-xs font-normal text-gray-400">last 7 days</span>
            )}
          </h2>
          {recentMarketChanges.length === 0 ? (
            <Card className="p-6 border-gray-200 bg-white text-center">
              <p className="text-gray-400 text-sm">No market-specific changes detected yet.</p>
              <p className="text-gray-400 text-xs mt-1">
                Changes will appear here after running market-specific scrapers.
              </p>
            </Card>
          ) : (
            <Card className="border-gray-200 bg-white divide-y divide-gray-100">
              {recentMarketChanges.map((change) => {
                const comp = competitorMap[change.competitorId];
                return (
                  <div key={change.id} className="px-4 py-3 flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-sm font-medium text-gray-900">
                          {comp?.name ?? change.competitorId}
                        </span>
                        <SeverityBadge severity={change.severity} />
                      </div>
                      <p className="text-xs text-gray-600 truncate">
                        <span className="text-gray-400">{change.domain}/{change.fieldName}:</span>{" "}
                        {change.newValue}
                      </p>
                    </div>
                    <span className="text-[11px] text-gray-400 shrink-0">
                      <TimeAgo dateStr={change.detectedAt} />
                    </span>
                  </div>
                );
              })}
            </Card>
          )}
        </section>
      </div>

      {/* Active promotions */}
      <section>
        <h2 className="text-base font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Tag className="w-4 h-4 text-gray-400" />
          Active Promotions
          {promoCount > 0 && (
            <span className="text-xs font-normal text-gray-400">
              {promoCount} found
            </span>
          )}
        </h2>

        {promoCount === 0 ? (
          <Card className="p-6 border-gray-200 bg-white text-center">
            <p className="text-gray-400 text-sm">No promotions found for this market.</p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {marketPromos.slice(0, 12).map(({ competitorId, promo, isMarketSpecific }, i) => {
              const competitor = competitorMap[competitorId];
              const title = String(promo.title ?? promo.name ?? `Promo ${i + 1}`);
              const offerValue = promo.offer_value ?? promo.value ?? null;
              const expiry = promo.expiry ?? null;
              const promoType = promo.type ? String(promo.type).replace(/_/g, " ") : null;
              const sourceUrl = promo.source_url ? String(promo.source_url) : null;

              return (
                <Card
                  key={i}
                  className="p-4 border-gray-200 bg-white hover:shadow-sm transition-shadow"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-1.5">
                      <Link
                        href={`/competitors/${competitorId}`}
                        className="text-xs font-semibold text-primary hover:text-primary/80 transition-colors"
                      >
                        {competitor?.name ?? competitorId}
                      </Link>
                      <DataSourceBadge isMarketSpecific={isMarketSpecific} />
                    </div>
                    {offerValue != null && (
                      <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-green-50 text-green-700 border border-green-200">
                        {String(offerValue)}
                      </span>
                    )}
                  </div>
                  <p className="text-gray-900 font-medium text-sm leading-snug">{title}</p>
                  <div className="flex items-center gap-2 mt-2">
                    {promoType && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-600 capitalize">
                        {promoType}
                      </span>
                    )}
                    {expiry != null && (
                      <span className="text-gray-400 text-[11px]">Exp: {String(expiry)}</span>
                    )}
                  </div>
                  {sourceUrl && (
                    <a
                      href={sourceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] mt-2 inline-block text-primary hover:text-primary/80 transition-colors"
                    >
                      View source &rarr;
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
