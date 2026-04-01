"use client";

import { useState } from "react";

export function CollapsibleText({
  text,
  lines = 3,
  className = "",
}: {
  text: string;
  lines?: number;
  className?: string;
}) {
  const [expanded, setExpanded] = useState(false);

  // Rough heuristic: if text is short enough, don't show toggle
  const isLong = text.length > lines * 80;

  return (
    <div className={className}>
      <p
        className={`text-base text-gray-700 leading-relaxed ${!expanded && isLong ? `line-clamp-${lines}` : ""}`}
        style={!expanded && isLong ? { WebkitLineClamp: lines, display: "-webkit-box", WebkitBoxOrient: "vertical", overflow: "hidden" } : undefined}
      >
        {text}
      </p>
      {isLong && (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="text-sm text-primary font-medium mt-2 hover:underline"
        >
          {expanded ? "Show less" : "Read more"}
        </button>
      )}
    </div>
  );
}
