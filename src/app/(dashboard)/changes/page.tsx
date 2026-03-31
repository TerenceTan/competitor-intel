"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { timeAgo } from "@/lib/utils";
import { RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { SeverityBadge } from "@/components/shared/severity-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { ChangesTimeline } from "@/components/charts/changes-timeline";

interface ChangeEvent {
  id: number;
  competitorId: string;
  competitorName: string;
  domain: string;
  fieldName: string;
  oldValue: string | null;
  newValue: string | null;
  severity: string;
  detectedAt: string;
}

interface Competitor {
  id: string;
  name: string;
}

const SEVERITY_OPTIONS = ["all", "critical", "high", "medium", "low"];

export default function ChangesPage() {
  const [changes, setChanges] = useState<ChangeEvent[]>([]);
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const [filterCompetitor, setFilterCompetitor] = useState("all");
  const [filterDomain, setFilterDomain] = useState("all");
  const [filterSeverity, setFilterSeverity] = useState("all");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const [changesRes, competitorsRes] = await Promise.all([
        fetch("/api/changes"),
        fetch("/api/competitors"),
      ]);
      if (!changesRes.ok) throw new Error(`Changes API: HTTP ${changesRes.status}`);
      if (!competitorsRes.ok) throw new Error(`Competitors API: HTTP ${competitorsRes.status}`);
      const changesData = await changesRes.json();
      const competitorsData = await competitorsRes.json();
      setChanges(changesData);
      setCompetitors(competitorsData);
      setLastRefresh(new Date());
    } catch (err) {
      console.error("Failed to fetch changes", err);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    // Auto-refresh every 5 minutes
    const interval = setInterval(fetchData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const domains = Array.from(new Set(changes.map((c) => c.domain))).sort();

  const filtered = useMemo(() => changes.filter((c) => {
    if (filterCompetitor !== "all" && c.competitorId !== filterCompetitor)
      return false;
    if (filterDomain !== "all" && c.domain !== filterDomain) return false;
    if (filterSeverity !== "all" && c.severity?.toLowerCase() !== filterSeverity)
      return false;
    return true;
  }), [changes, filterCompetitor, filterDomain, filterSeverity]);

  // Reset page when filters change
  useEffect(() => { setPage(1); }, [filterCompetitor, filterDomain, filterSeverity]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // Compute daily change counts for the timeline chart (last 14 days)
  const timelineData = useMemo(() => {
    const dayMap: Record<string, { count: number; critical: number; high: number; medium: number; low: number }> = {};
    // Initialize last 14 days
    for (let i = 13; i >= 0; i--) {
      const d = new Date(Date.now() - i * 24 * 60 * 60 * 1000);
      const key = d.toISOString().slice(0, 10);
      dayMap[key] = { count: 0, critical: 0, high: 0, medium: 0, low: 0 };
    }
    for (const c of changes) {
      const day = c.detectedAt.slice(0, 10);
      if (dayMap[day]) {
        dayMap[day].count++;
        const sev = c.severity?.toLowerCase() as "critical" | "high" | "medium" | "low";
        if (sev in dayMap[day]) dayMap[day][sev]++;
      }
    }
    return Object.entries(dayMap).map(([day, counts]) => ({ day, ...counts }));
  }, [changes]);

  function exportCSV() {
    const headers = [
      "Date",
      "Competitor",
      "Domain",
      "Field",
      "Old Value",
      "New Value",
      "Severity",
    ];
    const rows = filtered.map((c) => [
      c.detectedAt,
      c.competitorName,
      c.domain,
      c.fieldName,
      c.oldValue ?? "",
      c.newValue ?? "",
      c.severity,
    ]);
    const csv = [headers, ...rows]
      .map((r) =>
        r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")
      )
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "change-feed.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const selectClass =
    "bg-white border border-gray-200 text-gray-700 text-sm rounded-lg px-3 py-1.5 outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20 hover:border-gray-300";

  return (
    <div className="space-y-6 max-w-7xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Change Feed</h1>
          <p className="text-gray-500 text-sm mt-1">
            Detected changes across all competitors — auto-refreshes every 5
            minutes
          </p>
        </div>
        <div className="text-right">
          <p className="text-gray-400 text-xs">
            Last refresh: {timeAgo(lastRefresh.toISOString())}
          </p>
          <button
            onClick={fetchData}
            className="text-xs hover:underline mt-1 text-primary"
          >
            Refresh now
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-3">
        <select
          value={filterCompetitor}
          onChange={(e) => setFilterCompetitor(e.target.value)}
          className={selectClass}
          aria-label="Filter by competitor"
        >
          <option value="all">All Competitors</option>
          {competitors.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>

        <select
          value={filterDomain}
          onChange={(e) => setFilterDomain(e.target.value)}
          className={selectClass}
          aria-label="Filter by domain"
        >
          <option value="all">All Domains</option>
          {domains.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>

        <select
          value={filterSeverity}
          onChange={(e) => setFilterSeverity(e.target.value)}
          className={selectClass}
          aria-label="Filter by severity"
        >
          {SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s === "all" ? "All Severities" : s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          ))}
        </select>

        <button
          onClick={exportCSV}
          className="px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 text-gray-600 hover:text-gray-900 hover:border-gray-300 hover:bg-gray-50 active:bg-gray-100 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          Export CSV ({filtered.length})
        </button>
      </div>

      {/* Activity Timeline */}
      {!loading && !error && changes.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Activity (Last 14 Days)</h3>
          <ChangesTimeline data={timelineData} />
        </div>
      )}

      {/* Table */}
      {error ? (
        <EmptyState
          icon={RefreshCw}
          title="Failed to load changes"
          description="Something went wrong while fetching data."
          action={
            <button onClick={fetchData} className="px-4 py-2 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary/90 active:bg-primary/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2">
              Try again
            </button>
          }
        />
      ) : loading ? (
        <div className="rounded-xl border border-gray-200 overflow-x-auto bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50/80">
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">When</th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Competitor</th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Domain</th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Field</th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Old Value</th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">New Value</th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Severity</th>
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 8 }).map((_, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                  <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
                  <td className="px-4 py-3"><Skeleton className="h-4 w-16" /></td>
                  <td className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                  <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
                  <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
                  <td className="px-4 py-3"><Skeleton className="h-5 w-14 rounded-full" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No changes found"
          description="No changes match the current filters. Try adjusting your filters."
        />
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block rounded-xl border border-gray-200 overflow-x-auto bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50/80">
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">When</th>
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Competitor</th>
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Domain</th>
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Field</th>
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Change</th>
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Severity</th>
                </tr>
              </thead>
              <tbody>
                {paginated.map((event, idx) => (
                  <tr
                    key={event.id}
                    className={`border-b border-gray-100 hover:bg-primary/[0.03] transition-colors ${
                      idx === paginated.length - 1 ? "border-b-0" : ""
                    }`}
                  >
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                      {timeAgo(event.detectedAt)}
                    </td>
                    <td className="px-4 py-3 text-gray-900 font-medium">
                      {event.competitorName}
                    </td>
                    <td className="px-4 py-3 text-gray-500 capitalize">
                      {event.domain}
                    </td>
                    <td className="px-4 py-3 text-gray-700 font-medium">
                      {event.fieldName}
                    </td>
                    <td className="px-4 py-3 text-xs max-w-xs">
                      <div className="flex flex-col gap-1">
                        {event.oldValue && (
                          <span className="inline-flex items-center gap-1 line-through text-red-600/70 bg-red-50 rounded px-1.5 py-0.5 line-clamp-2">
                            {event.oldValue}
                          </span>
                        )}
                        {event.newValue && (
                          <span className="inline-flex items-center gap-1 text-green-700 bg-green-50 rounded px-1.5 py-0.5 line-clamp-2">
                            {event.newValue}
                          </span>
                        )}
                        {!event.oldValue && !event.newValue && (
                          <span className="text-gray-400">—</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <SeverityBadge severity={event.severity} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile card view */}
          <div className="md:hidden space-y-3">
            {paginated.map((event) => (
              <div key={event.id} className="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{event.competitorName}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{timeAgo(event.detectedAt)}</p>
                  </div>
                  <SeverityBadge severity={event.severity} />
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-gray-500 uppercase tracking-wider">Domain</span>
                    <p className="text-gray-700 capitalize mt-0.5">{event.domain}</p>
                  </div>
                  <div>
                    <span className="text-gray-500 uppercase tracking-wider">Field</span>
                    <p className="text-gray-700 font-medium mt-0.5">{event.fieldName}</p>
                  </div>
                </div>
                <div className="text-xs space-y-1">
                  {event.oldValue && (
                    <p className="line-through text-red-600/70 bg-red-50 rounded px-2 py-1 line-clamp-2">
                      {event.oldValue}
                    </p>
                  )}
                  {event.newValue && (
                    <p className="text-green-700 bg-green-50 rounded px-2 py-1 line-clamp-2">
                      {event.newValue}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-xs text-gray-500">
                Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length}
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:text-gray-900 hover:border-gray-300 hover:bg-gray-50 active:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:border-gray-200 disabled:hover:text-gray-500 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-sm text-gray-700 font-medium tabular-nums">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:text-gray-900 hover:border-gray-300 hover:bg-gray-50 active:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:border-gray-200 disabled:hover:text-gray-500 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
