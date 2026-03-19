import { NextResponse } from "next/server";
import { db } from "@/db";
import { changeEvents, competitors } from "@/db/schema";
import { desc, ne, or, eq, isNull } from "drizzle-orm";

export async function GET() {
  // Exclude Pepperstone (is_self=1) from the competitor name map and change feed
  const allCompetitors = await db
    .select()
    .from(competitors)
    .where(or(eq(competitors.isSelf, 0), isNull(competitors.isSelf)));
  const competitorMap = Object.fromEntries(allCompetitors.map((c) => [c.id, c]));

  const changes = await db
    .select()
    .from(changeEvents)
    .where(ne(changeEvents.competitorId, "pepperstone"))
    .orderBy(desc(changeEvents.detectedAt))
    .limit(500);

  const result = changes.map((c) => ({
    ...c,
    competitorName: competitorMap[c.competitorId]?.name ?? c.competitorId,
  }));

  return NextResponse.json(result);
}
