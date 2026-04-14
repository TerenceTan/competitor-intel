import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { db } from "@/db";
import { scraperRuns } from "@/db/schema";
import { desc } from "drizzle-orm";
import { SCRAPERS, STALE_MULTIPLIER } from "@/lib/constants";

type StaleEntry = { label: string; reason: string };

/**
 * Collapse recent runs into "latest per scraper" and flag any whose age
 * exceeds their per-scraper threshold. Pulled out of the component so the
 * React purity rule doesn't trip on `Date.now()` inside a component body —
 * this is a plain helper, not a component, even though the component that
 * calls it is a server component where impurity would be fine anyway.
 */
function findStaleScrapers(
  latestByScraper: Map<string, { finishedAt: string | null }>,
  nowMs: number,
): StaleEntry[] {
  const stale: StaleEntry[] = [];

  for (const scraper of SCRAPERS) {
    const latest = latestByScraper.get(scraper.dbName);
    const thresholdMs = scraper.cadenceHours * STALE_MULTIPLIER * 60 * 60 * 1000;

    if (!latest || !latest.finishedAt) {
      stale.push({ label: scraper.label, reason: "never completed a run" });
      continue;
    }

    const finishedMs = new Date(latest.finishedAt).getTime();
    if (Number.isNaN(finishedMs)) {
      stale.push({ label: scraper.label, reason: "unreadable run timestamp" });
      continue;
    }

    const ageMs = nowMs - finishedMs;
    if (ageMs > thresholdMs) {
      const ageHours = Math.round(ageMs / (60 * 60 * 1000));
      stale.push({
        label: scraper.label,
        reason: `last run ${ageHours}h ago (expected every ${scraper.cadenceHours}h)`,
      });
    }
  }

  return stale;
}

/**
 * Stale-data banner — top-of-dashboard red warning when any scraper has
 * missed more than two expected cycles. Silent when everything is fresh, so
 * the dashboard doesn't scream wolf on a single cron misfire. Each scraper
 * has its own threshold (cadenceHours * STALE_MULTIPLIER) because a news
 * scraper missing 12 hours is an emergency, but a weekly pricing scraper
 * missing 12 hours is nothing.
 *
 * The banner reads only the *latest* run per scraper. A scraper that has
 * never run at all is also flagged — missing data is worse than stale data.
 */
export async function StaleDataBanner() {
  // Pull recent runs and collapse to the latest per scraperName. Limit is
  // generous enough to cover several days of runs across all scrapers so
  // that every active scraper's latest entry is captured.
  const recentRuns = await db
    .select({
      scraperName: scraperRuns.scraperName,
      finishedAt: scraperRuns.finishedAt,
    })
    .from(scraperRuns)
    .orderBy(desc(scraperRuns.startedAt))
    .limit(200);

  const latestByScraper = new Map<string, { finishedAt: string | null }>();
  for (const run of recentRuns) {
    if (!latestByScraper.has(run.scraperName)) {
      latestByScraper.set(run.scraperName, { finishedAt: run.finishedAt });
    }
  }

  // This is an async server component with `dynamic = "force-dynamic"` on the
  // parent layout, so it renders fresh on every request. `Date.now()` is safe
  // here — the React purity rule is defending against client-side re-renders
  // that don't apply to server components.
  // eslint-disable-next-line react-hooks/purity
  const stale = findStaleScrapers(latestByScraper, Date.now());

  if (stale.length === 0) return null;

  return (
    <div className="w-full px-4 py-3 bg-red-50 border-b border-red-200 text-red-900 text-sm">
      <div className="flex items-start gap-3 max-w-6xl mx-auto">
        <AlertTriangle className="w-5 h-5 shrink-0 text-red-600 mt-0.5" aria-hidden="true" />
        <div className="flex-1 min-w-0">
          <p className="font-semibold">
            {stale.length === 1
              ? "1 scraper is stale — dashboard data may be out of date."
              : `${stale.length} scrapers are stale — dashboard data may be out of date.`}
          </p>
          <ul className="mt-1 space-y-0.5 text-red-800">
            {stale.map((s) => (
              <li key={s.label}>
                <span className="font-medium">{s.label}:</span> {s.reason}
              </li>
            ))}
          </ul>
          <Link
            href="/admin"
            className="inline-block mt-1 text-red-700 underline hover:text-red-900"
          >
            Check scraper status on admin page →
          </Link>
        </div>
      </div>
    </div>
  );
}
