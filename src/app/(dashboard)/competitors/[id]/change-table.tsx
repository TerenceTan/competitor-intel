"use client";

import { timeAgo } from "@/lib/utils";

interface ChangeEvent {
  id: number;
  competitorId: string;
  domain: string;
  fieldName: string;
  oldValue: string | null;
  newValue: string | null;
  severity: string;
  detectedAt: string;
}

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

export function CompetitorChangeTable({
  changes,
}: {
  changes: ChangeEvent[];
}) {
  function exportCSV() {
    const headers = ["Date", "Domain", "Field", "Old Value", "New Value", "Severity"];
    const rows = changes.map((c) => [
      c.detectedAt,
      c.domain,
      c.fieldName,
      c.oldValue ?? "",
      c.newValue ?? "",
      c.severity,
    ]);
    const csv = [headers, ...rows]
      .map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "change-history.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  if (changes.length === 0) {
    return (
      <div
        className="rounded-xl border border-gray-200 p-8 text-center text-gray-500 bg-white"
      >
        No change events recorded yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <button
          onClick={exportCSV}
          className="px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 text-gray-500 hover:text-gray-700 hover:border-gray-400 transition-colors"
        >
          Export CSV
        </button>
      </div>
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
            {changes.map((event, idx) => (
              <tr
                key={event.id}
                className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${
                  idx === changes.length - 1 ? "border-b-0" : ""
                }`}
              >
                <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                  {timeAgo(event.detectedAt)}
                </td>
                <td className="px-4 py-3 text-gray-500 capitalize">
                  {event.domain}
                </td>
                <td className="px-4 py-3 text-gray-700 font-medium">
                  {event.fieldName}
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs max-w-[160px] truncate">
                  {event.oldValue ?? "—"}
                </td>
                <td className="px-4 py-3 text-gray-700 text-xs max-w-[160px] truncate">
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
    </div>
  );
}
