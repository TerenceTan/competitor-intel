"use client";

import { Card } from "@/components/ui/card";
import { Newspaper, ChevronRight, TrendingUp, TrendingDown, AlertTriangle, Minus } from "lucide-react";

interface MorningBriefProps {
  summary: string;
  generatedAt: string;
}

/** Keywords that hint at the sentiment/type of each bullet */
const negativeKeywords = ["drop", "declin", "lost", "lower", "fell", "below", "risk", "threat", "gap", "concern", "weak", "departure", "depart"];
const positiveKeywords = ["rose", "increas", "gain", "improv", "strong", "above", "launch", "lead", "grow", "expand", "boost"];
const alertKeywords = ["critical", "urgent", "alert", "warning", "immediate", "signif"];

function classifyBullet(text: string): "positive" | "negative" | "alert" | "neutral" {
  const lower = text.toLowerCase();
  if (alertKeywords.some((k) => lower.includes(k))) return "alert";
  if (negativeKeywords.some((k) => lower.includes(k))) return "negative";
  if (positiveKeywords.some((k) => lower.includes(k))) return "positive";
  return "neutral";
}

const bulletConfig = {
  positive: {
    Icon: TrendingUp,
    iconColor: "text-emerald-500",
    dotColor: "bg-emerald-400",
    bgColor: "bg-emerald-50/50",
  },
  negative: {
    Icon: TrendingDown,
    iconColor: "text-red-500",
    dotColor: "bg-red-400",
    bgColor: "bg-red-50/50",
  },
  alert: {
    Icon: AlertTriangle,
    iconColor: "text-amber-500",
    dotColor: "bg-amber-400",
    bgColor: "bg-amber-50/50",
  },
  neutral: {
    Icon: Minus,
    iconColor: "text-blue-400",
    dotColor: "bg-blue-300",
    bgColor: "bg-blue-50/30",
  },
};

function splitIntoBullets(text: string): string[] {
  // Try splitting by explicit bullet/list markers: "• ", "- ", "1. ", "1) "
  const explicitBullets = text.split(/(?:^|\n)\s*(?:[-•●]\s+|\d+[.)]\s+)/);
  if (explicitBullets.filter((b) => b.trim()).length >= 3) {
    return explicitBullets.filter((b) => b.trim()).map((b) => b.trim());
  }

  // Replace common abbreviations with a placeholder so they don't create
  // false sentence breaks (e.g. "vs. XM" or "e.g. some example").
  const ABBR_PLACEHOLDER = "\x00";
  const abbreviated = text.replace(/\b(vs|e\.g|i\.e|etc|approx|incl|excl|no)\.\s/gi, (m) =>
    m.replace(". ", ABBR_PLACEHOLDER),
  );

  // Split by sentence boundaries: ". " followed by uppercase letter
  const sentences = abbreviated.split(/(?<=\.)\s+(?=[A-Z])/);
  if (sentences.length >= 2) {
    // Restore abbreviation dots and merge very short fragments
    const merged: string[] = [];
    for (const s of sentences) {
      const restored = s.replaceAll(ABBR_PLACEHOLDER, ". ").trim();
      if (!restored) continue;
      if (merged.length > 0 && merged[merged.length - 1].length < 60) {
        merged[merged.length - 1] += " " + restored;
      } else {
        merged.push(restored);
      }
    }
    return merged;
  }

  // Fallback: return as single item
  return [text.trim()];
}

export function MorningBrief({ summary, generatedAt }: MorningBriefProps) {
  const bullets = splitIntoBullets(summary);

  return (
    <Card className="border-gray-200 bg-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-5 py-3.5 border-b border-gray-100 bg-gray-50/50">
        <Newspaper className="w-4.5 h-4.5 text-primary" />
        <h2 className="text-sm font-semibold text-gray-900">Morning Brief</h2>
        <span className="text-xs text-gray-400 ml-auto">{formatRelativeTime(generatedAt)}</span>
      </div>

      {/* Bullet points */}
      <div className="p-4 space-y-2">
        {bullets.map((bullet, idx) => {
          const type = classifyBullet(bullet);
          const { Icon, iconColor, bgColor } = bulletConfig[type];
          return (
            <div
              key={idx}
              className={`flex items-start gap-3 rounded-lg px-3.5 py-2.5 ${bgColor}`}
            >
              <Icon className={`w-4 h-4 shrink-0 mt-0.5 ${iconColor}`} />
              <p className="text-sm text-gray-700 leading-relaxed">{bullet}</p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}
