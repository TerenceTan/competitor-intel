"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { TimeAgo } from "@/components/ui/time-ago";
import { cn } from "@/lib/utils";

interface ScraperRun {
  scraperName: string;
  status: string;
  startedAt: string;
  recordsProcessed: number | null;
}

interface Scraper {
  name: string;
  dbName: string;
  label: string;
  domain: string;
}

interface Props {
  scrapers: readonly Scraper[];
  latestRunMap: Record<string, ScraperRun>;
}

export function ScraperTable({ scrapers, latestRunMap }: Props) {
  const router = useRouter();
  const [runningMap, setRunningMap] = useState<Record<string, boolean>>({});

  async function handleRun(scraperName: string) {
    setRunningMap((prev) => ({ ...prev, [scraperName]: true }));
    try {
      await fetch("/api/admin/run-scraper", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scraper: scraperName }),
      });
      // Refresh server data after a short delay to show updated status
      setTimeout(() => {
        router.refresh();
        setRunningMap((prev) => ({ ...prev, [scraperName]: false }));
      }, 2000);
    } catch {
      setRunningMap((prev) => ({ ...prev, [scraperName]: false }));
    }
  }

  return (
    <Card className="border-gray-200 overflow-hidden bg-white">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <span className="text-gray-700 font-medium text-sm">Scraper Status</span>
        <button
          onClick={() => handleRun("all")}
          disabled={runningMap["all"]}
          className={cn(
            "px-4 py-1.5 text-xs rounded-lg border transition-colors disabled:cursor-not-allowed font-medium",
            runningMap["all"]
              ? "bg-gray-100 text-gray-400 border-gray-200"
              : "bg-primary text-white border-primary hover:bg-primary/90 active:bg-primary/80"
          )}
        >
          {runningMap["all"] ? <><Loader2 className="w-3 h-3 animate-spin inline mr-1" />Running all…</> : "Run All Scrapers"}
        </button>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50/80">
            <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
              Scraper
            </th>
            <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
              Domain
            </th>
            <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
              Last Run
            </th>
            <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
              Status
            </th>
            <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
              Records
            </th>
            <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
              Action
            </th>
          </tr>
        </thead>
        <tbody>
          {scrapers.map((scraper, idx) => {
            const run = latestRunMap[scraper.dbName];
            const status = run?.status ?? "never_run";
            const isRunning = runningMap[scraper.name];
            const statusColor =
              status === "success"
                ? "bg-green-50 text-green-700 border-green-200"
                : status === "running"
                ? "bg-blue-50 text-blue-700 border-blue-200"
                : status === "error"
                ? "bg-red-50 text-red-700 border-red-200"
                : "bg-gray-100 text-gray-500 border-gray-200";

            return (
              <tr
                key={scraper.name}
                className={`border-b border-gray-100 hover:bg-primary/[0.03] transition-colors ${
                  idx === scrapers.length - 1 ? "border-b-0" : ""
                }`}
              >
                <td className="px-4 py-3 text-gray-700 font-medium">
                  {scraper.label}
                </td>
                <td className="px-4 py-3 text-gray-500 capitalize">
                  {scraper.domain}
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {run ? <TimeAgo dateStr={run.startedAt} /> : "Never"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${statusColor}`}
                  >
                    {status === "never_run" ? "Never run" : status}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {run?.recordsProcessed ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleRun(scraper.name)}
                    disabled={isRunning}
                    className={cn(
                      "px-3 py-1 text-xs rounded-lg border transition-colors disabled:cursor-not-allowed",
                      isRunning
                        ? "bg-gray-100 text-gray-400 border-gray-200"
                        : "bg-primary text-white border-primary hover:bg-primary/90 active:bg-primary/80"
                    )}
                  >
                    {isRunning ? <><Loader2 className="w-3 h-3 animate-spin inline mr-1" />Running…</> : "Run"}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
