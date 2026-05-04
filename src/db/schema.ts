import { sqliteTable, text, integer, real } from "drizzle-orm/sqlite-core";

export const competitors = sqliteTable("competitors", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  tier: integer("tier").notNull(),
  website: text("website").notNull(),
  isSelf: integer("is_self").notNull().default(0),
  createdAt: text("created_at").notNull().default(new Date().toISOString()),
  scraperConfig: text("scraper_config"),
  marketConfig: text("market_config"),
});

export const markets = sqliteTable("markets", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  code: text("code").notNull().unique(),
  characteristics: text("characteristics"),
  platforms: text("platforms"),
});

export const pricingSnapshots = sqliteTable("pricing_snapshots", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  competitorId: text("competitor_id").notNull().references(() => competitors.id),
  snapshotDate: text("snapshot_date").notNull(),
  leverageJson: text("leverage_json"),
  accountTypesJson: text("account_types_json"),
  minDepositUsd: real("min_deposit_usd"),
  instrumentsCount: integer("instruments_count"),
  fundingMethodsJson: text("funding_methods_json"),
  spreadJson: text("spread_json"),
  leverageSourcesJson: text("leverage_sources_json"),
  leverageConfidence: text("leverage_confidence"),
  leverageReconciliationJson: text("leverage_reconciliation_json"),
  minDepositSourcesJson: text("min_deposit_sources_json"),
  minDepositConfidence: text("min_deposit_confidence"),
  minDepositReconciliationJson: text("min_deposit_reconciliation_json"),
  marketCode: text("market_code").notNull().default("global"),
});

export const promoSnapshots = sqliteTable("promo_snapshots", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  competitorId: text("competitor_id").notNull().references(() => competitors.id),
  snapshotDate: text("snapshot_date").notNull(),
  promotionsJson: text("promotions_json"),
  marketCode: text("market_code").notNull().default("global"),
  extractionConfidence: text("extraction_confidence"),  // 'high' | 'medium' | 'low' | null — Phase 1 TRUST-01
});

export const socialSnapshots = sqliteTable("social_snapshots", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  competitorId: text("competitor_id").notNull().references(() => competitors.id),
  platform: text("platform").notNull(),
  snapshotDate: text("snapshot_date").notNull(),
  followers: integer("followers"),
  postsLast7d: integer("posts_last_7d"),
  engagementRate: real("engagement_rate"),
  latestPostUrl: text("latest_post_url"),
  marketCode: text("market_code").notNull().default("global"),
  extractionConfidence: text("extraction_confidence"),  // 'high' | 'medium' | 'low' | null — Phase 1 TRUST-01
});

export const reputationSnapshots = sqliteTable("reputation_snapshots", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  competitorId: text("competitor_id").notNull().references(() => competitors.id),
  snapshotDate: text("snapshot_date").notNull(),
  trustpilotScore: real("trustpilot_score"),
  trustpilotCount: integer("trustpilot_count"),
  fpaRating: real("fpa_rating"),
  iosRating: real("ios_rating"),
  androidRating: real("android_rating"),
  entitiesBreakdownJson: text("entities_breakdown_json"),
  myfxbookRating: real("myfxbook_rating"),
});

export const appStoreSnapshots = sqliteTable("app_store_snapshots", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  competitorId: text("competitor_id").notNull().references(() => competitors.id),
  entityLabel: text("entity_label"),
  iosAppId: text("ios_app_id").notNull(),
  marketCode: text("market_code").notNull(),
  snapshotDate: text("snapshot_date").notNull(),
  iosRating: real("ios_rating"),
  iosRatingCount: integer("ios_rating_count"),
});

