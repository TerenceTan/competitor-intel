"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { tierLabel } from "@/lib/utils";
import { ArrowUpDown, ArrowUp, ArrowDown, RefreshCw } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { parseMarketParam, MARKET_NAMES } from "@/lib/markets";

interface CompetitorRow {
  id: string;
  name: string;
  tier: number;
  website: string;
  maxLeverage: number | null;
  minDepositUsd: number | null;
  instrumentsCount: number | null;
  spreadFrom: string | null;
  accountTypesCount: number;
  promoCount: number;
  trustpilotScore: number | null;
  findingCounts: Record<string, number>;
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

/** Colored Trustpilot score with bar indicator */
function TrustpilotCell({ score }: { score: number | null }) {
  if (score == null) return <span className="text-gray-300">—</span>;
  // Color thresholds: <3.5 red, <4.0 amber, <4.5 green-ish, >=4.5 green
  let color = "text-red-600 bg-red-50";
  let barColor = "bg-red-400";
  if (score >= 4.5) { color = "text-green-700 bg-green-50"; barColor = "bg-green-500"; }
  else if (score >= 4.0) { color = "text-emerald-700 bg-emerald-50"; barColor = "bg-emerald-400"; }
  else if (score >= 3.5) { color = "text-amber-700 bg-amber-50"; barColor = "bg-amber-400"; }

  const pct = Math.min((score / 5) * 100, 100);
  return (
    <div className="flex items-center gap-2">
      <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${color}`}>
        {score.toFixed(1)}
      </span>
      <div className="w-12 h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/** Severity dots for AI findings */
function FindingDots({ counts }: { counts: Record<string, number> }) {
  const total = Object.values(counts).reduce((s, n) => s + n, 0);
  if (total === 0) return <span className="text-gray-300 text-xs">—</span>;

  const severities = ["critical", "high", "medium", "low"] as const;
  const dotColors: Record<string, string> = {
    critical: "bg-red-500",
    high: "bg-orange-400",
    medium: "bg-amber-400",
    low: "bg-blue-400",
  };
  const textColors: Record<string, string> = {
    critical: "text-red-700",
    high: "text-orange-600",
    medium: "text-amber-600",
    low: "text-blue-600",
  };

  return (
    <div className="flex items-center gap-1.5">
      {severities.map((sev) => {
        const count = counts[sev] || 0;
        if (count === 0) return null;
        return (
          <span key={sev} className="flex items-center gap-0.5" title={`${count} ${sev}`}>
            <span className={`w-2 h-2 rounded-full ${dotColors[sev]}`} />
            <span className={`text-xs font-semibold ${textColors[sev]}`}>{count}</span>
          </span>
        );
      })}
    </div>
  );
}

/** Freshness dot: green <3d, amber <7d, red >7d, gray = no data */
function FreshnessDot({ lastUpdated, now }: { lastUpdated: string | null; now: number }) {
  if (!lastUpdated) return <span className="w-2 h-2 rounded-full bg-gray-300 inline-block" title="No data" />;
  const daysSince = (now - new Date(lastUpdated).getTime()) / (1000 * 60 * 60 * 24);
  let color = "bg-green-500";
  let label = "Fresh";
  if (daysSince > 7) { color = "bg-red-400"; label = `${Math.floor(daysSince)}d ago`; }
  else if (daysSince > 3) { color = "bg-amber-400"; label = `${Math.floor(daysSince)}d ago`; }
  return <span className={`w-2 h-2 rounded-full ${color} inline-block`} title={label} />;
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
  className = "",
}: {
  children: React.ReactNode;
  col: SortKey;
  sortKey: SortKey;
  sortDir: "asc" | "desc";
  onSort: (col: SortKey) => void;
  className?: string;
}) {
  return (
    <th
      scope="col"
      className={`text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider cursor-pointer hover:text-gray-900 hover:bg-gray-50 select-none whitespace-nowrap transition-colors ${className}`}
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
  const searchParams = useSearchParams();
  const market = parseMarketParam(searchParams.get("market"));

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const url = market ? `/api/competitors?market=${market}` : "/api/competitors";
      const r = await fetch(url);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setData(d);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [market]);

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

  // Stable timestamp for freshness dots — recalculated only when data changes
  const now = useMemo(() => Date.now(), [data]);

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
          All tracked brokers — click a row to view full details
        </p>
        {market && (
          <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            Pricing & promos: {MARKET_NAMES[market]}
            <span className="text-primary/60">— Trustpilot remains global</span>
          </div>
        )}
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
                  {["Broker", "Leverage", "Min Deposit", "Spread", "Instruments", "Promos", "Trustpilot", "AI Findings"].map((h) => (
                    <th key={h} scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: 7 }).map((_, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="px-4 py-4"><Skeleton className="h-4 w-32" /><Skeleton className="h-4 w-16 mt-2" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-12" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-14" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-16" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-12" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-5 w-5 rounded-full" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-16" /></td>
                    <td className="px-4 py-4"><Skeleton className="h-4 w-20" /></td>
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
                  <Th col="maxLeverage" sortKey={sortKey} sortDir={sortDir} onSort={handleSort}>Leverage</Th>
                  <Th col="minDepositUsd" sortKey={sortKey} sortDir={sortDir} onSort={handleSort}>Min Deposit</Th>
                  <Th col="spreadFrom" sortKey={sortKey} sortDir={sortDir} onSort={handleSort}>Spread</Th>
                  <Th col="instrumentsCount" sortKey={sortKey} sortDir={sortDir} onSort={handleSort}>Instruments</Th>
                  <Th col="promoCount" sortKey={sortKey} sortDir={sortDir} onSort={handleSort}>Promos</Th>
                  <Th col="trustpilotScore" sortKey={sortKey} sortDir={sortDir} onSort={handleSort}>Trustpilot</Th>
                  <th scope="col" className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider whitespace-nowrap">
                    AI Findings
                  </th>
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
                    {/* Broker name + tier + freshness */}
                    <td className="px-4 py-3.5">
                      <Link
                        href={`/competitors/${row.id}`}
                        className="group/link"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div className="flex items-center gap-2">
                          <FreshnessDot lastUpdated={row.lastUpdated} now={now} />
                          <span className="font-semibold text-gray-900 group-hover/link:text-primary transition-colors">{row.name}</span>
                        </div>
                        <div className="mt-1 ml-4">
                          <TierBadge tier={row.tier} />
                        </div>
                      </Link>
                    </td>

                    {/* Leverage */}
                    <td className="px-4 py-3.5 text-gray-700 font-mono text-xs">
                      {row.maxLeverage ? (
                        <span className={row.maxLeverage >= 1000 ? "font-bold text-gray-900" : ""}>
                          1:{row.maxLeverage.toLocaleString()}
                        </span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>

                    {/* Min Deposit */}
                    <td className="px-4 py-3.5 font-mono text-xs">
                      {row.minDepositUsd != null ? (
                        <span className={row.minDepositUsd === 0 ? "text-green-700 font-bold" : "text-gray-700"}>
                          {row.minDepositUsd === 0 ? "No min" : `$${row.minDepositUsd.toLocaleString()}`}
                        </span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>

                    {/* Spread */}
                    <td className="px-4 py-3.5 text-xs">
                      {row.spreadFrom ? (
                        <span className="text-gray-700 font-mono">{row.spreadFrom}</span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>

                    {/* Instruments */}
                    <td className="px-4 py-3.5 text-xs">
                      {row.instrumentsCount ? (
                        <span className="text-gray-700 font-mono">{row.instrumentsCount.toLocaleString()}</span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>

                    {/* Promos */}
                    <td className="px-4 py-3.5 text-center">
                      {row.promoCount > 0 ? (
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white bg-primary">
                          {row.promoCount}
                        </span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>

                    {/* Trustpilot with visual bar */}
                    <td className="px-4 py-3.5">
                      <TrustpilotCell score={row.trustpilotScore} />
                    </td>

                    {/* AI Findings severity dots */}
                    <td className="px-4 py-3.5">
                      <FindingDots counts={row.findingCounts ?? {}} />
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
                    <div className="flex items-center gap-2">
                      <FreshnessDot lastUpdated={row.lastUpdated} now={now} />
                      <div>
                        <p className="font-semibold text-gray-900">{row.name}</p>
                        <div className="mt-1"><TierBadge tier={row.tier} /></div>
                      </div>
                    </div>
                    {Object.values(row.findingCounts ?? {}).reduce((s, n) => s + n, 0) > 0 && (
                      <FindingDots counts={row.findingCounts} />
                    )}
                  </div>
                  <div className="grid grid-cols-3 gap-x-3 gap-y-2 text-xs">
                    <div>
                      <span className="text-gray-400 uppercase tracking-wider text-xs">Leverage</span>
                      <p className="text-gray-700 font-mono mt-0.5">{row.maxLeverage ? `1:${row.maxLeverage}` : "—"}</p>
                    </div>
                    <div>
                      <span className="text-gray-400 uppercase tracking-wider text-xs">Min Deposit</span>
                      <p className="text-gray-700 font-mono mt-0.5">
                        {row.minDepositUsd != null ? (row.minDepositUsd === 0 ? "No min" : `$${row.minDepositUsd}`) : "—"}
                      </p>
                    </div>
                    <div>
                      <span className="text-gray-400 uppercase tracking-wider text-xs">Spread</span>
                      <p className="text-gray-700 font-mono mt-0.5">{row.spreadFrom ?? "—"}</p>
                    </div>
                    <div>
                      <span className="text-gray-400 uppercase tracking-wider text-xs">Instruments</span>
                      <p className="text-gray-700 font-mono mt-0.5">{row.instrumentsCount?.toLocaleString() ?? "—"}</p>
                    </div>
                    <div>
                      <span className="text-gray-400 uppercase tracking-wider text-xs">Promos</span>
                      <p className="text-gray-700 mt-0.5">{row.promoCount > 0 ? row.promoCount : "—"}</p>
                    </div>
                    <div>
                      <span className="text-gray-400 uppercase tracking-wider text-xs">Trustpilot</span>
                      <div className="mt-0.5">
                        <TrustpilotCell score={row.trustpilotScore} />
                      </div>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
