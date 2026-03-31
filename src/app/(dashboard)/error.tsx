"use client";

import { useEffect } from "react";
import { EmptyState } from "@/components/shared/empty-state";
import { AlertCircle } from "lucide-react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Dashboard error:", error);
  }, [error]);

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <EmptyState
        icon={AlertCircle}
        title="Something went wrong"
        description="An unexpected error occurred. Please try again."
        action={
          <button
            onClick={reset}
            className="mt-4 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary/90 active:bg-primary/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2"
          >
            Try again
          </button>
        }
      />
    </div>
  );
}
