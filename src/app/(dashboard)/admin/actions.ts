"use server";

import { db } from "@/db";
import { competitors } from "@/db/schema";
import { eq } from "drizzle-orm";
import { revalidatePath } from "next/cache";

export interface CompetitorFormData {
  id: string;
  name: string;
  tier: number;
  website: string;
  isSelf: boolean;
  scraperConfig: {
    pricing_url: string | null;
    pricing_wait_selector: string | null;
    account_urls: string[];
    promo_url: string | null;
    youtube_query: string | null;
    facebook_slug: string | null;
    instagram_handle: string | null;
    x_handle: string | null;
    wikifx_id: string | null;
    tradingfinder_slug: string | null;
    dailyforex_slug: string | null;
    myfxbook_slug: string | null;
    entities: Array<{
      label: string;
      trustpilot_slug: string | null;
      fpa_slug: string | null;
      ios_app_id: string | null;
      android_package: string | null;
    }>;
    known_leverage: string[] | null;
    known_account_types: string[] | null;
    known_min_deposit_usd: number | null;
  };
}

function validateId(id: string): string | null {
  if (!id) return "ID is required";
  if (!/^[a-z0-9-]+$/.test(id)) return "ID must be lowercase alphanumeric with hyphens";
  if (id.length > 50) return "ID too long";
  return null;
}

function validateForm(data: CompetitorFormData): string | null {
  const idErr = validateId(data.id);
  if (idErr) return idErr;
  if (!data.name.trim()) return "Name is required";
  if (![1, 2].includes(data.tier)) return "Tier must be 1 or 2";
  if (!data.website.trim()) return "Website is required";
  if (!data.scraperConfig.entities?.length) return "At least one entity is required";
  for (const entity of data.scraperConfig.entities) {
    if (!entity.label.trim()) return "Each entity must have a label";
  }
  return null;
}

export async function createCompetitor(data: CompetitorFormData) {
  const error = validateForm(data);
  if (error) return { error };

  const existing = await db.select({ id: competitors.id }).from(competitors).where(eq(competitors.id, data.id)).limit(1);
  if (existing.length > 0) return { error: `Competitor "${data.id}" already exists` };

  await db.insert(competitors).values({
    id: data.id,
    name: data.name.trim(),
    tier: data.tier,
    website: data.website.trim(),
    isSelf: data.isSelf ? 1 : 0,
    createdAt: new Date().toISOString(),
    scraperConfig: JSON.stringify(data.scraperConfig),
    marketConfig: null,
  });

  revalidatePath("/admin");
  return { success: true };
}

export async function updateCompetitor(id: string, data: CompetitorFormData) {
  const error = validateForm(data);
  if (error) return { error };

  await db
    .update(competitors)
    .set({
      name: data.name.trim(),
      tier: data.tier,
      website: data.website.trim(),
      isSelf: data.isSelf ? 1 : 0,
      scraperConfig: JSON.stringify(data.scraperConfig),
    })
    .where(eq(competitors.id, id));

  revalidatePath("/admin");
  return { success: true };
}

/* ------------------------------------------------------------------ */
/*  Auto-discovery: scrape website to pre-fill config                  */
/* ------------------------------------------------------------------ */

interface DiscoveredConfig {
  pricing_url: string | null;
  account_urls: string[];
  promo_url: string | null;
  youtube_query: string | null;
  facebook_slug: string | null;
  instagram_handle: string | null;
  x_handle: string | null;
  wikifx_id: string | null;
  tradingfinder_slug: string | null;
  dailyforex_slug: string | null;
  myfxbook_slug: string | null;
  trustpilot_slug: string | null;
  fpa_slug: string | null;
  ios_app_id: string | null;
  android_package: string | null;
}

async function fetchHtml(url: string): Promise<string | null> {
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0 (compatible; PepperstoneBot/1.0)" },
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  }
}

