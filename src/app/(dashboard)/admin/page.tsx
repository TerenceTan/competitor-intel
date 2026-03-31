import { db } from "@/db";
import { competitors, scraperRuns } from "@/db/schema";
import { desc } from "drizzle-orm";
import { Card } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import { Terminal, Server, Settings } from "lucide-react";
import { ScraperTable } from "@/components/admin/scraper-table";
import { SCRAPERS } from "@/lib/constants";

export default async function AdminPage() {
  const allCompetitors = await db.select().from(competitors);
  const recentRuns = await db
    .select()
    .from(scraperRuns)
    .orderBy(desc(scraperRuns.startedAt))
    .limit(50);

  // Map latest run per scraper
  const latestRunMap: Record<string, typeof recentRuns[0]> = {};
  for (const run of recentRuns) {
    if (!latestRunMap[run.scraperName]) {
      latestRunMap[run.scraperName] = run;
    }
  }

  return (
    <div className="space-y-8 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Admin Panel</h1>
        <p className="text-gray-500 text-sm mt-1">
          System configuration, scraper management, and data overview
        </p>
      </div>

      {/* Scraper Status Table */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Server className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold text-gray-900">Scraper Status</h2>
        </div>

        <ScraperTable scrapers={SCRAPERS} latestRunMap={latestRunMap} />
      </section>

      {/* System Logs */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Terminal className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold text-gray-900">System Logs</h2>
        </div>

        <Card
          className="p-6 border-gray-200 bg-white"
        >
          <p className="text-gray-500 text-sm mb-4">
            Logs are available via SSH on the server:
          </p>
          <div className="space-y-2">
            {SCRAPERS.map((scraper) => (
              <div
                key={scraper.name}
                className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 border border-gray-100"
              >
                <span className="text-gray-400 text-xs">$</span>
                <code className="text-blue-600 text-xs font-mono">
                  tail -f logs/{scraper.name}.log
                </code>
              </div>
            ))}
          </div>
        </Card>
      </section>

      {/* Competitor Config */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Settings className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold text-gray-900">
            Competitor Configuration
          </h2>
          <span className="text-gray-400 text-xs">(read-only)</span>
        </div>

        <Card
          className="border-gray-200 overflow-hidden bg-white"
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50/80">
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  ID
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Name
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Tier
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Website
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Added
                </th>
              </tr>
            </thead>
            <tbody>
              {allCompetitors.map((c, idx) => (
                <tr
                  key={c.id}
                  className={`border-b border-gray-100 ${
                    idx === allCompetitors.length - 1 ? "border-b-0" : ""
                  }`}
                >
                  <td className="px-4 py-3 text-gray-500 font-mono text-xs">
                    {c.id}
                  </td>
                  <td className="px-4 py-3 text-gray-900 font-medium">{c.name}</td>
                  <td className="px-4 py-3 text-gray-500">Tier {c.tier}</td>
                  <td className="px-4 py-3">
                    <a
                      href={c.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-gray-500 hover:text-primary text-xs transition-colors"
                    >
                      {c.website}
                    </a>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {formatDate(c.createdAt)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </section>
    </div>
  );
}
