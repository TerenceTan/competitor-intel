"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import Link from "next/link";
import { timeAgo, tierLabel } from "@/lib/utils";
import { ArrowUpDown, ArrowUp, ArrowDown, RefreshCw } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";

interface CompetitorRow {
  id: string;
  name: string;
  tier: number;
  website: string;
  maxLeverage: number | null;
  minDepositUsd: number | null;
  instrumentsCount: number | null;
  promoCount: number;
  trustpilotScore: number | null;
  latestInsightSummary: string | null;
  latestInsightDate: string | null;
  lastUpdated: string | null;
}

function TierBadge({ tier }: { tier: number }) {
  const classes: Record<number, string> = {
    1: "bg-blue-50 text-blue-700 border-blue-200",
    2: "bg-indigo-50 text-indigo-700 border-indigo-200",
    3: "bg-gray-100 text-gray-600 border-gray-200",
  };
  const cls = classes[tier] ?? classes[3];
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}
    >
      {tierLabel(tier)}
    </span>
  );
}

type SortKey = keyof CompetitorRow;

function SortIcon({ col, sortKey, sortDir }: { col: SortKey; sortKey: SortKey; sortDir: "asc" | "desc" }) {
  if (sortKey !== col) {
    return <ArrowUpDown className="w-3 h-3 inline ml-1 text-gray-400" />;
  }
  const Icon = sortDir === "asc" ? ArrowUp : ArrowDown;
  return <Icon className="w-3 h-3 inline ml-1 text-primary" />;
}

function Th({
  children,
  col,
  sortKey,
  sortDir,
  onSort,
}: {
  children: React.ReactNode;
  col: SortKey;
  sortKey: SortKey;
  sortDir: "asc" | "desc";
  onSort: (col: SortKey) => void;
}) {
  return (
    <th
      scope="col"
      className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider cursor-pointer hover:text-gray-900 hover:bg-gray-50 select-none whitespace-nowrap transition-colors"
      onClick={() => onSort(col)}
    >
      {children}
      <SortIcon col={col} sortKey={sortKey} sortDir={sortDir} />
    </th>
  );
}

