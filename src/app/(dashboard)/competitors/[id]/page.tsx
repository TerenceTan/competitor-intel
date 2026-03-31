import { db } from "@/db";
import {
  competitors,
  aiInsights,
  pricingSnapshots,
  promoSnapshots,
  socialSnapshots,
  reputationSnapshots,
  newsItems,
  changeEvents,
  wikifxSnapshots,
} from "@/db/schema";
import { desc, eq } from "drizzle-orm";
import { notFound } from "next/navigation";
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
import { SeverityBadge } from "@/components/shared/severity-badge";

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
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

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
      .where(eq(promoSnapshots.competitorId, id))
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
  ]);

  // Parse JSON fields
  let keyFindings: Array<{ finding: string; severity: string }> = [];
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

  keyFindings = safeParseJson(latestInsight?.keyFindingsJson, [], "keyFindingsJson");
  actions = safeParseJson(latestInsight?.actionsJson, [], "actionsJson");
  accountTypes = safeParseJson(latestPricing?.accountTypesJson, [], "accountTypesJson");
  promotions = safeParseJson(latestPromo?.promotionsJson, [], "promotionsJson");
  fundingMethods = safeParseJson(latestPricing?.fundingMethodsJson, [], "fundingMethodsJson");
  entitiesBreakdown = safeParseJson(latestReputation?.entitiesBreakdownJson, [], "entitiesBreakdownJson");
  wikifxAccounts = safeParseJson(latestWikifx?.accountsJson, [], "accountsJson");
  marketingStrategy = safeParseJson(latestWikifx?.marketingStrategyJson, [], "marketingStrategyJson");
  bizArea = safeParseJson(latestWikifx?.bizAreaJson, [], "bizAreaJson");

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

  // Build social map (latest per platform)
  const socialMap: Record<string, typeof socialData[0]> = {};
  for (const snap of socialData) {
    if (!socialMap[snap.platform]) {
      socialMap[snap.platform] = snap;
    }
  }

  const tierColors: Record<number, string> = {
    1: "bg-blue-50 text-blue-700 border-blue-200",
    2: "bg-indigo-50 text-indigo-700 border-indigo-200",
    3: "bg-gray-100 text-gray-600 border-gray-200",
  };
  const tierCls = tierColors[competitor.tier] ?? tierColors[3];

  const urgencyColors: Record<string, string> = {
    high: "text-orange-600",
    medium: "text-amber-600",
    low: "text-blue-600",
  };

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
        <TabsContent value="overview" className="mt-6 space-y-6">
          {!latestInsight ? (
            <Card
              className="p-8 border-gray-200 text-center text-gray-500 bg-white"
            >
              No AI insights generated yet.
            </Card>
          ) : (
            <>
              <Card
                className="p-6 border-gray-200 bg-white"
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-gray-900 font-semibold">Summary</h3>
                  <span className="text-gray-400 text-xs">
                    Generated {timeAgo(latestInsight.generatedAt)}
                  </span>
                </div>
                <p className="text-gray-700 leading-loose text-sm">
                  {latestInsight.summary ?? "No summary available."}
                </p>
                {latestInsight.implications && (
                  <div className="mt-6 pt-6 border-t border-gray-200">
                    <p className="text-gray-500 text-xs uppercase tracking-wider mb-3">
                      Implications for Pepperstone
                    </p>
                    <p className="text-gray-600 text-sm leading-loose">
                      {latestInsight.implications}
                    </p>
                  </div>
                )}
              </Card>

              {keyFindings.length > 0 && (
                <Card
                  className="p-6 border-gray-200 bg-white"
                >
                  <h3 className="text-gray-900 font-semibold mb-4">
                    Key Findings
                  </h3>
                  <div className="space-y-3">
                    {keyFindings.map((f, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 p-3 rounded-lg bg-gray-50"
                      >
                        <SeverityBadge severity={f.severity} />
                        <p className="text-gray-700 text-sm flex-1">
                          {f.finding}
                        </p>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {actions.length > 0 && (
                <Card
                  className="p-6 border-gray-200 bg-white"
                >
                  <h3 className="text-gray-900 font-semibold mb-4">
                    Recommended Actions
                  </h3>
                  <div className="space-y-3">
                    {actions.map((a, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 p-3 rounded-lg bg-gray-50"
                      >
                        <span
                          className={`text-xs font-semibold uppercase tracking-wider mt-0.5 ${
                            urgencyColors[a.urgency?.toLowerCase()] ??
                            "text-gray-500"
                          }`}
                        >
                          {a.urgency}
                        </span>
                        <p className="text-gray-700 text-sm flex-1">
                          {a.action}
                        </p>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              <div title="Requires Anthropic API key">
                <button
                  disabled
                  className="px-4 py-2 rounded-lg text-sm font-medium bg-primary text-white cursor-not-allowed opacity-50 border border-primary"
                >
                  Regenerate Analysis
                </button>
                <span className="text-gray-400 text-xs ml-3">
                  Requires Anthropic API key
                </span>
              </div>
            </>
          )}
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

              {wikifxAccounts.length > 0 ? (
                <Card className="p-6 border-gray-200 bg-white">
                  <h3 className="text-gray-900 font-semibold mb-4">Account Types</h3>
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
                              <tr className="bg-gray-50 border-b border-gray-200">
                                {["Spread (from)", "Max Leverage", "Min Deposit", "Currency", "Instruments"].map((h) => (
                                  <th key={h} className="text-left px-4 py-2 text-gray-500 font-medium text-xs uppercase tracking-wider">
                                    {h}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              <tr>
                                <td className="px-4 py-3 text-gray-700">{acc.spread_from ?? "—"}</td>
                                <td className="px-4 py-3 text-gray-700">{acc.max_leverage ?? "—"}</td>
                                <td className="px-4 py-3 text-gray-700">{acc.min_deposit ?? "—"}</td>
                                <td className="px-4 py-3 text-gray-700">{acc.currency ?? "—"}</td>
                                <td className="px-4 py-3 text-gray-700">{acc.instruments ?? "—"}</td>
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
              return (
                <Card
                  key={platform}
                  className="p-5 border-gray-200 bg-white"
                >
                  <h4 className="text-gray-900 font-medium capitalize mb-3">
                    {platform}
                  </h4>
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
                label: "App Store (iOS)",
                value: latestReputation?.iosRating,
                suffix: "/5",
                count: null,
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
