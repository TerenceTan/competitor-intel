// Mirrors scrapers/market_config.py — keep in sync if the Python list changes.
// Used by the dashboard's MarketSelector and per-market query filters.

export const PRIORITY_MARKETS = [
  "sg",
  "my",
  "th",
  "vn",
  "id",
  "hk",
  "tw",
  "cn",
  "mn",
] as const;

export type MarketCode = (typeof PRIORITY_MARKETS)[number];

export const MARKET_NAMES: Record<MarketCode, string> = {
  sg: "Singapore",
  my: "Malaysia",
  th: "Thailand",
  vn: "Vietnam",
  id: "Indonesia",
  hk: "Hong Kong",
  tw: "Taiwan",
  cn: "China",
  mn: "Mongolia",
};

export const MARKET_FLAGS: Record<MarketCode, string> = {
  sg: "🇸🇬",
  my: "🇲🇾",
  th: "🇹🇭",
  vn: "🇻🇳",
  id: "🇮🇩",
  hk: "🇭🇰",
  tw: "🇹🇼",
  cn: "🇨🇳",
  mn: "🇲🇳",
};

export function isMarketCode(value: string | null | undefined): value is MarketCode {
  return !!value && (PRIORITY_MARKETS as readonly string[]).includes(value);
}

// Normalises a raw URL param to a valid market code or null (treat invalid as "all markets").
export function parseMarketParam(value: string | null | undefined): MarketCode | null {
  return isMarketCode(value) ? value : null;
}
