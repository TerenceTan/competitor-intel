/** Scraper definitions used by admin and executive summary pages */
export const SCRAPERS = [
  { name: "pricing-scraper", dbName: "pricing_scraper", label: "Pricing Scraper", domain: "pricing" },
  { name: "promo-scraper", dbName: "promo_scraper", label: "Promo Scraper", domain: "promotions" },
  { name: "social-scraper", dbName: "social_scraper", label: "Social Scraper", domain: "social" },
  { name: "reputation-scraper", dbName: "reputation_scraper", label: "Reputation Scraper", domain: "reputation" },
  { name: "wikifx-scraper", dbName: "wikifx_scraper", label: "WikiFX Scraper", domain: "wikifx" },
  { name: "news-scraper", dbName: "news_scraper", label: "News Scraper", domain: "news" },
  { name: "ai-analysis", dbName: "ai_analyzer", label: "AI Analysis", domain: "insights" },
] as const;

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
  "telegram",
  "facebook",
  "instagram",
  "line",
  "zalo",
] as const;
