"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useTransition } from "react";
import { Globe } from "lucide-react";
import { PRIORITY_MARKETS, MARKET_NAMES, MARKET_FLAGS } from "@/lib/markets";

// Renders a small select that reads/writes ?market=<code> on the current URL.
// Server components downstream read searchParams.market and filter their queries.
export function MarketSelector() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const current = searchParams.get("market") ?? "";

  function onChange(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set("market", value);
    } else {
      params.delete("market");
    }
    const query = params.toString();
    const url = query ? `${pathname}?${query}` : pathname;
    startTransition(() => router.push(url));
  }

  return (
    <label className="flex items-center gap-2 text-sm text-gray-600">
      <Globe className="w-4 h-4 text-gray-400" aria-hidden />
      <span className="sr-only md:not-sr-only md:text-xs md:uppercase md:tracking-wider md:text-gray-500">
        Market
      </span>
      <select
        value={current}
        onChange={(e) => onChange(e.target.value)}
        disabled={isPending}
        aria-label="Filter dashboard by market"
        className="rounded-md border border-gray-200 bg-white px-2 py-1 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50"
      >
        <option value="">All markets</option>
        {PRIORITY_MARKETS.map((code) => (
          <option key={code} value={code}>
            {MARKET_FLAGS[code]} {MARKET_NAMES[code]}
          </option>
        ))}
      </select>
    </label>
  );
}
