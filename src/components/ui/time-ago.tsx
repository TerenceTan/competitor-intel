"use client";

import { useEffect, useState } from "react";

function computeTimeAgo(dateStr: string): string {
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

export function TimeAgo({ dateStr }: { dateStr: string }) {
  const [label, setLabel] = useState(() => computeTimeAgo(dateStr));

  useEffect(() => {
    const interval = setInterval(() => setLabel(computeTimeAgo(dateStr)), 60_000);
    return () => clearInterval(interval);
  }, [dateStr]);

  return <span>{label}</span>;
}
