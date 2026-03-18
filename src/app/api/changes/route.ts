import { NextResponse } from "next/server";
import { db } from "@/db";
import { changeEvents, competitors } from "@/db/schema";
import { desc } from "drizzle-orm";

export async function GET() {
  const allCompetitors = await db.select().from(competitors);
  const competitorMap = Object.fromEntries(allCompetitors.map((c) => [c.id, c]));

  const changes = await db
    .select()
    .from(changeEvents)
    .orderBy(desc(changeEvents.detectedAt))
    .limit(500);

  const result = changes.map((c) => ({
    ...c,
    competitorName: competitorMap[c.competitorId]?.name ?? c.competitorId,
  }));

  return NextResponse.json(result);
}
