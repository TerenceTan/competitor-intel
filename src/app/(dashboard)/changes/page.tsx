"use client";

import { useEffect, useState, useCallback } from "react";
import { timeAgo } from "@/lib/utils";

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

function SeverityBadge({ severity }: { severity: string }) {
  const colorMap: Record<string, string> = {
    critical: "bg-red-50 text-red-700 border-red-200",
    high: "bg-orange-50 text-orange-700 border-orange-200",
    medium: "bg-amber-50 text-amber-700 border-amber-200",
    low: "bg-blue-50 text-blue-700 border-blue-200",
  };
  const cls =
    colorMap[severity?.toLowerCase()] ??
    "bg-gray-100 text-gray-600 border-gray-200";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}
    >
      {severity ?? "unknown"}
    </span>
  );
}

export default function ChangesPage() {
  const [changes, setChanges] = useState<ChangeEvent[]>([]);
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const [filterCompetitor, setFilterCompetitor] = useState("all");
  const [filterDomain, setFilterDomain] = useState("all");
  const [filterSeverity, setFilterSeverity] = useState("all");

  const fetchData = useCallback(async () => {
    try {
      const [changesRes, competitorsRes] = await Promise.all([
        fetch("/api/changes"),
        fetch("/api/competitors"),
      ]);
      const changesData = await changesRes.json();
      const competitorsData = await competitorsRes.json();
      setChanges(changesData);
      setCompetitors(competitorsData);
      setLastRefresh(new Date());
    } catch (err) {
      console.error("Failed to fetch changes", err);
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

  const filtered = changes.filter((c) => {
    if (filterCompetitor !== "all" && c.competitorId !== filterCompetitor)
      return false;
    if (filterDomain !== "all" && c.domain !== filterDomain) return false;
    if (filterSeverity !== "all" && c.severity?.toLowerCase() !== filterSeverity)
      return false;
    return true;
  });

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
    "bg-white border border-gray-200 text-gray-700 text-sm rounded-lg px-3 py-1.5 outline-none focus:border-blue-500";

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
            className="text-xs hover:underline mt-1"
            style={{ color: "#0064FA" }}
          >
            Refresh now
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={filterCompetitor}
          onChange={(e) => setFilterCompetitor(e.target.value)}
          className={selectClass}
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
        >
          {SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s === "all" ? "All Severities" : s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          ))}
        </select>

        <button
          onClick={exportCSV}
          className="px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 text-gray-500 hover:text-gray-700 hover:border-gray-400 transition-colors"
        >
          Export CSV ({filtered.length})
        </button>
      </div>

      {/* Table */}
      {loading ? (
        <div
          className="rounded-xl border border-gray-200 p-12 text-center text-gray-500 bg-white"
        >
          Loading changes...
        </div>
      ) : filtered.length === 0 ? (
        <div
          className="rounded-xl border border-gray-200 p-12 text-center text-gray-500 bg-white"
        >
          No changes match the current filters.
        </div>
      ) : (
        <div
          className="rounded-xl border border-gray-200 overflow-x-auto bg-white"
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  When
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Competitor
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Domain
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Field
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Old Value
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  New Value
                </th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Severity
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((event, idx) => (
                <tr
                  key={event.id}
                  className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${
                    idx === filtered.length - 1 ? "border-b-0" : ""
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
                  <td className="px-4 py-3 text-gray-500 text-xs max-w-[140px] truncate">
                    {event.oldValue ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-700 text-xs max-w-[140px] truncate">
                    {event.newValue ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    <SeverityBadge severity={event.severity} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
