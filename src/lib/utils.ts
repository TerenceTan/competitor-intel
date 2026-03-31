import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function timeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return "Unknown";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 30) return `${diffDays}d ago`;
  const diffMonths = Math.floor(diffDays / 30);
  if (diffMonths < 12) return `${diffMonths}mo ago`;
  return `${Math.floor(diffMonths / 12)}y ago`;
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Singapore",
  });
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleString("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Singapore",
  }) + " SGT";
}

/**
 * Parse leverage JSON (stored as string-object, string-array, or number)
 * and return a display string like "1:1000" or "Unlimited".
 */
export function extractMaxLeverage(leverageJson: string | null | undefined): string {
  if (!leverageJson) return "—";
  try {
    const parsed = JSON.parse(leverageJson);
    const nums: number[] = [];
    let hasUnlimited = false;
    const process = (v: unknown) => {
      const s = String(v).toLowerCase();
      if (s.includes("unlimited")) { hasUnlimited = true; return; }
      const part = s.includes(":") ? s.split(":").pop()! : s;
      const n = parseInt(part, 10);
      if (!isNaN(n)) nums.push(n);
    };
    if (typeof parsed === "number") return `1:${parsed.toLocaleString()}`;
    if (Array.isArray(parsed)) parsed.forEach(process);
    else if (typeof parsed === "object" && parsed !== null) Object.values(parsed).forEach(process);
    if (hasUnlimited && nums.length === 0) return "Unlimited";
    if (nums.length > 0) return hasUnlimited ? "Unlimited" : `1:${Math.max(...nums).toLocaleString()}`;
  } catch {}
  return "—";
}

export function severityToVariant(
  severity: string
): "destructive" | "secondary" | "outline" | "default" {
  switch (severity?.toLowerCase()) {
    case "critical":
      return "destructive";
    case "high":
      return "default";
    case "medium":
      return "secondary";
    case "low":
      return "outline";
    default:
      return "outline";
  }
}

/** Safely parse JSON with fallback. Logs malformed data in development. */
export function safeParseJson<T>(json: string | null | undefined, fallback: T, label?: string): T {
  if (!json) return fallback;
  try {
    return JSON.parse(json);
  } catch (e) {
    if (process.env.NODE_ENV === "development") {
      console.warn(`[safeParseJson] Malformed JSON${label ? ` in ${label}` : ""}:`, e);
    }
    return fallback;
  }
}

export function tierLabel(tier: number): string {
  switch (tier) {
    case 1:
      return "Tier 1";
    case 2:
      return "Tier 2";
    case 3:
      return "Tier 3";
    default:
      return `Tier ${tier}`;
  }
}
