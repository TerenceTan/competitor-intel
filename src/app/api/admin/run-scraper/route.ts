import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";
import { createHash } from "node:crypto";

const SCRAPER_FILES: Record<string, string> = {
  "pricing-scraper": "pricing_scraper.py",
  "promo-scraper": "promo_scraper.py",
  "social-scraper": "social_scraper.py",
  "reputation-scraper": "reputation_scraper.py",
  "news-scraper": "news_scraper.py",
  "ai-analysis": "ai_analyzer.py",
  "all": "run_all.py",
};

function deriveToken(password: string): string {
  return createHash("sha256").update(password).digest("hex");
}

function isAuthenticated(request: NextRequest): boolean {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) return false;
  const authToken = request.cookies.get("auth_token")?.value;
  return authToken === deriveToken(password);
}

export async function POST(req: NextRequest) {
  if (!isAuthenticated(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { scraper } = await req.json();
  const filename = SCRAPER_FILES[scraper];

  if (!filename) {
    return NextResponse.json({ error: "Unknown scraper" }, { status: 400 });
  }

  const scriptPath = path.join(process.cwd(), "scrapers", filename);

  const child = spawn("python3", [scriptPath], {
    detached: true,
    stdio: "ignore",
    cwd: process.cwd(),
  });
  child.unref();

  return NextResponse.json({ started: true, scraper, filename });
}
