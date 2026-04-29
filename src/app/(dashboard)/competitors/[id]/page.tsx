import { db } from "@/db";
import {
  competitors,
  aiInsights,
  pricingSnapshots,
  promoSnapshots,
  socialSnapshots,
  reputationSnapshots,
  appStoreSnapshots,
  newsItems,
  changeEvents,
  wikifxSnapshots,
  accountTypeSnapshots,
} from "@/db/schema";
import { and, desc, eq } from "drizzle-orm";
import { notFound } from "next/navigation";
import { parseMarketParam, MARKET_NAMES } from "@/lib/markets";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import { Card } from "@/components/ui/card";
import { timeAgo, formatDate, formatDateTime, tierLabel, extractMaxLeverage, safeParseJson } from "@/lib/utils";
import { CompetitorChangeTable } from "./change-table";
import { ReputationRadar } from "@/components/charts/reputation-radar";
import { SocialBarChart } from "@/components/charts/social-bar-chart";
import { EmptyState } from "@/components/shared/empty-state";
import { SeverityDonut } from "@/components/charts/severity-donut";
import { SeverityCards } from "@/components/ai-overview/severity-cards";
import { FindingRow } from "@/components/ai-overview/finding-row";
import { ActionsKanban } from "@/components/ai-overview/actions-kanban";
import { CollapsibleText } from "@/components/ai-overview/collapsible-text";
import { Lightbulb, Target } from "lucide-react";

/** Display a data value or "—" for missing/junk. Catches nulls, empty strings, and verbose fallback text. */
function displayValue(val: string | null | undefined): string {
  if (val == null) return "—";
  const s = val.trim();
  if (!s || s === "-" || s === "--" || s === "—") return "—";
  if (/^(unable to|not (available|specified|mentioned|found|provided)|n\/?a|unknown|none|varies|see |contact |check |no (data|info))$/i.test(s)) return "—";
  return s;
}

function SentimentBadge({ sentiment }: { sentiment: string | null }) {
  const colorMap: Record<string, string> = {
    positive: "bg-green-50 text-green-700 border-green-200",
    neutral: "bg-gray-100 text-gray-600 border-gray-200",
    negative: "bg-red-50 text-red-700 border-red-200",
  };
  const s = sentiment?.toLowerCase() ?? "neutral";
  const cls = colorMap[s] ?? colorMap.neutral;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}
    >
      {s}
    </span>
  );
}

import { PLATFORMS } from "@/lib/constants";