function extractSocialLinks(html: string) {
  const result: Partial<DiscoveredConfig> = {};

  // Facebook
  const fbMatch = html.match(/href="https?:\/\/(?:www\.)?facebook\.com\/([a-zA-Z0-9._-]+)/i);
  if (fbMatch) result.facebook_slug = fbMatch[1].replace(/\/$/, "");

  // Instagram
  const igMatch = html.match(/href="https?:\/\/(?:www\.)?instagram\.com\/([a-zA-Z0-9._-]+)/i);
  if (igMatch) result.instagram_handle = igMatch[1].replace(/\/$/, "");

  // X / Twitter
  const xMatch = html.match(/href="https?:\/\/(?:www\.)?(?:twitter|x)\.com\/([a-zA-Z0-9_]+)/i);
  if (xMatch) result.x_handle = xMatch[1].replace(/\/$/, "");

  // YouTube (extract channel name for query)
  const ytMatch = html.match(/href="https?:\/\/(?:www\.)?youtube\.com\/(?:@|c\/|channel\/|user\/)([a-zA-Z0-9_-]+)/i);
  if (ytMatch) result.youtube_query = ytMatch[1].replace(/[_-]+/g, " ");

  // Trustpilot
  const tpMatch = html.match(/href="https?:\/\/(?:www\.)?trustpilot\.com\/review\/([a-zA-Z0-9._-]+)/i);
  if (tpMatch) result.trustpilot_slug = tpMatch[1];

  return result;
}

function extractPageLinks(html: string, baseUrl: string) {
  const result: { pricing_url: string | null; account_urls: string[]; promo_url: string | null } = {
    pricing_url: null,
    account_urls: [],
    promo_url: null,
  };

  // Normalize base URL
  const base = baseUrl.replace(/\/$/, "");

  // Find all href values
  const hrefRe = /href="([^"]+)"/gi;
  const allLinks: string[] = [];
  let m;
  while ((m = hrefRe.exec(html)) !== null) {
    let href = m[1];
    if (href.startsWith("/")) href = base + href;
    if (href.startsWith(base)) allLinks.push(href);
  }

  // Pricing / account type pages
  const pricingPatterns = /account[-_]?type|trading[-_]?account|pricing|spread/i;
  const promoPatterns = /promot|bonus|offer|campaign/i;
  const accountPatterns = /account|deposit|withdraw|funding|instrument|market/i;

  const seen = new Set<string>();
  for (const link of allLinks) {
    const path = link.replace(base, "").toLowerCase();
    if (seen.has(link) || path.includes("login") || path.includes("register") || path.includes("demo")) continue;
    seen.add(link);

    if (!result.pricing_url && pricingPatterns.test(path)) {
      result.pricing_url = link;
    } else if (!result.promo_url && promoPatterns.test(path)) {
      result.promo_url = link;
    } else if (result.account_urls.length < 4 && accountPatterns.test(path)) {
      result.account_urls.push(link);
    }
  }

  return result;
}

export async function discoverCompetitorConfig(
  name: string,
  website: string
): Promise<{ config: Partial<DiscoveredConfig>; errors: string[] }> {
  const errors: string[] = [];
  const config: Partial<DiscoveredConfig> = {};
  const domain = website.replace(/^https?:\/\//, "").replace(/\/$/, "");
  const baseUrl = `https://${domain}`;

  // 1. Fetch homepage — extract social links and page URLs
  const html = await fetchHtml(baseUrl);
  if (html) {
    const social = extractSocialLinks(html);
    Object.assign(config, social);

    const pages = extractPageLinks(html, baseUrl);
    if (pages.pricing_url) config.pricing_url = pages.pricing_url;
    if (pages.promo_url) config.promo_url = pages.promo_url;
    if (pages.account_urls.length > 0) config.account_urls = pages.account_urls;
  } else {
    errors.push("Could not fetch homepage");
  }

  // Default youtube_query from name
  if (!config.youtube_query) config.youtube_query = `${name} trading`;

  // 2. Search Trustpilot (if not found in homepage links)
  if (!config.trustpilot_slug) {
    config.trustpilot_slug = domain;
  }

  // 3. Generate likely slugs from domain/name
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  config.tradingfinder_slug = slug;
  config.dailyforex_slug = slug;
  config.myfxbook_slug = slug;

  // 4. Search WikiFX
  try {
    const wikiRes = await fetch(
      `https://www.wikifx.com/en/search.html?keyword=${encodeURIComponent(name)}`,
      {
        headers: { "User-Agent": "Mozilla/5.0 (compatible; PepperstoneBot/1.0)" },
        signal: AbortSignal.timeout(10000),
      }
    );
    if (wikiRes.ok) {
      const wikiHtml = await wikiRes.text();
      const wikiMatch = wikiHtml.match(/\/en\/dealer\/(\d+)\.html/);
      if (wikiMatch) config.wikifx_id = wikiMatch[1];
    }
  } catch {
    errors.push("WikiFX search timed out");
  }

  // 5. Search App Store (iTunes lookup by name)
  try {
    const itunesRes = await fetch(
      `https://itunes.apple.com/search?term=${encodeURIComponent(name)}&entity=software&limit=3`,
      { signal: AbortSignal.timeout(8000) }
    );
    if (itunesRes.ok) {
      const itunesData = await itunesRes.json();
      const results = itunesData.results as Array<{ trackId: number; sellerName: string; bundleId: string }>;
      const match = results.find(
        (r) =>
          r.sellerName?.toLowerCase().includes(name.toLowerCase().split(" ")[0]) ||
          r.bundleId?.toLowerCase().includes(slug.replace(/-/g, ""))
      );
      if (match) {
        config.ios_app_id = String(match.trackId);
        config.android_package = match.bundleId;
      }
    }
  } catch {
    errors.push("App Store search timed out");
  }

  return { config, errors };
}

export async function deleteCompetitor(id: string) {
  if (!id) return { error: "ID is required" };
  if (id === "pepperstone") return { error: "Cannot delete self-benchmark" };

  await db.delete(competitors).where(eq(competitors.id, id));

  revalidatePath("/admin");
  return { success: true };
}
