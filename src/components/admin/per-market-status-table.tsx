"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import {
  PRIORITY_MARKETS,
  MARKET_NAMES,
  MARKET_FLAGS,
  type MarketCode,
} from "@/lib/markets";
import {
  upsertCompetitorMarket,
  clearCompetitorMarket,
} from "@/app/(dashboard)/admin/actions";

type CuratedStatus = "active" | "planned" | "withdrawn" | "emerging";
const STATUS_OPTIONS: CuratedStatus[] = [
  "active",
  "planned",
  "withdrawn",
  "emerging",
];

type RowState = {
  status: CuratedStatus | ""; // "" means "not curated" / cleared
  notes: string;
  dirty: boolean;
  saving: boolean;
};

interface ExistingRow {
  marketCode: string;
  status: string;
  notes: string | null;
}

interface Props {
  competitorId: string;
  existingRows: ExistingRow[];
}

export function PerMarketStatusTable({ competitorId, existingRows }: Props) {
  const router = useRouter();
  const [, startTransition] = useTransition();

  // Build initial state from existingRows keyed by marketCode. Every
  // PRIORITY_MARKETS entry gets a row even when competitor_markets has no
  // row for that (competitor, market) tuple — the "Not curated" sentinel.
  const initial: Record<MarketCode, RowState> = Object.fromEntries(
    PRIORITY_MARKETS.map((code) => {
      const existing = existingRows.find((r) => r.marketCode === code);
      return [
        code,
        {
          status: (existing?.status as CuratedStatus | undefined) ?? "",
          notes: existing?.notes ?? "",
          dirty: false,
          saving: false,
        } satisfies RowState,
      ];
    }),
  ) as Record<MarketCode, RowState>;

  const [rows, setRows] = useState<Record<MarketCode, RowState>>(initial);

  function update(code: MarketCode, patch: Partial<RowState>) {
    setRows((r) => ({ ...r, [code]: { ...r[code], ...patch, dirty: true } }));
  }

  async function save(code: MarketCode) {
    const row = rows[code];
    setRows((r) => ({ ...r, [code]: { ...r[code], saving: true } }));
    try {
      if (row.status === "") {
        // Empty status = clear (delete the row). Server-side no-op if no
        // prior row, so idempotent.
        const result = await clearCompetitorMarket(competitorId, code);
        if ("error" in result) {
          toast.error(result.error);
          return;
        }
        toast.success(`Cleared ${MARKET_NAMES[code]}`);
      } else {
        const result = await upsertCompetitorMarket(
          competitorId,
          code,
          row.status,
          row.notes.trim() || null,
        );
        if ("error" in result) {
          toast.error(result.error);
          return;
        }
        toast.success(`Saved ${MARKET_NAMES[code]}: ${row.status}`);
      }
      // Mark clean. revalidatePath() on the server invalidates the parent
      // page cache; router.refresh() pulls the new server-component data
      // into this client component without a full reload.
      setRows((r) => ({ ...r, [code]: { ...r[code], dirty: false } }));
      startTransition(() => router.refresh());
    } finally {
      setRows((r) => ({ ...r, [code]: { ...r[code], saving: false } }));
    }
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50/60 border-b border-gray-200">
          <tr>
            <th className="text-left px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider">
              Market
            </th>
            <th className="text-left px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider w-44">
              Status
            </th>
            <th className="text-left px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider">
              Notes
            </th>
            <th className="text-right px-4 py-2.5 text-gray-500 font-medium text-[11px] uppercase tracking-wider w-28">
              Action
            </th>
          </tr>
        </thead>
        <tbody>
          {PRIORITY_MARKETS.map((code) => {
            const row = rows[code];
            return (
              <tr
                key={code}
                className="border-b border-gray-100 last:border-b-0"
              >
                <td className="px-4 py-2.5">
                  <span className="inline-flex items-center gap-2">
                    <span className="text-base">{MARKET_FLAGS[code]}</span>
                    <span className="text-gray-900 font-medium">
                      {MARKET_NAMES[code]}
                    </span>
                    <span className="text-gray-400 text-[11px] uppercase">
                      {code}
                    </span>
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <select
                    value={row.status}
                    onChange={(e) =>
                      update(code, {
                        status: e.target.value as RowState["status"],
                      })
                    }
                    disabled={row.saving}
                    className="border border-gray-300 rounded-md px-2 py-1 text-sm bg-white"
                  >
                    <option value="">— Not curated —</option>
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-2.5">
                  <input
                    type="text"
                    value={row.notes}
                    onChange={(e) => update(code, { notes: e.target.value })}
                    disabled={row.saving}
                    placeholder="Marketing rationale (optional)"
                    maxLength={500}
                    className="w-full border border-gray-300 rounded-md px-2 py-1 text-sm bg-white"
                  />
                </td>
                <td className="px-4 py-2.5 text-right">
                  <button
                    type="button"
                    onClick={() => save(code)}
                    disabled={!row.dirty || row.saving}
                    className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                      row.dirty && !row.saving
                        ? "bg-primary text-white hover:bg-primary/90"
                        : "bg-gray-100 text-gray-400 cursor-not-allowed"
                    }`}
                  >
                    {row.saving ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : row.status === "" ? (
                      "Clear"
                    ) : (
                      "Save"
                    )}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
