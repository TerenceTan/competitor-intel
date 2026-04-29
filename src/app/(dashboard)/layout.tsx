import { db } from "@/db";
import { competitors, scraperRuns } from "@/db/schema";
import { desc, eq } from "drizzle-orm";
import { Sidebar } from "@/components/layout/sidebar";
import { MobileHeader } from "@/components/layout/mobile-header";
import { BetaBar } from "@/components/layout/beta-bar";
import { StaleDataBanner } from "@/components/layout/stale-data-banner";
import { MarketSelector } from "@/components/layout/market-selector";
import { formatDateTime } from "@/lib/utils";

// Dashboard pages query the SQLite DB at render time — never prerender statically
export const dynamic = "force-dynamic";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const allCompetitors = await db.select().from(competitors).where(eq(competitors.isSelf, 0));
  const competitorCount = allCompetitors.length;
  const [lastRun] = await db
    .select({ finishedAt: scraperRuns.finishedAt })
    .from(scraperRuns)
    .orderBy(desc(scraperRuns.finishedAt))
    .limit(1);
  const lastUpdated = lastRun?.finishedAt ?? null;

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      {/* Notice bar — dismissible */}
      <BetaBar />

      {/* Stale-data warning — renders only when a scraper has missed >2 cycles */}
      <StaleDataBanner />

      {/* Skip to main content */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-12 focus:left-4 focus:z-[60] focus:px-4 focus:py-2 focus:bg-white focus:text-primary focus:rounded-lg focus:shadow-lg focus:text-sm focus:font-medium"
      >
        Skip to main content
      </a>

      <div className="flex flex-1 min-w-0">

      <Sidebar competitorCount={competitorCount} />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Top header */}
        <header
          className="flex items-center justify-between px-4 md:px-6 py-3 border-b border-gray-200 shrink-0 bg-white"
        >
          <MobileHeader competitorCount={competitorCount} />
          <div className="flex items-center gap-4 text-sm text-gray-500">
            <MarketSelector />
            <span>
              Data as of:{" "}
              <span className="text-gray-700">
                {lastUpdated ? formatDateTime(lastUpdated) : "—"}
              </span>
            </span>
            <div
              className="w-2 h-2 rounded-full bg-primary"
              title="Database connected"
            />
          </div>
        </header>

        {/* Main content */}
        <main id="main-content" className="flex-1 p-4 md:p-8 overflow-auto">
          {children}
        </main>
      </div>
      </div>
    </div>
  );
}
