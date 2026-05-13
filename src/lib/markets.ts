// Canonical APAC v1 market list — kept in sync with CONTEXT.md D2-01 and ROADMAP Phase 2
// (8 markets: SG, HK, TW, MY, TH, PH, ID, VN). Used by the dashboard's MarketSelector
// and per-market query filters.
//
// Note: scrapers/market_config.py is the legacy ScraperAPI list and still references
// out-of-scope CN + MN entries because that file predates the APAC v1 scoping. It is
// being deprecated by Phase 2's Apify cutover and will be reconciled in plan 02-02 —
// do NOT mirror this file there.

export const PRIORITY_MARKETS = [
  "sg",
  "hk",
  "tw",
  "my",
  "th",
  "ph",
  "id",
  "vn",
] as const;

export type MarketCode = (typeof PRIORITY_MARKETS)[number];

export const MARKET_NAMES: Record<MarketCode, string> = {
  sg: "Singapore",
  hk: "Hong Kong",
  tw: "Taiwan",
  my: "Malaysia",
  th: "Thailand",
  ph: "Philippines",
  id: "Indonesia",
  vn: "Vietnam",
};

export const MARKET_FLAGS: Record<MarketCode, string> = {
  sg: "🇸🇬",
  hk: "🇭🇰",
  tw: "🇹🇼",
  my: "🇲🇾",
  th: "🇹🇭",
  ph: "🇵🇭",
  id: "🇮🇩",
  vn: "🇻🇳",
};

export function isMarketCode(value: string | null | undefined): value is MarketCode {
  return !!value && (PRIORITY_MARKETS as readonly string[]).includes(value);
}

// Normalises a raw URL param to a valid market code or null (treat invalid as "all markets").
export function parseMarketParam(value: string | null | undefined): MarketCode | null {
  return isMarketCode(value) ? value : null;
}