export default function CompetitorsPage() {
  const [data, setData] = useState<CompetitorRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("tier");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const r = await fetch("/api/competitors");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setData(d);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  const sorted = useMemo(() => {
    return [...data].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (typeof av === "number" && typeof bv === "number") {
        return sortDir === "asc" ? av - bv : bv - av;
      }
      const as = String(av).toLowerCase();
      const bs = String(bv).toLowerCase();
      return sortDir === "asc" ? as.localeCompare(bs) : bs.localeCompare(as);
    });
  }, [data, sortKey, sortDir]);

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Competitors</h1>
        <p className="text-gray-500 text-sm mt-1">
          All tracked brokers with latest data — click a row to view full
          details
        </p>
      </div>

      {error ? (
        <EmptyState
          icon={RefreshCw}
          title="Failed to load competitors"
          description="Something went wrong while fetching data."
          action={
            <button onClick={fetchData} className="px-4 py-2 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary/90 active:bg-primary/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2">
              Try again
            </button>
          }
        />
      ) : loading ? (
        <>
          {/* Desktop skeleton */}
          <div className="hidden md:block rounded-xl border border-gray-200 overflow-x-auto bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50/80">
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Broker</th>
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Max Leverage</th>
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Min Deposit</th>
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Active Promos</th>
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Trustpilot</th>
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Latest AI Insight</th>
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Last Updated</th>
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: 7 }).map((_, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="px-4 py-4"><Skeleton className="h-4 w-32" /><Skeleton className="h-4 w-16 mt-2" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-12" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-14" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-5 w-5 mx-auto rounded-full" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-10" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-full" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-16" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Mobile skeleton */}
          <div className="md:hidden space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
                <Skeleton className="h-5 w-32" />
                <div className="grid grid-cols-2 gap-3">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-full" />
                </div>
              </div>
            ))}
          </div>
        </>
      ) : sorted.length === 0 ? (
        <EmptyState
          title="No competitors found"
          description="No competitor data is available yet."
        />
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block rounded-xl border border-gray-200 overflow-x-auto bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50/80">
                  <Th col="name" sortKey={sortKey} sortDir={sortDir} onSort={handleSort}>Broker</Th>
                  <Th col="maxLeverage" sortKey={sortKey} sortDir={sortDir} onSort={handleSort}>Max Leverage</Th>
                  <Th col="minDepositUsd" sortKey={sortKey} sortDir={sortDir} onSort={handleSort}>Min Deposit</Th>
                  <Th col="promoCount" sortKey={sortKey} sortDir={sortDir} onSort={handleSort}>Active Promos</Th>
                  <Th col="trustpilotScore" sortKey={sortKey} sortDir={sortDir} onSort={handleSort}>Trustpilot</Th>
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                    Latest AI Insight
                  </th>
                  <Th col="lastUpdated" sortKey={sortKey} sortDir={sortDir} onSort={handleSort}>Last Updated</Th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((row, idx) => (
                  <tr
                    key={row.id}
                    className={`border-b border-gray-100 hover:bg-primary/[0.03] transition-colors cursor-pointer ${
                      idx === sorted.length - 1 ? "border-b-0" : ""
                    }`}
                    onClick={() => window.location.href = `/competitors/${row.id}`}
                  >
                    <td className="px-4 py-4">
                      <Link
                        href={`/competitors/${row.id}`}
                        className="group/link"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div className="font-semibold text-gray-900 group-hover/link:text-primary transition-colors">{row.name}</div>
                        <div className="mt-1">
                          <TierBadge tier={row.tier} />
                        </div>
                      </Link>
                    </td>
                    <td className="px-4 py-4 text-gray-700 font-mono">
                      {row.maxLeverage ? `1:${row.maxLeverage}` : "—"}
                    </td>
                    <td className="px-4 py-4 text-gray-700 font-mono">
                      {row.minDepositUsd != null
                        ? `$${row.minDepositUsd.toLocaleString()}`
                        : "—"}
                    </td>
                    <td className="px-4 py-4 text-center">
                      {row.promoCount > 0 ? (
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white bg-primary">
                          {row.promoCount}
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-4 text-gray-700">
                      {row.trustpilotScore != null ? (
                        <span className="flex items-center gap-1">
                          <span className="text-yellow-400">★</span>
                          {row.trustpilotScore.toFixed(1)}
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-4 text-gray-500 max-w-xs">
                      {row.latestInsightSummary ? (
                        <p className="truncate text-xs" title={row.latestInsightSummary}>
                          {row.latestInsightSummary}
                        </p>
                      ) : (
                        <span className="text-gray-400 text-xs">No insight</span>
                      )}
                    </td>
                    <td className="px-4 py-4 text-gray-500 text-xs whitespace-nowrap">
                      {row.lastUpdated ? timeAgo(row.lastUpdated) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile card view */}
          <div className="md:hidden space-y-3">
            {sorted.map((row) => (
              <Link key={row.id} href={`/competitors/${row.id}`} className="block">
                <div className="rounded-xl border border-gray-200 bg-white p-4 hover:border-primary/30 hover:shadow-sm transition-all space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-semibold text-gray-900">{row.name}</p>
                      <div className="mt-1"><TierBadge tier={row.tier} /></div>
                    </div>
                    <span className="text-gray-500 text-xs whitespace-nowrap">
                      {row.lastUpdated ? timeAgo(row.lastUpdated) : "—"}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                    <div>
                      <span className="text-gray-500 uppercase tracking-wider">Leverage</span>
                      <p className="text-gray-700 font-mono mt-0.5">{row.maxLeverage ? `1:${row.maxLeverage}` : "—"}</p>
                    </div>
                    <div>
                      <span className="text-gray-500 uppercase tracking-wider">Min Deposit</span>
                      <p className="text-gray-700 font-mono mt-0.5">{row.minDepositUsd != null ? `$${row.minDepositUsd.toLocaleString()}` : "—"}</p>
                    </div>
                    <div>
                      <span className="text-gray-500 uppercase tracking-wider">Promos</span>
                      <p className="text-gray-700 mt-0.5">{row.promoCount > 0 ? row.promoCount : "—"}</p>
                    </div>
                    <div>
                      <span className="text-gray-500 uppercase tracking-wider">Trustpilot</span>
                      <p className="text-gray-700 mt-0.5">{row.trustpilotScore != null ? `★ ${row.trustpilotScore.toFixed(1)}` : "—"}</p>
                    </div>
                  </div>
                  {row.latestInsightSummary && (
                    <p className="text-gray-500 text-xs line-clamp-2">{row.latestInsightSummary}</p>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