export default async function CompetitorDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ market?: string }>;
}) {
  const { id } = await params;
  const sp = await searchParams;
  const market = parseMarketParam(sp.market);

  const [competitor] = await db
    .select()
    .from(competitors)
    .where(eq(competitors.id, id))
    .limit(1);

  if (!competitor) notFound();

  // Fetch all data in parallel
  const [
    latestInsight,
    latestPricing,
    latestPromo,
    socialData,
    latestReputation,
    news,
    changes,
    latestWikifx,
    latestAccountTypes,
  ] = await Promise.all([
    db
      .select()
      .from(aiInsights)
      .where(eq(aiInsights.competitorId, id))
      .orderBy(desc(aiInsights.generatedAt), desc(aiInsights.id))
      .limit(1)
      .then((r) => r[0] ?? null),

    db
      .select()
      .from(pricingSnapshots)
      .where(eq(pricingSnapshots.competitorId, id))
      .orderBy(desc(pricingSnapshots.snapshotDate), desc(pricingSnapshots.id))
      .limit(1)
      .then((r) => r[0] ?? null),

    db
      .select()
      .from(promoSnapshots)
      .where(and(
        eq(promoSnapshots.competitorId, id),
        ...(market ? [eq(promoSnapshots.marketCode, market)] : []),
      ))
      .orderBy(desc(promoSnapshots.snapshotDate), desc(promoSnapshots.id))
      .limit(1)
      .then((r) => r[0] ?? null),

    db
      .select()
      .from(socialSnapshots)
      .where(eq(socialSnapshots.competitorId, id))
      .orderBy(desc(socialSnapshots.snapshotDate), desc(socialSnapshots.id)),

    db
      .select()
      .from(reputationSnapshots)
      .where(eq(reputationSnapshots.competitorId, id))
      .orderBy(desc(reputationSnapshots.snapshotDate), desc(reputationSnapshots.id))
      .limit(1)
      .then((r) => r[0] ?? null),

    db
      .select()
      .from(newsItems)
      .where(eq(newsItems.competitorId, id))
      .orderBy(desc(newsItems.publishedAt))
      .limit(20),

    db
      .select()
      .from(changeEvents)
      .where(eq(changeEvents.competitorId, id))
      .orderBy(desc(changeEvents.detectedAt))
      .limit(50),

    db
      .select()
      .from(wikifxSnapshots)
      .where(eq(wikifxSnapshots.competitorId, id))
      .orderBy(desc(wikifxSnapshots.snapshotDate), desc(wikifxSnapshots.id))
      .limit(1)
      .then((r) => r[0] ?? null),

    db
      .select()
      .from(accountTypeSnapshots)
      .where(eq(accountTypeSnapshots.competitorId, id))
      .orderBy(desc(accountTypeSnapshots.snapshotDate), desc(accountTypeSnapshots.id))
      .limit(1)
      .then((r) => r[0] ?? null),
  ]);

  // Per-market App Store ratings for the iOS card.
  // When a market is selected, fetch the latest rating in that storefront;
  // otherwise leave the global iosRating from reputation_snapshots.
  const appStoreRows = await db
    .select()
    .from(appStoreSnapshots)
    .where(and(
      eq(appStoreSnapshots.competitorId, id),
      ...(market ? [eq(appStoreSnapshots.marketCode, market)] : []),
    ))
    .orderBy(desc(appStoreSnapshots.snapshotDate), desc(appStoreSnapshots.id))
    .limit(market ? 5 : 30);
  const marketAppStoreRating = market
    ? (appStoreRows[0]?.iosRating ?? null)
    : null;
  const marketAppStoreReviews = market
    ? (appStoreRows[0]?.iosRatingCount ?? null)
    : null;

  // Parse JSON fields
  let keyFindings: Array<{ finding: string; severity: string; evidence?: string }> = [];
  let actions: Array<{ action: string; urgency: string }> = [];
  let accountTypes: Array<Record<string, unknown>> = [];
  let promotions: Array<Record<string, unknown>> = [];
  let fundingMethods: string[] = [];
  let entitiesBreakdown: Array<{
    label: string;
    trustpilot_score: number | null;
    trustpilot_count: number | null;
    fpa_rating?: number | null;
    ios_rating: number | null;
    android_rating: number | null;
    myfxbook_rating?: number | null;
  }> = [];
  let wikifxAccounts: Array<{
    name?: string;
    spread_from?: string;
    max_leverage?: string;
    min_deposit?: string;
    currency?: string;
    instruments?: string;
  }> = [];
  let marketingStrategy: Array<{ title: string; description: string }> = [];
  let bizArea: string[] = [];
  let detailedAccounts: Array<{
    account_name?: string;
    account_category?: string;
    min_deposit?: string;
    spread_from?: string;
    spread_type?: string;
    commission?: string;
    commission_structure?: string;
    max_leverage?: string;
    execution_type?: string;
    min_lot_size?: string;
    max_lot_size?: string;
    platforms?: string[];
    base_currencies?: string[];
    margin_call_pct?: string;
    stop_out_pct?: string;
    swap_free_available?: boolean;
    negative_balance_protection?: boolean;
    instruments_count?: string;
    target_audience?: string;
    notes?: string;
  }> = [];

  keyFindings = safeParseJson(latestInsight?.keyFindingsJson, [], "keyFindingsJson");
  actions = safeParseJson(latestInsight?.actionsJson, [], "actionsJson");
  accountTypes = safeParseJson(latestPricing?.accountTypesJson, [], "accountTypesJson");
  promotions = safeParseJson(latestPromo?.promotionsJson, [], "promotionsJson");
  fundingMethods = safeParseJson(latestPricing?.fundingMethodsJson, [], "fundingMethodsJson");
  entitiesBreakdown = safeParseJson(latestReputation?.entitiesBreakdownJson, [], "entitiesBreakdownJson");
  wikifxAccounts = safeParseJson(latestWikifx?.accountsJson, [], "accountsJson");
  marketingStrategy = safeParseJson(latestWikifx?.marketingStrategyJson, [], "marketingStrategyJson");
  bizArea = safeParseJson(latestWikifx?.bizAreaJson, [], "bizAreaJson");
  detailedAccounts = safeParseJson(latestAccountTypes?.accountsDetailedJson, [], "accountsDetailedJson");

  // Derive min deposit and max leverage from WikiFX accounts if available
  let wikifxMinDeposit: string | null = null;
  let wikifxMaxLeverage: string | null = null;
  if (wikifxAccounts.length > 0) {
    const deposits = wikifxAccounts
      .map((a) => a.min_deposit)
      .filter((v): v is string => !!v && /[\d]/.test(v));
    if (deposits.length > 0) wikifxMinDeposit = deposits[0];
    const leverages = wikifxAccounts
      .map((a) => a.max_leverage)
      .filter((v): v is string => !!v && /[\d]/.test(v));
    if (leverages.length > 0) wikifxMaxLeverage = leverages[0];
  }

  // Build social map (latest per platform). When a market is selected, prefer
  // a per-market snapshot if one exists; otherwise fall back to the global row.
  const socialMap: Record<string, typeof socialData[0]> = {};
  if (market) {
    for (const snap of socialData) {
      if (snap.marketCode === market && !socialMap[snap.platform]) {
        socialMap[snap.platform] = snap;
      }
    }
  }
  for (const snap of socialData) {
    if (!socialMap[snap.platform] && snap.marketCode === "global") {
      socialMap[snap.platform] = snap;
    }
  }
  // Track which platforms came from a per-market override so the UI can label them
  const socialMarketOverride: Record<string, boolean> = {};
  for (const platform of Object.keys(socialMap)) {
    socialMarketOverride[platform] = market != null && socialMap[platform].marketCode === market;
  }

  const tierColors: Record<number, string> = {
    1: "bg-blue-50 text-blue-700 border-blue-200",
    2: "bg-indigo-50 text-indigo-700 border-indigo-200",
    3: "bg-gray-100 text-gray-600 border-gray-200",
  };
  const tierCls = tierColors[competitor.tier] ?? tierColors[3];

  return (
    <div className="space-y-8 max-w-6xl">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-bold text-gray-900">{competitor.name}</h1>
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${tierCls}`}
            >
              {tierLabel(competitor.tier)}
            </span>
          </div>
          <a
            href={competitor.website}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-gray-500 hover:text-primary transition-colors"
          >
            {competitor.website}
          </a>
          {market && (
            <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
              <span className="h-1.5 w-1.5 rounded-full bg-primary" />
              Promos, App Store, social: {MARKET_NAMES[market]}
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList className="bg-gray-100 border border-gray-200 h-auto p-1 w-full flex">
          {[
            { value: "overview", label: "AI Overview" },
            { value: "pricing", label: "Pricing" },
            { value: "promotions", label: "Promotions" },
            { value: "digital", label: "Digital Presence" },
            { value: "reputation", label: "Reputation" },
            { value: "changes", label: "Change History" },
          ].map((tab) => (
            <TabsTrigger
              key={tab.value}
              value={tab.value}
              className="flex-1 text-xs"
            >
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Tab 1: AI Overview */}
        <TabsContent value="overview" className="mt-6 space-y-5">
          {!latestInsight ? (
            <EmptyState
              icon={Lightbulb}
              title="No AI insights generated yet"
              description="Run the AI analyzer to generate competitive intelligence for this broker."
            />
          ) : (() => {
            const severityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
            const sortedFindings = [...keyFindings].sort(
              (a, b) => (severityOrder[a.severity?.toLowerCase()] ?? 4) - (severityOrder[b.severity?.toLowerCase()] ?? 4)
            );

            const severityKeys = ["critical", "high", "medium", "low"] as const;
            const severityLabels: Record<string, string> = { critical: "Critical", high: "High", medium: "Medium", low: "Low" };
            const severityHex: Record<string, string> = { critical: "#ef4444", high: "#f97316", medium: "#f59e0b", low: "#3b82f6" };

            const severityCounts: Record<string, number> = {};
            for (const k of severityKeys) {
              severityCounts[k] = keyFindings.filter((f) => f.severity?.toLowerCase() === k).length;
            }

            const severityDonutData = severityKeys
              .filter((k) => severityCounts[k] > 0)
              .map((k) => ({
                label: severityLabels[k],
                count: severityCounts[k],
                color: severityHex[k],
              }));

            const urgencyDonutData = [
              { key: "immediate", label: "Immediate", color: "#ef4444" },
              { key: "this_week", label: "This Week", color: "#f97316" },
              { key: "this_month", label: "This Month", color: "#3b82f6" },
            ].map((u) => ({
              label: u.label,
              count: actions.filter((a) => a.urgency?.toLowerCase() === u.key).length,
              color: u.color,
            }));

            return (
              <>
                {/* Row 1: Severity stat cards */}
                <SeverityCards counts={severityCounts} />
                <p className="text-xs text-gray-400 text-right -mt-3">
                  Generated {timeAgo(latestInsight.generatedAt)}
                </p>

                {/* Row 2: Donut charts */}
                {(keyFindings.length > 0 || actions.length > 0) && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {keyFindings.length > 0 && (
                      <Card className="p-5 border-gray-200 bg-white">
                        <p className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-3">Findings by Severity</p>
                        <SeverityDonut
                          data={severityDonutData}
                          centerLabel="findings"
                          centerValue={keyFindings.length}
                        />
                      </Card>
                    )}
                    {actions.length > 0 && (
                      <Card className="p-5 border-gray-200 bg-white">
                        <p className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-3">Actions by Urgency</p>
                        <SeverityDonut
                          data={urgencyDonutData}
                          centerLabel="actions"
                          centerValue={actions.length}
                        />
                      </Card>
                    )}
                  </div>
                )}

                {/* Row 3: Key findings — compact expandable rows */}
                {sortedFindings.length > 0 && (
                  <Card className="p-4 border-gray-200 bg-white">
                    <p className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-3">Key Findings</p>
                    <div className="space-y-1">
                      {sortedFindings.map((f, i) => (
                        <FindingRow
                          key={i}
                          finding={f.finding}
                          severity={f.severity}
                          evidence={f.evidence}
                        />
                      ))}
                    </div>
                  </Card>
                )}

                {/* Row 4: Actions kanban by urgency */}
                {actions.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-3">Recommended Actions</p>
                    <ActionsKanban actions={actions} />
                  </div>
                )}

                {/* Row 5: Summary + Implications (collapsed) */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Card className="p-5 border-gray-200 bg-white">
                    <p className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-2">AI Summary</p>
                    <CollapsibleText text={latestInsight.summary ?? "No summary available."} />
                  </Card>
                  {latestInsight.implications && (
                    <Card className="p-5 border-gray-200 bg-primary/5 border-primary/15">
                      <div className="flex items-center gap-1.5 mb-2">
                        <Target className="w-3.5 h-3.5 text-primary" />
                        <p className="text-primary text-xs font-semibold uppercase tracking-wider">Impact on Pepperstone</p>
                      </div>
                      <CollapsibleText text={latestInsight.implications} />
                    </Card>
                  )}
                </div>
              </>
            );
          })()}
        </TabsContent>

        {/* Tab 2: Pricing */}
        <TabsContent value="pricing" className="mt-4">
          {!latestPricing ? (
            <Card
              className="p-8 border-gray-200 text-center text-gray-500 bg-white"
            >
              No pricing data available yet.
            </Card>
          ) : (
            <div className="space-y-4">
              <Card
                className="p-6 border-gray-200 bg-white"
              >
                <h3 className="text-gray-900 font-semibold mb-4">
                  Pricing Overview
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
                    <p className="text-gray-500 text-xs uppercase tracking-wider mb-1">
                      Min Deposit
                    </p>
                    <p className="text-gray-900 text-xl font-bold">
                      {wikifxMinDeposit ?? (latestPricing.minDepositUsd != null
                        ? `$${latestPricing.minDepositUsd.toLocaleString()}`
                        : "—")}
                    </p>
                    {wikifxMinDeposit && <p className="text-gray-400 text-xs mt-0.5">via WikiFX</p>}
                  </div>
                  <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
                    <p className="text-gray-500 text-xs uppercase tracking-wider mb-1">
                      Max Leverage
                    </p>
                    <p className="text-gray-900 text-xl font-bold">
                      {wikifxMaxLeverage ?? extractMaxLeverage(latestPricing?.leverageJson)}
                    </p>
                    {wikifxMaxLeverage && <p className="text-gray-400 text-xs mt-0.5">via WikiFX</p>}
                  </div>
                  <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
                    <p className="text-gray-500 text-xs uppercase tracking-wider mb-1">
                      Instruments
                    </p>
                    <p className="text-gray-900 text-xl font-bold">
                      {latestPricing.instrumentsCount ?? "—"}
                    </p>
                  </div>
                  <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
                    <p className="text-gray-500 text-xs uppercase tracking-wider mb-1">
                      Snapshot Date
                    </p>
                    <p className="text-gray-900 text-sm font-medium">
                      {formatDate(latestPricing.snapshotDate)}
                    </p>
                  </div>
                </div>
                {fundingMethods.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <p className="text-gray-500 text-xs uppercase tracking-wider mb-2">
                      Funding Methods
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {fundingMethods.map((m) => (
                        <span
                          key={m}
                          className="px-2 py-1 rounded-md text-xs bg-gray-100 text-gray-700 border border-gray-200"
                        >
                          {m}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </Card>

              {bizArea.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {bizArea.map((area) => (
                    <span
                      key={area}
                      className="px-2 py-1 rounded-md text-xs bg-blue-50 text-blue-700 border border-blue-200"
                    >
                      {area}
                    </span>
                  ))}
                </div>
              )}

              {detailedAccounts.length > 0 ? (
                <Card className="p-6 border-gray-200 bg-white">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-gray-900 font-semibold">Account Types</h3>
                    {latestAccountTypes && (
                      <span className="text-gray-400 text-xs">
                        Updated {formatDate(latestAccountTypes.snapshotDate)}
                      </span>
                    )}
                  </div>
                  <Tabs defaultValue={detailedAccounts[0]?.account_name ?? "0"}>
                    <TabsList className="bg-gray-100 border border-gray-200 h-auto p-1 flex flex-wrap mb-4">
                      {detailedAccounts.map((acc, i) => (
                        <TabsTrigger key={i} value={acc.account_name ?? String(i)} className="text-xs">
                          {acc.account_name ?? `Account ${i + 1}`}
                        </TabsTrigger>
                      ))}
                    </TabsList>
                    {detailedAccounts.map((acc, i) => (
                      <TabsContent key={i} value={acc.account_name ?? String(i)}>
                        {acc.account_category && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary mb-3">
                            {acc.account_category.replace("_", " ")}
                          </span>
                        )}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                          {[
                            { label: "Min Deposit", value: acc.min_deposit },
                            { label: "Spread From", value: acc.spread_from },
                            { label: "Commission", value: acc.commission },
                            { label: "Max Leverage", value: acc.max_leverage },
                            { label: "Execution", value: acc.execution_type },
                            { label: "Min Lot", value: acc.min_lot_size },
                            { label: "Margin Call", value: acc.margin_call_pct },
                            { label: "Stop Out", value: acc.stop_out_pct },
                          ].map((item) => {
                            const display = displayValue(item.value);
                            return (
                              <div key={item.label} className="p-3 rounded-lg bg-gray-50 border border-gray-100">
                                <p className="text-gray-500 text-xs mb-0.5">{item.label}</p>
                                <p className={`text-sm font-medium ${display === "—" ? "text-gray-300" : "text-gray-900"}`}>{display}</p>
                              </div>
                            );
                          })}
                        </div>
                        <div className="space-y-2 text-sm">
                          {acc.platforms && acc.platforms.length > 0 && (
                            <div className="flex items-center gap-2">
                              <span className="text-gray-500 text-xs w-24 shrink-0">Platforms</span>
                              <div className="flex flex-wrap gap-1">
                                {acc.platforms.map((p) => (
                                  <span key={p} className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-700">{p}</span>
                                ))}
                              </div>
                            </div>
                          )}
                          {acc.base_currencies && acc.base_currencies.length > 0 && (
                            <div className="flex items-center gap-2">
                              <span className="text-gray-500 text-xs w-24 shrink-0">Currencies</span>
                              <div className="flex flex-wrap gap-1">
                                {acc.base_currencies.map((c) => (
                                  <span key={c} className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-700">{c}</span>
                                ))}
                              </div>
                            </div>
                          )}
                          {acc.swap_free_available != null && (
                            <div className="flex items-center gap-2">
                              <span className="text-gray-500 text-xs w-24 shrink-0">Swap-Free</span>
                              <span className={`text-xs font-medium ${acc.swap_free_available ? "text-green-600" : "text-gray-400"}`}>
                                {acc.swap_free_available ? "Available" : "Not available"}
                              </span>
                            </div>
                          )}
                          {acc.negative_balance_protection != null && (
                            <div className="flex items-center gap-2">
                              <span className="text-gray-500 text-xs w-24 shrink-0">NBP</span>
                              <span className={`text-xs font-medium ${acc.negative_balance_protection ? "text-green-600" : "text-gray-400"}`}>
                                {acc.negative_balance_protection ? "Yes" : "No"}
                              </span>
                            </div>
                          )}
                          {acc.target_audience && (
                            <div className="flex items-center gap-2">
                              <span className="text-gray-500 text-xs w-24 shrink-0">For</span>
                              <span className="text-gray-700 text-xs">{acc.target_audience}</span>
                            </div>
                          )}
                          {acc.notes && (
                            <p className="text-gray-400 text-xs italic mt-2">{acc.notes}</p>
                          )}
                        </div>
                      </TabsContent>
                    ))}
                  </Tabs>
                </Card>
              ) : wikifxAccounts.length > 0 ? (
                <Card className="p-6 border-gray-200 bg-white">
                  <h3 className="text-gray-900 font-semibold mb-4">Account Types <span className="text-gray-400 text-xs font-normal">(via WikiFX)</span></h3>
                  <Tabs defaultValue={wikifxAccounts[0]?.name ?? "0"}>
                    <TabsList className="bg-gray-100 border border-gray-200 h-auto p-1 flex flex-wrap mb-4">
                      {wikifxAccounts.map((acc, i) => (
                        <TabsTrigger key={i} value={acc.name ?? String(i)} className="text-xs">
                          {acc.name ?? `Account ${i + 1}`}
                        </TabsTrigger>
                      ))}
                    </TabsList>
                    {wikifxAccounts.map((acc, i) => (
                      <TabsContent key={i} value={acc.name ?? String(i)}>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
                            <thead>
                              <tr className="bg-gray-50/80 border-b border-gray-200">
                                {["Spread (from)", "Max Leverage", "Min Deposit", "Currency", "Instruments"].map((h) => (
                                  <th key={h} className="text-left px-4 py-2 text-gray-500 font-medium text-xs uppercase tracking-wider">
                                    {h}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              <tr>
                                <td className="px-4 py-3 text-gray-700">{displayValue(acc.spread_from)}</td>
                                <td className="px-4 py-3 text-gray-700">{displayValue(acc.max_leverage)}</td>
                                <td className="px-4 py-3 text-gray-700">{displayValue(acc.min_deposit)}</td>
                                <td className="px-4 py-3 text-gray-700">{displayValue(acc.currency)}</td>
                                <td className="px-4 py-3 text-gray-700">{displayValue(acc.instruments)}</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </TabsContent>
                    ))}
                  </Tabs>
                </Card>
              ) : accountTypes.length > 0 ? (
                <Card className="p-6 border-gray-200 bg-white">
                  <h3 className="text-gray-900 font-semibold mb-4">Account Types</h3>
                  <div className="flex flex-wrap gap-2">
                    {(accountTypes as unknown[]).map((acc, i) => (
                      <span
                        key={i}
                        className="px-3 py-1.5 rounded-lg text-sm font-medium bg-gray-50 text-gray-700 border border-gray-200"
                      >
                        {String(acc)}
                      </span>
                    ))}
                  </div>
                </Card>
              ) : null}
            </div>
          )}
        </TabsContent>

        {/* Tab 3: Promotions */}
        <TabsContent value="promotions" className="mt-6 space-y-6">
          {promotions.length === 0 ? (
            <Card className="p-8 border-gray-200 text-center text-gray-500 bg-white">
              No active promotions found.
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {promotions.map((promo, i) => {
                const title = String(promo.title ?? promo.name ?? `Promo ${i + 1}`);
                const description = promo.description ? String(promo.description) : null;
                const offerValue = promo.offer_value ?? promo.value ?? promo.amount ?? null;
                const expiry = promo.expiry ?? promo.end_date ?? promo.endDate ?? null;
                const sourceUrl = promo.source_url ? String(promo.source_url) : null;

                return (
                  <Card key={i} className="p-6 border-gray-200 bg-white flex flex-col gap-3">
                    <h4 className="text-gray-900 font-semibold text-sm leading-snug">
                      {title}
                    </h4>
                    {offerValue != null && (
                      <p className="text-xl font-bold text-primary">
                        {String(offerValue)}
                      </p>
                    )}
                    {description && (
                      <p className="text-gray-600 text-sm leading-relaxed">
                        {description}
                      </p>
                    )}
                    <div className="flex flex-wrap items-center gap-3 mt-auto pt-2 border-t border-gray-100">
                      {expiry && (
                        <span className="text-gray-400 text-xs">
                          Expires: {String(expiry)}
                        </span>
                      )}
                      {sourceUrl && (
                        <a
                          href={sourceUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs font-medium hover:underline ml-auto text-primary"
                        >
                          View source →
                        </a>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
          )}

          {marketingStrategy.length > 0 && (
            <Card className="p-6 border-gray-200 bg-white">
              <h3 className="text-gray-900 font-semibold mb-4">WikiFX Marketing Intelligence</h3>
              <div className="space-y-3">
                {marketingStrategy.map((item, i) => (
                  <div key={i} className="p-3 rounded-lg bg-gray-50 border border-gray-100">
                    <p className="font-medium text-gray-800 text-sm">{item.title}</p>
                    {item.description && (
                      <p className="text-gray-600 text-sm mt-1">{item.description}</p>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </TabsContent>

        {/* Tab 4: Digital Presence */}
        <TabsContent value="digital" className="mt-4 space-y-6">
          <Card className="p-6 border-gray-200 bg-white">
            <h3 className="text-gray-900 font-semibold mb-4">Follower Comparison</h3>
            <SocialBarChart
              data={PLATFORMS
                .filter((p) => socialMap[p]?.followers != null && socialMap[p]!.followers! > 0)
                .map((p) => ({ platform: p.charAt(0).toUpperCase() + p.slice(1), followers: socialMap[p]!.followers! }))}
            />
          </Card>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {PLATFORMS.map((platform) => {
              const snap = socialMap[platform];
              const isPerMarket = socialMarketOverride[platform];
              return (
                <Card
                  key={platform}
                  className="p-5 border-gray-200 bg-white"
                >
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-gray-900 font-medium capitalize">
                      {platform}
                    </h4>
                    {market && (
                      <span className={`text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded border ${
                        isPerMarket
                          ? "border-primary/30 bg-primary/5 text-primary"
                          : "border-gray-200 bg-gray-50 text-gray-500"
                      }`}>
                        {isPerMarket ? `${MARKET_NAMES[market]} profile` : "Global"}
                      </span>
                    )}
                  </div>
                  {!snap ? (
                    <p className="text-gray-400 text-sm">
                      N/A — Data unavailable
                    </p>
                  ) : (
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-500">Followers</span>
                        <span className="text-gray-700 font-mono">
                          {snap.followers != null
                            ? snap.followers.toLocaleString()
                            : "—"}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-500">Posts (7d)</span>
                        <span className="text-gray-700 font-mono">
                          {snap.postsLast7d ?? "—"}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-500">Engagement</span>
                        <span className="text-gray-700 font-mono">
                          {snap.engagementRate != null
                            ? `${(snap.engagementRate * 100).toFixed(2)}%`
                            : "—"}
                        </span>
                      </div>
                      <p className="text-gray-400 text-xs pt-1">
                        Updated {timeAgo(snap.snapshotDate)}
                      </p>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        </TabsContent>

        {/* Tab 5: Reputation */}
        <TabsContent value="reputation" className="mt-6 space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {[
              {
                label: "Trustpilot",
                value: latestReputation?.trustpilotScore,
                suffix: "/5",
                count: latestReputation?.trustpilotCount,
              },
              {
                label: "MyFXBook",
                value: latestReputation?.myfxbookRating,
                suffix: "/10",
                count: null,
              },
              {
                label: market
                  ? `App Store — ${MARKET_NAMES[market]}`
                  : "App Store (iOS)",
                value: market ? marketAppStoreRating : latestReputation?.iosRating,
                suffix: "/5",
                count: market ? marketAppStoreReviews : null,
              },
              {
                label: "Google Play",
                value: latestReputation?.androidRating,
                suffix: "/5",
                count: null,
              },
              {
                label: "WikiFX Score",
                value: latestWikifx?.wikifxScore,
                suffix: "/10",
                count: null,
              },
            ].map((item) => (
              <Card
                key={item.label}
                className="p-5 border-gray-200 bg-white"
              >
                <p className="text-gray-500 text-xs mb-2">{item.label}</p>
                <p className="text-gray-900 text-2xl font-bold">
                  {item.value != null ? (
                    <>
                      {item.value.toFixed(1)}
                      <span className="text-gray-400 text-sm font-normal">
                        {item.suffix}
                      </span>
                    </>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                </p>
                {item.count != null && (
                  <p className="text-gray-400 text-xs mt-1">
                    {item.count.toLocaleString()} reviews
                  </p>
                )}
              </Card>
            ))}
          </div>

          <Card className="p-6 border-gray-200 bg-white">
            <h3 className="text-gray-900 font-semibold mb-4">Reputation Overview</h3>
            <ReputationRadar
              trustpilot={latestReputation?.trustpilotScore ?? null}
              myfxbook={latestReputation?.myfxbookRating ?? null}
              ios={latestReputation?.iosRating ?? null}
              android={latestReputation?.androidRating ?? null}
              wikifx={latestWikifx?.wikifxScore ?? null}
            />
          </Card>

          {entitiesBreakdown.length > 0 && (
            <Card className="border-gray-200 bg-white overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-gray-900 font-semibold">Entity Breakdown</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 bg-gray-50/80">
                      {["Entity", "Trustpilot", "FPA", "MyFXBook", "App Store", "Google Play"].map((h) => (
                        <th
                          key={h}
                          className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {entitiesBreakdown.map((entity, i) => (
                      <tr
                        key={i}
                        className={`border-b border-gray-100 ${i === entitiesBreakdown.length - 1 ? "border-b-0" : ""}`}
                      >
                        <td className="px-4 py-3 text-gray-700 font-medium">{entity.label}</td>
                        <td className="px-4 py-3 text-gray-600 font-mono text-xs">
                          {entity.trustpilot_score != null ? (
                            <>
                              {entity.trustpilot_score.toFixed(1)}
                              {entity.trustpilot_count != null && (
                                <span className="text-gray-400 ml-1">
                                  ({entity.trustpilot_count.toLocaleString()} rev)
                                </span>
                              )}
                            </>
                          ) : "—"}
                        </td>
                        <td className="px-4 py-3 text-gray-600 font-mono text-xs">
                          {entity.fpa_rating != null ? entity.fpa_rating.toFixed(1) : "—"}
                        </td>
                        <td className="px-4 py-3 text-gray-600 font-mono text-xs">
                          {entity.myfxbook_rating != null ? entity.myfxbook_rating.toFixed(1) : "—"}
                        </td>
                        <td className="px-4 py-3 text-gray-600 font-mono text-xs">
                          {entity.ios_rating != null ? entity.ios_rating.toFixed(1) : "—"}
                        </td>
                        <td className="px-4 py-3 text-gray-600 font-mono text-xs">
                          {entity.android_rating != null ? entity.android_rating.toFixed(1) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {news.length > 0 && (
            <Card
              className="p-6 border-gray-200 bg-white"
            >
              <h3 className="text-gray-900 font-semibold mb-5">Recent News</h3>
              <div className="space-y-4">
                {news.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-start gap-4 p-4 rounded-lg bg-gray-50 border border-gray-100"
                  >
                    <SentimentBadge sentiment={item.sentiment} />
                    <div className="flex-1 min-w-0">
                      {item.url ? (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-gray-800 text-sm font-medium hover:text-primary transition-colors line-clamp-2 leading-snug"
                        >
                          {item.title}
                        </a>
                      ) : (
                        <p className="text-gray-800 text-sm font-medium leading-snug">{item.title}</p>
                      )}
                      <p className="text-gray-400 text-xs mt-2">
                        {item.source && <span>{item.source} · </span>}
                        {formatDateTime(item.publishedAt)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </TabsContent>

        {/* Tab 6: Change History */}
        <TabsContent value="changes" className="mt-4">
          <CompetitorChangeTable changes={changes} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
