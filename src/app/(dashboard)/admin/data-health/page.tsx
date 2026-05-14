import { db } from "@/db";
import { scraperRuns, apifyRunLogs, competitorMarkets } from "@/db/schema";
import { desc, sql, gte, and, eq } from "drizzle-orm";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { SCRAPERS, ACTOR_TO_SCRAPER } from "@/lib/constants";
import { formatDateTime } from "@/lib/utils";

// Force-dynamic — this page reads SQLite at request time. Inherits the
// (dashboard) route group layout (sidebar + market selector + stale banner)
// AND the existing auth middleware in src/middleware.ts (T-01-05-01 mitigation:
// /admin/* requires the auth_token cookie).
export const dynamic = "force-dynamic";

// D-06 — Apify monthly spend cap. Originally specified $100/mo assuming paid
// tier. As of Phase 1 EC2 deploy (2026-05-04) the account is on the free tier
// (~$5 monthly credit, platform-enforced — no user-settable Console limit).
// Reflect that here so the cost-pct indicator tells the truth. Bump back to
// 100 when the account upgrades for Phase 2 fanout.
const APIFY_MONTHLY_CAP_USD = 5;

export default async function DataHealthPage() {
  // Compute time-window cutoffs once at the top of the request. Server
  // components are evaluated per-request on the server (not re-rendered on
  // the client), so Date.now() is the correct way to source "now". React
  // 19's react-hooks/purity rule is conservative and flags it anyway —
  // disabled inline rather than refactored, because the alternative
  // (passing `now` as a prop or using next/headers) doesn't apply to a
  // page-level server component. Same pattern as competitors/[id]/page.tsx.
  // eslint-disable-next-line react-hooks/purity
  const now = Date.now();
  const sevenDaysAgoIso = new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString();
  const nowDate = new Date(now);
  const monthStartIso = new Date(
    nowDate.getFullYear(),
    nowDate.getMonth(),
    1,
  ).toISOString();

  // Four parallel Drizzle queries — keeps page-load <500ms with the
  // idx_apify_runs_started_at index from Plan 01-01. Plan 02-05 adds a
  // fourth zero-counts query GROUP BY (actor_id, market_code) so operators
  // can see WHICH markets are failing for each scraper — critical for
  // triage once the Phase 2 fanout flag is flipped.
  const [latestRuns, costRow, zeroCounts, zeroByMarket, seededRows] = await Promise.all([
    db
      .select({
        scraperName: scraperRuns.scraperName,
        finishedAt: scraperRuns.finishedAt,
        startedAt: scraperRuns.startedAt,
        status: scraperRuns.status,
        errorMessage: scraperRuns.errorMessage,
      })
      .from(scraperRuns)
      .orderBy(desc(scraperRuns.startedAt))
      .limit(200),

    db
      .select({
        // COALESCE handles the empty-table case so the cost panel always renders.
        total: sql<number>`COALESCE(SUM(${apifyRunLogs.costUsd}), 0)`,
      })
      .from(apifyRunLogs)
      .where(gte(apifyRunLogs.startedAt, monthStartIso))
      .then((r) => r[0] ?? { total: 0 }),

    db
      .select({
        actorId: apifyRunLogs.actorId,
        count: sql<number>`COUNT(*)`,
      })
      .from(apifyRunLogs)
      .where(
        and(
          eq(apifyRunLogs.status, "empty"),
          gte(apifyRunLogs.startedAt, sevenDaysAgoIso),
        ),
      )
      .groupBy(apifyRunLogs.actorId),

    // NEW (Phase 2 / Plan 02-05): per-market breakdown of zero-result counts.
    // Same WHERE clause as zeroCounts above; adds market_code to the GROUP BY.
    // Operator triage: when a scraper shows N zero-results, which markets are
    // failing? Indexed on started_at (idx_apify_runs_started_at, Plan 01-01)
    // so adding market_code to GROUP BY is cheap.
    db
      .select({
        actorId: apifyRunLogs.actorId,
        marketCode: apifyRunLogs.marketCode,
        count: sql<number>`COUNT(*)`,
      })
      .from(apifyRunLogs)
      .where(
        and(
          eq(apifyRunLogs.status, "empty"),
          gte(apifyRunLogs.startedAt, sevenDaysAgoIso),
        ),
      )
      .groupBy(apifyRunLogs.actorId, apifyRunLogs.marketCode),

    // Phase 2.1 / D2.1-12 — Markets with at least one curated row.
    // Counts DISTINCT market_code (via GROUP BY) so the operator can see
    // at-a-glance how many of the 8 APAC v1 markets have been seeded by
    // marketing review. Empty table → 0 of 8 (visually unchanged from a
    // zero-cost panel).
    db
      .select({
        marketCode: competitorMarkets.marketCode,
      })
      .from(competitorMarkets)
      .groupBy(competitorMarkets.marketCode),
  ]);

  // Collapse latestRuns into a Map keyed by scraperName (most-recent wins per name).
  const latestByScraper = new Map<
    string,
    { finishedAt: string | null; status: string; error: string | null }
  >();
  for (const r of latestRuns) {
    if (!latestByScraper.has(r.scraperName)) {
      latestByScraper.set(r.scraperName, {
        finishedAt: r.finishedAt,
        status: r.status,
        error: r.errorMessage,
      });
    }
  }

  // Phase 2.1 / D2.1-12 — seeded-markets tile data. Each row in seededRows
  // is a distinct marketCode (the GROUP BY collapses duplicates), so the
  // length is the count of markets with at least one curated competitor.
  const seededMarkets = seededRows.length;

  // SQLite returns SUM as a string under some adapter paths — Number() coerces
  // safely; COALESCE above guarantees non-null.
  const totalCost = Number(costRow.total) || 0;
  const costPct = Math.round((totalCost / APIFY_MONTHLY_CAP_USD) * 100);
  const costColor =
    costPct >= 70 ? "text-red-600" : costPct >= 40 ? "text-amber-600" : "text-green-700";

  // Use Intl.NumberFormat for currency — never hand-roll $X.XX templates.
  const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Data Health</h1>
        <p className="text-sm text-gray-500 mt-1">
          Per-scraper status, zero-result counts (last 7 days), and Apify cost-to-date.
        </p>
      </div>

      <section className="rounded-xl border border-gray-200 bg-white p-6">
        <h2 className="text-sm font-medium text-gray-700 mb-2">Apify Cost (this month)</h2>
        <p className={`text-3xl font-semibold ${costColor}`}>
          {usd.format(totalCost)}
          <span className="text-base font-normal text-gray-500 ml-2">
            of {usd.format(APIFY_MONTHLY_CAP_USD)}/mo cap ({costPct}%)
          </span>
        </p>
      </section>

      {/* Phase 2.1 / D2.1-12 — Per-market curation status tile.
          Counts distinct market_code values in competitor_markets so the
          operator can see at-a-glance how much of the curation review has
          landed in the DB. Additive to (does not replace) the existing
          Phase 2 per-market zero-result breakdown rendered in the Scrapers
          table below. */}
      <section className="rounded-xl border border-gray-200 bg-white p-6">
        <h2 className="text-sm font-medium text-gray-700 mb-2">Per-market curation</h2>
        <p className="text-3xl font-semibold text-gray-900">
          {seededMarkets}
          <span className="text-base font-normal text-gray-500 ml-2">
            of 8 markets seeded
          </span>
        </p>
        {seededMarkets < 8 && (
          <p className="text-xs text-gray-500 mt-2">
            Markets without a curated competitor list fall back to Phase 2{" "}
            &ldquo;show all&rdquo; behavior. Run{" "}
            <code className="text-[11px] bg-gray-100 px-1 py-0.5 rounded">
              scrapers/admin/import_market_decisions.py
            </code>{" "}
            after the next marketing review, or edit per competitor at{" "}
            <code className="text-[11px] bg-gray-100 px-1 py-0.5 rounded">
              /admin/competitors/&lt;id&gt;
            </code>
            .
          </p>
        )}
      </section>

      <section className="rounded-xl border border-gray-200 bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Scraper</TableHead>
              <TableHead>Last run</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Zero-result runs (7d)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {SCRAPERS.map((s) => {
              const latest = latestByScraper.get(s.dbName);
              // Equality lookup via ACTOR_TO_SCRAPER (single source of truth in @/lib/constants).
              // Replaces a substring match that silently returned 0 because actor_id
              // ("apify/facebook-posts-scraper") never contains the dbName ("apify_social") —
              // see code review WR-01 / verification SC3.
              const zr =
                zeroCounts.find((z) => ACTOR_TO_SCRAPER[z.actorId] === s.dbName)?.count ?? 0;
              // Per-market breakdown for this scraper, sorted alphabetically by
              // market code (hk, id, my, ph, sg, th, tw, vn). 'global' rows are
              // excluded so Phase 1 free-tier users (APIFY_MARKETS_ENABLED unset,
              // all rows tagged 'global') see no badge — visual unchanged from
              // Phase 1 until the operator flips the flag. Same ACTOR_TO_SCRAPER
              // equality lookup as the total count above (NOT a substring match —
              // see WR-01).
              const breakdown = zeroByMarket
                .filter(
                  (z) =>
                    ACTOR_TO_SCRAPER[z.actorId] === s.dbName &&
                    z.marketCode !== "global",
                )
                .sort((a, b) => a.marketCode.localeCompare(b.marketCode))
                .map((z) => `${z.marketCode}:${Number(z.count)}`)
                .join(", ");
              const statusLabel = latest?.status ?? "never run";
              const statusClass =
                latest?.status === "success"
                  ? "text-green-700"
                  : latest?.status === "running"
                    ? "text-blue-600"
                    : "text-red-600";
              return (
                <TableRow key={s.name}>
                  <TableCell className="font-medium">{s.label}</TableCell>
                  <TableCell>
                    {latest?.finishedAt ? formatDateTime(latest.finishedAt) : "—"}
                  </TableCell>
                  <TableCell>
                    <span className={statusClass}>{statusLabel}</span>
                  </TableCell>
                  <TableCell className="text-right">
                    {Number(zr) > 0 ? (
                      <span className="inline-flex items-baseline gap-1.5">
                        <span className="text-amber-600">{Number(zr)}</span>
                        {breakdown && (
                          <span className="text-[10px] text-gray-500 font-mono">
                            ({breakdown})
                          </span>
                        )}
                      </span>
                    ) : (
                      "0"
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </section>
    </div>
  );
}
