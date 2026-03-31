import { Skeleton } from "@/components/ui/skeleton";

interface Column {
  label: string;
  className?: string;
}

interface DataTableProps {
  columns: Column[];
  children: React.ReactNode;
  loading?: boolean;
  loadingRows?: number;
}

export function DataTable({ columns, children, loading, loadingRows = 5 }: DataTableProps) {
  return (
    <div className="rounded-xl border border-gray-200 overflow-x-auto bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50/80">
            {columns.map((col, i) => (
              <th
                key={i}
                scope="col"
                className={`text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider ${col.className ?? ""}`}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: loadingRows }).map((_, rowIdx) => (
                <tr key={rowIdx} className="border-b border-gray-100">
                  {columns.map((_, colIdx) => (
                    <td key={colIdx} className="px-4 py-3">
                      <Skeleton className="h-4 w-full" />
                    </td>
                  ))}
                </tr>
              ))
            : children}
        </tbody>
      </table>
    </div>
  );
}
