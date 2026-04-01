"use client";

const columns: { key: string; label: string; headerBg: string; headerText: string; dotBg: string }[] = [
  { key: "immediate", label: "Immediate", headerBg: "bg-red-50", headerText: "text-red-700", dotBg: "bg-red-500" },
  { key: "this_week", label: "This Week", headerBg: "bg-orange-50", headerText: "text-orange-700", dotBg: "bg-orange-400" },
  { key: "this_month", label: "This Month", headerBg: "bg-blue-50", headerText: "text-blue-700", dotBg: "bg-blue-400" },
];

export function ActionsKanban({
  actions,
}: {
  actions: Array<{ action: string; urgency: string }>;
}) {
  const grouped: Record<string, Array<{ action: string; urgency: string }>> = {};
  for (const col of columns) grouped[col.key] = [];
  for (const a of actions) {
    const key = a.urgency?.toLowerCase() ?? "this_month";
    if (grouped[key]) grouped[key].push(a);
    else grouped["this_month"].push(a);
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {columns.map((col) => {
        const items = grouped[col.key];
        return (
          <div key={col.key} className="rounded-lg border border-gray-200 overflow-hidden bg-white">
            <div className={`flex items-center gap-2 px-3 py-2 ${col.headerBg}`}>
              <span className={`w-2 h-2 rounded-full ${col.dotBg}`} />
              <span className={`text-xs font-semibold uppercase tracking-wider ${col.headerText}`}>
                {col.label}
              </span>
              <span className={`ml-auto text-xs font-bold ${col.headerText}`}>{items.length}</span>
            </div>
            <div className="p-2.5 space-y-2 min-h-[60px]">
              {items.length === 0 ? (
                <div className="flex items-center justify-center h-[44px] border border-dashed border-gray-200 rounded-md">
                  <span className="text-xs text-gray-400">None</span>
                </div>
              ) : (
                items.map((a, i) => (
                  <div
                    key={i}
                    className="px-3 py-2.5 rounded-md bg-gray-50 border border-gray-100 hover:bg-gray-100 transition-colors"
                  >
                    <p className="text-sm text-gray-700 leading-relaxed">{a.action}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
