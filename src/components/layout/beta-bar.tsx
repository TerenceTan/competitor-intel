"use client";

import { useSyncExternalStore, useCallback } from "react";
import { FlaskConical, X } from "lucide-react";

const STORAGE_KEY = "beta-bar-dismissed";

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

function getSnapshot() {
  return localStorage.getItem(STORAGE_KEY) === "true";
}

function getServerSnapshot() {
  return false;
}

export function BetaBar() {
  const dismissed = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const handleDismiss = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, "true");
    window.dispatchEvent(new StorageEvent("storage", { key: STORAGE_KEY }));
  }, []);

  if (dismissed) return null;

  return (
    <div className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-50 border-b border-blue-200 text-blue-800 text-sm font-medium">
      <FlaskConical className="w-4 h-4 shrink-0 text-blue-500" />
      <span>
        <strong>Beta:</strong> This dashboard is under active development. We are actively expanding the scraping module — more data and coverage will be included over the next few days.
      </span>
      <button
        onClick={handleDismiss}
        className="ml-2 p-1 rounded-md text-blue-500 hover:text-blue-700 hover:bg-blue-100 transition-colors"
        aria-label="Dismiss notice"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
