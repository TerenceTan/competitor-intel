import { db } from "./index";
import { runMigrations } from "./migrate";
import { competitors, markets, pricingSnapshots, promoSnapshots, reputationSnapshots, changeEvents, aiInsights, socialSnapshots, newsItems } from "./schema";

const COMPETITORS = [
  { id: "ic-markets", name: "IC Markets", tier: 1, website: "icmarkets.com" },
  { id: "exness", name: "Exness", tier: 1, website: "exness.com" },
  { id: "vantage", name: "Vantage Markets", tier: 1, website: "vantagemarkets.com" },
  { id: "xm", name: "XM Group", tier: 1, website: "xm.com" },
  { id: "hfm", name: "HFM", tier: 1, website: "hfm.com" },
  { id: "fbs", name: "FBS", tier: 2, website: "fbs.com" },
  { id: "iux", name: "IUX", tier: 2, website: "iux.com" },
  { id: "fxpro", name: "FxPro", tier: 2, website: "fxpro.com" },
  { id: "mitrade", name: "Mitrade", tier: 2, website: "mitrade.com" },
  { id: "tmgm", name: "TMGM", tier: 2, website: "tmgm.com" },
];

const MARKETS = [
  { id: "sg", code: "sg", name: "Singapore", characteristics: "Asia's largest FX hub. Institutional-grade expectations. High LTV but high CAC.", platforms: "LinkedIn,Facebook,Telegram" },
  { id: "hk", code: "hk", name: "Hong Kong", characteristics: "Major financial centre. Bilingual. Sophisticated retail and HNW clients.", platforms: "Facebook,Instagram,Telegram,YouTube" },
  { id: "th", code: "th", name: "Thailand", characteristics: "Strong retail participation. Responds well to education and influencers.", platforms: "Facebook,YouTube,LINE" },
  { id: "vn", code: "vn", name: "Vietnam", characteristics: "High-growth. Trust and credibility paramount. Community-driven learning.", platforms: "Facebook,Zalo,YouTube" },
  { id: "id", code: "id", name: "Indonesia", characteristics: "Largest growth market in SEA. High mobile engagement.", platforms: "TikTok,Instagram,WhatsApp" },
  { id: "my", code: "my", name: "Malaysia", characteristics: "Risk-aware traders. Islamic finance offerings are key differentiator.", platforms: "Facebook,WhatsApp" },
  { id: "jp", code: "jp", name: "Japan", characteristics: "One of the world's most active retail FX communities. Deep localisation required.", platforms: "LINE,X/Twitter,YouTube" },
  { id: "mn", code: "mn", name: "Mongolia", characteristics: "Small but emerging market. Mobile-first. Price-sensitive.", platforms: "Facebook,Telegram" },
  { id: "in", code: "in", name: "India", characteristics: "Massive population. Trust and INR payment options are key differentiators.", platforms: "WhatsApp,YouTube,Instagram,Telegram" },
  { id: "ph", code: "ph", name: "Philippines", characteristics: "Fast-growing retail FX market. Mobile-first culture. Strong Facebook dominance.", platforms: "Facebook,TikTok,YouTube,Viber" },
  { id: "tw", code: "tw", name: "Taiwan", characteristics: "Sophisticated, Japan-influenced FX culture. High retail participation.", platforms: "LINE,Facebook,YouTube" },
  { id: "cn", code: "cn", name: "China", characteristics: "Largest potential market but most restricted. Manual monitoring only.", platforms: "WeChat (manual),Weibo (manual),Douyin (manual)" },
];

const today = new Date().toISOString().split("T")[0];

