import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";
import { createHash } from "crypto";

const SCRAPER_FILES: Record<string, string> = {
  "pricing-scraper": "pricing_scraper.py",
  "promo-scraper": "promo_scraper.py",
  "social-scraper": "social_scraper.py",
  "reputation-scraper": "reputation_scraper.py",
  "news-scraper": "news_scraper.py",
  "ai-analysis": "ai_analyzer.py",
  "all": "run_all.py",
};

// In-memory concurrency guard — only one scraper process at a time
let runningScraperName: string | null = null;

// Simple per-IP rate limiter: max 10 scraper starts per 15 minutes
const rateLimitMap = new Map<string, { count: number; resetAt: number }>();
const RATE_LIMIT_MAX = 10;
const RATE_LIMIT_WINDOW_MS = 15 * 60 * 1000;

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const entry = rateLimitMap.get(ip);
  if (!entry || now > entry.resetAt) {
    rateLimitMap.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return true;
  }
  if (entry.count >= RATE_LIMIT_MAX) return false;
  entry.count++;
  return true;
}

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

  const ip =
    req.headers.get("x-forwarded-for")?.split(",")[0].trim() ?? "unknown";
  if (!checkRateLimit(ip)) {
    return NextResponse.json(
      { error: "Too many requests — try again in 15 minutes" },
      { status: 429 }
    );
  }

  if (runningScraperName !== null) {
    return NextResponse.json(
      { error: `Scraper already running: ${runningScraperName}` },
      { status: 409 }
    );
  }

  const body = await req.json().catch(() => ({}));
  const scraper = typeof body?.scraper === "string" ? body.scraper : null;
  const filename = scraper ? SCRAPER_FILES[scraper] : undefined;

  if (!filename) {
    return NextResponse.json({ error: "Unknown scraper" }, { status: 400 });
  }

  const scriptPath = path.join(process.cwd(), "scrapers", filename);

  runningScraperName = scraper;
  const child = spawn("python3", [scriptPath], {
    detached: true,
    stdio: "ignore",
    cwd: process.cwd(),
  });
  child.unref();
  child.on("exit", () => {
    runningScraperName = null;
  });

  return NextResponse.json({ started: true, scraper, filename });
}
