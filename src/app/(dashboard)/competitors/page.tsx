"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { timeAgo, tierLabel } from "@/lib/utils";
import { ArrowUpDown } from "lucide-react";

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

function SortIcon({ col, sortKey }: { col: SortKey; sortKey: SortKey }) {
  return (
    <ArrowUpDown
      className={`w-3 h-3 inline ml-1 ${sortKey === col ? "text-blue-600" : "text-gray-400"}`}
    />
  );
}

function Th({
  children,
  col,
  sortKey,
  onSort,
}: {
  children: React.ReactNode;
  col: SortKey;
  sortKey: SortKey;
  onSort: (col: SortKey) => void;
}) {
  return (
    <th
      className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider cursor-pointer hover:text-gray-700 select-none whitespace-nowrap"
      onClick={() => onSort(col)}
    >
      {children}
      <SortIcon col={col} sortKey={sortKey} />
    </th>
  );
}

export default function CompetitorsPage() {
  const [data, setData] = useState<CompetitorRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>("tier");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  useEffect(() => {
    fetch("/api/competitors")
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

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

      <div
        className="rounded-xl border border-gray-200 overflow-x-auto bg-white"
      >
        {loading ? (
          <div className="p-12 text-center text-gray-500">Loading...</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <Th col="name" sortKey={sortKey} onSort={handleSort}>Broker</Th>
                <Th col="maxLeverage" sortKey={sortKey} onSort={handleSort}>Max Leverage</Th>
                <Th col="minDepositUsd" sortKey={sortKey} onSort={handleSort}>Min Deposit</Th>
                <Th col="promoCount" sortKey={sortKey} onSort={handleSort}>Active Promos</Th>
                <Th col="trustpilotScore" sortKey={sortKey} onSort={handleSort}>Trustpilot</Th>
                <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                  Latest AI Insight
                </th>
                <Th col="lastUpdated" sortKey={sortKey} onSort={handleSort}>Last Updated</Th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((row, idx) => (
                <tr
                  key={row.id}
                  className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${
                    idx === sorted.length - 1 ? "border-b-0" : ""
                  }`}
                >
                  <td className="px-4 py-4">
                    <Link
                      href={`/competitors/${row.id}`}
                      className="hover:underline"
                    >
                      <div className="font-semibold text-gray-900">{row.name}</div>
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
                      <span
                        className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white"
                        style={{ backgroundColor: "#0064FA" }}
                      >
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
        )}
      </div>
    </div>
  );
}