async function seed() {
  console.log("Running migrations...");
  runMigrations();

  console.log("Seeding competitors...");
  for (const comp of COMPETITORS) {
    await db.insert(competitors).values(comp).onConflictDoNothing();
  }

  console.log("Seeding markets...");
  for (const market of MARKETS) {
    await db.insert(markets).values(market).onConflictDoNothing();
  }

  console.log("Seeding sample pricing data...");
  const pricingData = [
    { competitorId: "ic-markets", minDepositUsd: 200, instrumentsCount: 2250, leverageJson: JSON.stringify({ standard: "1:1000", raw: "1:500" }), accountTypesJson: JSON.stringify(["Standard", "Raw Spread", "cTrader"]), fundingMethodsJson: JSON.stringify(["Credit Card", "Bank Wire", "Skrill", "Neteller", "PayPal"]) },
    { competitorId: "exness", minDepositUsd: 1, instrumentsCount: 290, leverageJson: JSON.stringify({ standard: "1:2000", pro: "1:unlimited" }), accountTypesJson: JSON.stringify(["Standard", "Standard Cent", "Pro", "Raw Spread", "Zero"]), fundingMethodsJson: JSON.stringify(["Credit Card", "Bank Wire", "Perfect Money", "Cryptocurrency"]) },
    { competitorId: "vantage", minDepositUsd: 50, instrumentsCount: 1000, leverageJson: JSON.stringify({ standard: "1:500", raw: "1:500" }), accountTypesJson: JSON.stringify(["Standard STP", "Raw ECN", "Pro ECN"]), fundingMethodsJson: JSON.stringify(["Credit Card", "Bank Wire", "PayPal", "Skrill"]) },
    { competitorId: "xm", minDepositUsd: 5, instrumentsCount: 1380, leverageJson: JSON.stringify({ micro: "1:1000", standard: "1:888", ultra_low: "1:888" }), accountTypesJson: JSON.stringify(["Micro", "Standard", "Ultra Low", "Shares"]), fundingMethodsJson: JSON.stringify(["Credit Card", "Bank Wire", "Skrill", "Neteller"]) },
    { competitorId: "fxtm", minDepositUsd: 10, instrumentsCount: 250, leverageJson: JSON.stringify({ advantage: "1:2000", standard: "1:1000" }), accountTypesJson: JSON.stringify(["Standard", "Cent", "Shares", "ECN"]), fundingMethodsJson: JSON.stringify(["Credit Card", "Bank Wire", "Skrill", "Neteller"]) },
    { competitorId: "atfx", minDepositUsd: 100, instrumentsCount: 300, leverageJson: JSON.stringify({ standard: "1:400" }), accountTypesJson: JSON.stringify(["Standard", "Premium"]), fundingMethodsJson: JSON.stringify(["Credit Card", "Bank Wire", "Local Payment"]) },
    { competitorId: "fp-markets", minDepositUsd: 100, instrumentsCount: 10000, leverageJson: JSON.stringify({ standard: "1:500", raw: "1:500" }), accountTypesJson: JSON.stringify(["Standard", "Raw", "IRESS"]), fundingMethodsJson: JSON.stringify(["Credit Card", "Bank Wire", "PayPal", "Skrill", "Neteller"]) },
    { competitorId: "fbs", minDepositUsd: 1, instrumentsCount: 550, leverageJson: JSON.stringify({ cent: "1:1000", standard: "1:3000" }), accountTypesJson: JSON.stringify(["Cent", "Micro", "Standard", "Zero Spread", "ECN"]), fundingMethodsJson: JSON.stringify(["Credit Card", "Bank Wire", "Skrill", "Neteller", "Cryptocurrency"]) },
    { competitorId: "titan-fx", minDepositUsd: 200, instrumentsCount: 200, leverageJson: JSON.stringify({ standard: "1:500", blade: "1:500" }), accountTypesJson: JSON.stringify(["Standard", "Blade", "Micro"]), fundingMethodsJson: JSON.stringify(["Credit Card", "Bank Wire", "Cryptocurrency"]) },
    { competitorId: "mifx", minDepositUsd: 100, instrumentsCount: 170, leverageJson: JSON.stringify({ standard: "1:500" }), accountTypesJson: JSON.stringify(["Standard", "Premium"]), fundingMethodsJson: JSON.stringify(["Bank Wire", "Local IDR Transfer"]) },
    { competitorId: "fintrix", minDepositUsd: 100, instrumentsCount: 300, leverageJson: JSON.stringify({ standard: "1:500" }), accountTypesJson: JSON.stringify(["Standard", "Pro"]), fundingMethodsJson: JSON.stringify(["Credit Card", "Bank Wire", "Cryptocurrency"]) },
  ];
  for (const p of pricingData) {
    await db.insert(pricingSnapshots).values({ ...p, snapshotDate: today }).onConflictDoNothing();
  }

  console.log("Seeding sample reputation data...");
  const repData = [
    { competitorId: "ic-markets", trustpilotScore: 4.7, trustpilotCount: 38000, fpaRating: 4.8, iosRating: 4.6, androidRating: 4.4 },
    { competitorId: "exness", trustpilotScore: 4.1, trustpilotCount: 12000, fpaRating: 3.9, iosRating: 4.5, androidRating: 4.3 },
    { competitorId: "vantage", trustpilotScore: 4.5, trustpilotCount: 8500, fpaRating: 4.2, iosRating: 4.4, androidRating: 4.2 },
    { competitorId: "xm", trustpilotScore: 3.9, trustpilotCount: 22000, fpaRating: 3.7, iosRating: 4.2, androidRating: 4.0 },
    { competitorId: "fxtm", trustpilotScore: 4.3, trustpilotCount: 9000, fpaRating: 4.1, iosRating: 4.3, androidRating: 4.1 },
    { competitorId: "atfx", trustpilotScore: 4.0, trustpilotCount: 3200, fpaRating: 3.8, iosRating: 4.1, androidRating: 4.0 },
    { competitorId: "fp-markets", trustpilotScore: 4.8, trustpilotCount: 6500, fpaRating: 4.6, iosRating: 4.5, androidRating: 4.3 },
    { competitorId: "fbs", trustpilotScore: 3.8, trustpilotCount: 5800, fpaRating: 3.5, iosRating: 4.2, androidRating: 4.1 },
    { competitorId: "titan-fx", trustpilotScore: 4.6, trustpilotCount: 1200, fpaRating: 4.4, iosRating: 4.3, androidRating: 4.2 },
    { competitorId: "mifx", trustpilotScore: 3.7, trustpilotCount: 800, fpaRating: 3.6, iosRating: 4.0, androidRating: 3.9 },
    { competitorId: "fintrix", trustpilotScore: 4.2, trustpilotCount: 120, fpaRating: null, iosRating: null, androidRating: null },
  ];
  for (const r of repData) {
    await db.insert(reputationSnapshots).values({ ...r, snapshotDate: today }).onConflictDoNothing();
  }

  console.log("Seeding sample promotions...");
  const promoData = [
    { competitorId: "exness", promotionsJson: JSON.stringify([{ name: "VN Cashback Offer March 2026", type: "cashback", value: "$500", markets: ["vn"], endDate: "2026-03-31" }, { name: "No Deposit Bonus", type: "deposit_bonus", value: "$30", markets: ["th", "my", "id"], endDate: "2026-04-30" }]) },
    { competitorId: "xm", promotionsJson: JSON.stringify([{ name: "XM Ultra Low Account Bonus", type: "deposit_bonus", value: "100% up to $500", markets: ["sg", "my", "th"], endDate: "2026-04-15" }, { name: "XM Trading Contest Q1 2026", type: "competition", value: "$50,000 prize pool", markets: ["sg", "hk", "jp", "tw"], endDate: "2026-03-31" }]) },
    { competitorId: "fbs", promotionsJson: JSON.stringify([{ name: "FBS 100% Deposit Bonus", type: "deposit_bonus", value: "100% up to $500", markets: ["th", "id", "ph", "my"], endDate: "2026-05-31" }, { name: "FBS Partner Program", type: "ib", value: "Up to $15/lot", markets: ["th", "id", "vn", "ph"], endDate: null }]) },
    { competitorId: "ic-markets", promotionsJson: JSON.stringify([{ name: "IC Markets Raw Spread Account Promo", type: "spread_discount", value: "From 0.0 pips", markets: ["sg", "hk", "au"], endDate: null }]) },
    { competitorId: "vantage", promotionsJson: JSON.stringify([{ name: "Vantage Welcome Bonus", type: "deposit_bonus", value: "50% up to $1000", markets: ["sg", "my", "th", "vn"], endDate: "2026-06-30" }]) },
    { competitorId: "fintrix", promotionsJson: JSON.stringify([{ name: "Fintrix Launch Promotion", type: "deposit_bonus", value: "50% up to $2000", markets: ["sg", "au", "hk"], endDate: "2026-04-30" }]) },
  ];
  for (const p of promoData) {
    await db.insert(promoSnapshots).values({ ...p, snapshotDate: today }).onConflictDoNothing();
  }

  console.log("Seeding sample change events...");
  const changes = [
    { competitorId: "exness", domain: "promotions", fieldName: "active_promotions", oldValue: "1 promotion", newValue: "2 promotions", severity: "high", detectedAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString() },
    { competitorId: "fintrix", domain: "pricing", fieldName: "min_deposit_usd", oldValue: "200", newValue: "100", severity: "medium", detectedAt: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString() },
    { competitorId: "xm", domain: "promotions", fieldName: "trading_contest", oldValue: null, newValue: "XM Trading Contest Q1 2026 - $50,000 prize pool", severity: "high", detectedAt: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString() },
    { competitorId: "fbs", domain: "pricing", fieldName: "max_leverage", oldValue: "1:2000", newValue: "1:3000", severity: "medium", detectedAt: new Date(Date.now() - 18 * 60 * 60 * 1000).toISOString() },
    { competitorId: "ic-markets", domain: "reputation", fieldName: "trustpilot_score", oldValue: "4.6", newValue: "4.7", severity: "low", detectedAt: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString() },
    { competitorId: "vantage", domain: "promotions", fieldName: "welcome_bonus", oldValue: "30% up to $500", newValue: "50% up to $1000", severity: "high", detectedAt: new Date(Date.now() - 36 * 60 * 60 * 1000).toISOString() },
    { competitorId: "fp-markets", domain: "pricing", fieldName: "instruments_count", oldValue: "9500", newValue: "10000", severity: "low", detectedAt: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString() },
  ];
  for (const c of changes) {
    await db.insert(changeEvents).values(c).onConflictDoNothing();
  }

  console.log("Seeding sample AI insights...");
  const insights = [
    {
      competitorId: "exness",
      generatedAt: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
      summary: "Exness launched a new cashback promotion targeting Vietnam traders, offering up to $500 cashback on deposits above $1,000. This is their third Vietnam-specific campaign in 2026.",
      keyFindingsJson: JSON.stringify([
        { finding: "New cashback promotion live on exness.com/vn/", severity: "high", evidence: "Promotions page shows 'VN Cashback Offer March 2026'" },
        { finding: "No deposit bonus extended to SEA markets through April 2026", severity: "medium", evidence: "Global promotions page updated" }
      ]),
      implications: "Exness is aggressively targeting Pepperstone's Vietnam growth market with a high-value cashback offer that undercuts current Pepperstone promotions.",
      actionsJson: JSON.stringify([
        { action: "Review Pepperstone Vietnam promotion calendar — consider counter-offer", urgency: "this_week" },
        { action: "Inform Vietnam regional manager of competitive development", urgency: "immediate" }
      ])
    },
    {
      competitorId: "fintrix",
      generatedAt: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
      summary: "Fintrix Markets has lowered their minimum deposit from $200 to $100 and launched a 50% welcome bonus, likely leveraging founders' knowledge of Pepperstone's client acquisition strategies.",
      keyFindingsJson: JSON.stringify([
        { finding: "Minimum deposit reduced 50% from $200 to $100", severity: "medium", evidence: "Pricing page updated March 16 2026" },
        { finding: "Launch promotion offering 50% deposit match up to $2000", severity: "high", evidence: "New promotions page visible on fintrix.com" }
      ]),
      implications: "Fintrix is positioning aggressively with pricing that directly mirrors Pepperstone's entry-level tier. Given founder backgrounds, this is a deliberate competitive signal.",
      actionsJson: JSON.stringify([
        { action: "Monitor Fintrix for any Pepperstone-specific positioning language", urgency: "immediate" },
        { action: "Review Pepperstone welcome offer competitiveness in SG/HK markets", urgency: "this_week" }
      ])
    },
    {
      competitorId: "xm",
      generatedAt: new Date(Date.now() - 10 * 60 * 60 * 1000).toISOString(),
      summary: "XM Group launched a Q1 2026 trading contest with a $50,000 prize pool targeting key APAC financial hubs. This follows their pattern of quarterly contest marketing.",
      keyFindingsJson: JSON.stringify([
        { finding: "Trading Contest Q1 2026 launched — $50,000 prize pool", severity: "high", evidence: "XM contests page and social media" },
        { finding: "Contest targeted at Singapore, HK, Japan, Taiwan", severity: "medium", evidence: "Regional landing pages live" }
      ]),
      implications: "XM is doubling down on tier-1 APAC markets with high-value competition marketing. Pepperstone has no comparable contest currently running in these markets.",
      actionsJson: JSON.stringify([
        { action: "Evaluate trading contest as a Q2 activation for SG/HK", urgency: "this_month" },
        { action: "Brief campaign managers in targeted markets", urgency: "this_week" }
      ])
    },
  ];
  for (const insight of insights) {
    await db.insert(aiInsights).values(insight).onConflictDoNothing();
  }

  console.log("Seeding sample social data...");
  const socialData = [
    { competitorId: "ic-markets", platform: "youtube", followers: 85000, postsLast7d: 3, engagementRate: 2.1 },
    { competitorId: "ic-markets", platform: "telegram", followers: 42000, postsLast7d: 12, engagementRate: 4.5 },
    { competitorId: "exness", platform: "youtube", followers: 320000, postsLast7d: 7, engagementRate: 3.8 },
    { competitorId: "exness", platform: "telegram", followers: 180000, postsLast7d: 21, engagementRate: 6.2 },
    { competitorId: "xm", platform: "youtube", followers: 210000, postsLast7d: 5, engagementRate: 2.9 },
    { competitorId: "xm", platform: "facebook", followers: 980000, postsLast7d: 14, engagementRate: 1.8 },
    { competitorId: "fbs", platform: "facebook", followers: 2100000, postsLast7d: 28, engagementRate: 5.3 },
    { competitorId: "fbs", platform: "youtube", followers: 145000, postsLast7d: 6, engagementRate: 4.1 },
    { competitorId: "vantage", platform: "youtube", followers: 62000, postsLast7d: 4, engagementRate: 2.4 },
    { competitorId: "fp-markets", platform: "youtube", followers: 48000, postsLast7d: 3, engagementRate: 2.0 },
  ];
  for (const s of socialData) {
    await db.insert(socialSnapshots).values({ ...s, snapshotDate: today }).onConflictDoNothing();
  }

  console.log("Seeding sample news items...");
  const news = [
    { competitorId: "exness", title: "Exness Reports Record Trading Volumes in Southeast Asia Q1 2026", url: "#", source: "Finance Magnates", publishedAt: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), sentiment: "positive" },
    { competitorId: "fintrix", title: "Fintrix Markets Launches with Former Pepperstone Team", url: "#", source: "FX News", publishedAt: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(), sentiment: "neutral" },
    { competitorId: "xm", title: "XM Group Expands Operations in Japan Market", url: "#", source: "ForexLive", publishedAt: new Date(Date.now() - 72 * 60 * 60 * 1000).toISOString(), sentiment: "positive" },
    { competitorId: "fbs", title: "FBS Under Regulatory Scrutiny in Multiple APAC Markets", url: "#", source: "LeapRate", publishedAt: new Date(Date.now() - 96 * 60 * 60 * 1000).toISOString(), sentiment: "negative" },
    { competitorId: "ic-markets", title: "IC Markets Achieves 10 Million Client Milestone", url: "#", source: "Finance Magnates", publishedAt: new Date(Date.now() - 120 * 60 * 60 * 1000).toISOString(), sentiment: "positive" },
  ];
  for (const n of news) {
    await db.insert(newsItems).values(n).onConflictDoNothing();
  }

  console.log("Seed complete!");
}

seed().catch(console.error);
