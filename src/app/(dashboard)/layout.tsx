import { db } from "@/db";
import { competitors, scraperRuns } from "@/db/schema";
import { desc } from "drizzle-orm";
import { Sidebar } from "@/components/layout/sidebar";
import { MobileHeader } from "@/components/layout/mobile-header";
import { formatDateTime } from "@/lib/utils";

// Dashboard pages query the SQLite DB at render time — never prerender statically
export const dynamic = "force-dynamic";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const allCompetitors = await db.select().from(competitors);
  const competitorCount = allCompetitors.length;
  const [lastRun] = await db
    .select({ finishedAt: scraperRuns.finishedAt })
    .from(scraperRuns)
    .orderBy(desc(scraperRuns.finishedAt))
    .limit(1);
  const lastUpdated = lastRun?.finishedAt ?? null;

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar competitorCount={competitorCount} />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Top header */}
        <header
          className="flex items-center justify-between px-4 md:px-6 py-3 border-b border-gray-200 shrink-0 bg-white"
        >
          <MobileHeader competitorCount={competitorCount} />
          <div className="flex items-center gap-4 text-sm text-gray-500">
            <span>
              Last updated:{" "}
              <span className="text-gray-700">
                {lastUpdated ? formatDateTime(lastUpdated) : "—"}
              </span>
            </span>
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: "#0064FA" }}
              title="Database connected"
            />
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 p-4 md:p-6 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
