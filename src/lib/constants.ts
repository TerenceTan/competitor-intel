/**
 * Scraper definitions used by admin and executive summary pages.
 *
 * `cadenceHours` is the expected gap between successful runs (matches the cron
 * schedule in SCRAPER_SCHEDULE.md). The stale-data banner flags a scraper as
 * stale when its latest successful run is older than cadenceHours * 2.5 — i.e.
 * it has missed more than two expected cycles. That buffer is deliberate:
 * CRON misfires or a single transient failure shouldn't surface a scary red
 * banner on the dashboard, but two missed cycles in a row means the user can
 * no longer trust the data and needs to act.
 */
export const SCRAPERS = [
  { name: "pricing-scraper", dbName: "pricing_scraper", label: "Pricing Scraper", domain: "pricing", cadenceHours: 168 },
  { name: "account-types-scraper", dbName: "account_types_scraper", label: "Account Types Scraper", domain: "account_types", cadenceHours: 48 },
  { name: "promo-scraper", dbName: "promo_scraper", label: "Promo Scraper", domain: "promotions", cadenceHours: 48 },
  { name: "social-scraper", dbName: "social_scraper", label: "Social Scraper", domain: "social", cadenceHours: 168 },
  { name: "apify-social", dbName: "apify_social", label: "Apify Social Scraper", domain: "social", cadenceHours: 168 },
  { name: "reputation-scraper", dbName: "reputation_scraper", label: "Reputation Scraper", domain: "reputation", cadenceHours: 72 },
  { name: "wikifx-scraper", dbName: "wikifx_scraper", label: "WikiFX Scraper", domain: "wikifx", cadenceHours: 168 },
  { name: "news-scraper", dbName: "news_scraper", label: "News Scraper", domain: "news", cadenceHours: 6 },
  { name: "ai-analysis", dbName: "ai_analyzer", label: "AI Analysis", domain: "insights", cadenceHours: 24 },
] as const;

/**
 * Maps Apify actor_id (the value stored in apify_run_logs.actor_id by
 * scrapers/apify_social.py) to the dbName of the SCRAPERS entry that owns it.
 *
 * Source of truth on the Python side: scrapers/apify_social.py:79 (ACTOR_ID).
 * When Phase 2 adds Instagram (apify/instagram-scraper) and X (apidojo/tweet-scraper)
 * actors, add entries here AND mirror them in the corresponding scraper module.
 *
 * Used by /admin/data-health to look up per-actor zero-result counts by equality
 * (replaces a substring-match that silently returned 0 — see code review WR-01 / SC3).
 */
export const ACTOR_TO_SCRAPER: Record<string, string> = {
  "apify/facebook-posts-scraper": "apify_social",
  "apify/instagram-profile-scraper": "apify_social",
  "kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest": "apify_social",
};

/** Multiplier applied to cadenceHours to get the stale threshold — 2.5 cycles of grace. */
export const STALE_MULTIPLIER = 2.5;

/** Country flag emoji by market code */
export const MARKET_FLAGS: Record<string, string> = {
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

/** Social media platforms tracked across competitor profiles */
export const PLATFORMS = [
  "youtube",
  "facebook",
  "instagram",
  "x",
] as const;
