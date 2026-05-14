import { db } from "@/db";
import { competitors, competitorMarkets } from "@/db/schema";
import { eq } from "drizzle-orm";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Settings } from "lucide-react";
import { PerMarketStatusTable } from "@/components/admin/per-market-status-table";

// Force-dynamic — reads SQLite at request time. Inherits the (dashboard)
// route group's auth middleware (auth_token cookie required).
export const dynamic = "force-dynamic";

export default async function AdminCompetitorDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: rawId } = await params;
  // Validate id shape (mirrors validateId in actions.ts:40-44): lowercase
  // alphanumeric + hyphens, max 50 chars. Unknown shape → 404.
  if (!/^[a-z0-9-]+$/.test(rawId) || rawId.length > 50) notFound();

  const [competitor, existingRows] = await Promise.all([
    db
      .select()
      .from(competitors)
      .where(eq(competitors.id, rawId))
      .limit(1)
      .then((rows) => rows[0]),
    db
      .select({
        marketCode: competitorMarkets.marketCode,
        status: competitorMarkets.status,
        notes: competitorMarkets.notes,
      })
      .from(competitorMarkets)
      .where(eq(competitorMarkets.competitorId, rawId)),
  ]);

  if (!competitor) notFound();

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <Link
          href="/admin"
          className="inline-flex items-center gap-1 text-gray-500 hover:text-primary transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Admin
        </Link>
        <span className="text-gray-300">/</span>
        <span className="text-gray-700 font-medium">Competitors</span>
        <span className="text-gray-300">/</span>
        <span className="text-gray-700 font-medium">{competitor.name}</span>
      </div>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Settings className="w-5 h-5 text-gray-400" />
          {competitor.name}
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          <span className="font-mono">{competitor.id}</span>
          <span className="mx-2 text-gray-300">·</span>
          <a
            href={
              competitor.website.startsWith("http")
                ? competitor.website
                : `https://${competitor.website}`
            }
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            {competitor.website}
          </a>
          <span className="mx-2 text-gray-300">·</span>
          <span>Tier {competitor.tier}</span>
        </p>
      </div>

      {/* Per-market curation */}
      <section>
        <h2 className="text-base font-semibold text-gray-900 mb-2">
          Per-market curation
        </h2>
        <p className="text-sm text-gray-500 mb-3">
          Set this broker&apos;s status per APAC v1 market.{" "}
          <strong>active</strong> = show on the per-market dashboard.{" "}
          <strong>planned</strong> / <strong>withdrawn</strong> /{" "}
          <strong>emerging</strong> = hide from the main grid (still auditable
          via change_events). <strong>Not curated</strong> = no row in the
          table; defaults to Phase 2 &quot;show all&quot; if no other competitor
          is curated for this market.
        </p>
        <PerMarketStatusTable
          competitorId={competitor.id}
          existingRows={existingRows}
        />
      </section>
    </div>
  );
}