// Per-actor-run diagnostics for Apify-based scrapers (Phase 1, SOCIAL-05, D-08).
// Mirrors scrapers/db_utils.py CREATE TABLE apify_run_logs.
export const apifyRunLogs = sqliteTable("apify_run_logs", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  scraperRunId: integer("scraper_run_id").references(() => scraperRuns.id),
  apifyRunId: text("apify_run_id"),
  actorId: text("actor_id").notNull(),
  actorVersion: text("actor_version"),
  competitorId: text("competitor_id").notNull().references(() => competitors.id),
  platform: text("platform").notNull(),
  marketCode: text("market_code").notNull().default("global"),
  status: text("status").notNull(),  // 'success' | 'failed' | 'empty'
  datasetCount: integer("dataset_count").default(0),
  costUsd: real("cost_usd"),
  errorMessage: text("error_message"),
  startedAt: text("started_at").notNull(),
  finishedAt: text("finished_at"),
});

// Phase 1 schema-only delta (per INFRA-05). Phase 3 owns the BigQuery sync code.
export const shareOfSearchSnapshots = sqliteTable("share_of_search_snapshots", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  marketCode: text("market_code").notNull(),
  term: text("term").notNull(),
  brand: text("brand").notNull(),
  shareOfSearch: real("share_of_search").notNull(),
  capturedAt: text("captured_at").notNull(),
  snapshotDate: text("snapshot_date").notNull(),
});

export const wikifxSnapshots = sqliteTable("wikifx_snapshots", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  competitorId: text("competitor_id").notNull().references(() => competitors.id),
  snapshotDate: text("snapshot_date").notNull(),
  wikifxScore: real("wikifx_score"),
  accountsJson: text("accounts_json"),
  marketingStrategyJson: text("marketing_strategy_json"),
  bizAreaJson: text("biz_area_json"),
});

export const accountTypeSnapshots = sqliteTable("account_type_snapshots", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  competitorId: text("competitor_id").notNull().references(() => competitors.id),
  snapshotDate: text("snapshot_date").notNull(),
  accountsDetailedJson: text("accounts_detailed_json"),
  sourceUrls: text("source_urls"),
  extractionMethod: text("extraction_method"),
  reconciliationJson: text("reconciliation_json"),
  marketCode: text("market_code").notNull().default("global"),
});

export const newsItems = sqliteTable("news_items", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  competitorId: text("competitor_id").notNull().references(() => competitors.id),
  title: text("title").notNull(),
  url: text("url"),
  source: text("source"),
  publishedAt: text("published_at"),
  sentiment: text("sentiment"),
});

export const changeEvents = sqliteTable("change_events", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  competitorId: text("competitor_id").notNull().references(() => competitors.id),
  domain: text("domain").notNull(),
  fieldName: text("field_name").notNull(),
  oldValue: text("old_value"),
  newValue: text("new_value"),
  severity: text("severity").notNull(),
  detectedAt: text("detected_at").notNull().default(new Date().toISOString()),
  marketCode: text("market_code").notNull().default("global"),
});

export const aiInsights = sqliteTable("ai_insights", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  competitorId: text("competitor_id").notNull().references(() => competitors.id),
  generatedAt: text("generated_at").notNull(),
  summary: text("summary"),
  keyFindingsJson: text("key_findings_json"),
  implications: text("implications"),
  actionsJson: text("actions_json"),
});

export const aiPortfolioInsights = sqliteTable("ai_portfolio_insights", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  generatedAt: text("generated_at").notNull(),
  summary: text("summary"),
  actionsJson: text("actions_json"),
});

export const scraperRuns = sqliteTable("scraper_runs", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  scraperName: text("scraper_name").notNull(),
  startedAt: text("started_at").notNull(),
  finishedAt: text("finished_at"),
  status: text("status").notNull().default("running"),
  errorMessage: text("error_message"),
  recordsProcessed: integer("records_processed").default(0),
  // Noise-floor metric: how many raw diffs vs how many made it past the
  // threshold filter in scrapers/change_thresholds.py. A healthy ratio is
  // registered << raw. Surface on /admin page later.
  rawDeltasCount: integer("raw_deltas_count").notNull().default(0),
  registeredEventsCount: integer("registered_events_count").notNull().default(0),
});
