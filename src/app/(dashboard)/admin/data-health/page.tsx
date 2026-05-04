import { db } from "@/db";
import { scraperRuns, apifyRunLogs } from "@/db/schema";
import { desc, sql, gte, and, eq } from "drizzle-orm";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { SCRAPERS } from "@/lib/constants";
import { formatDateTime } from "@/lib/utils";

// Force-dynamic — this page reads SQLite at request time. Inherits the
// (dashboard) route group layout (sidebar + market selector + stale banner)
// AND the existing auth middleware in src/middleware.ts (T-01-05-01 mitigation:
// /admin/* requires the auth_token cookie).
export const dynamic = "force-dynamic";

// D-06 — Apify monthly spend cap. Primary defense is the account-level cap set
// in Apify Console; this constant is what the dashboard renders to the operator.
const APIFY_MONTHLY_CAP_USD = 100;

export default async function DataHealthPage() {
  const sevenDaysAgoIso = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
  const monthStartIso = new Date(
    new Date().getFullYear(),
    new Date().getMonth(),
    1,
  ).toISOString();

  // Three parallel Drizzle queries — keeps page-load <500ms with the
  // idx_apify_runs_started_at index from Plan 01-01.
  const [latestRuns, costRow, zeroCounts] = await Promise.all([
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
              // Approximate match: zero-result actor IDs include the scraper
              // slug (e.g., apify_social) — only Apify-backed scrapers appear
              // here so the lookup naturally returns 0 for non-Apify scrapers.
              const zr =
                zeroCounts.find(
                  (z) => z.actorId.includes(s.name) || z.actorId.includes(s.dbName),
                )?.count ?? 0;
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
                      <span className="text-amber-600">{Number(zr)}</span>
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
