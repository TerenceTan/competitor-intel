import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";
import { createHash, timingSafeEqual } from "crypto";

// Mirror of scrapers/run_all.py SCRIPTS list — keep in sync.
const SCRAPER_FILES: Record<string, string> = {
  "pricing-scraper": "pricing_scraper.py",
  "account-types-scraper": "account_types_scraper.py",
  "promo-scraper": "promo_scraper.py",
  "social-scraper": "social_scraper.py",
  "apify-social": "apify_social.py",
  "reputation-scraper": "reputation_scraper.py",
  "wikifx-scraper": "wikifx_scraper.py",
  "news-scraper": "news_scraper.py",
  "ai-analysis": "ai_analyzer.py",
  "all": "run_all.py",
};

// Use venv Python (apify_client / dotenv etc. live there per Ubuntu PEP-668).
// Override via VENV_PYTHON env var if the venv isn't at .venv/.
const VENV_PYTHON = process.env.VENV_PYTHON || path.join(process.cwd(), ".venv", "bin", "python");

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
  if (!authToken) return false;
  const expected = deriveToken(password);
  if (authToken.length !== expected.length) return false;
  return timingSafeEqual(Buffer.from(authToken), Buffer.from(expected));
}

/** Resolve client IP — prefer x-real-ip (set by trusted proxies) over x-forwarded-for */
function getClientIp(request: NextRequest): string {
  return (
    request.headers.get("x-real-ip") ??
    request.headers.get("x-forwarded-for")?.split(",")[0].trim() ??
    "unknown"
  );
}

export async function POST(req: NextRequest) {
  if (!isAuthenticated(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const ip = getClientIp(req);
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

  // Path traversal guard: resolved path must stay within scrapers directory
  const scrapersDir = path.resolve(path.join(process.cwd(), "scrapers"));
  const scriptPath = path.resolve(path.join(scrapersDir, filename));
  if (!scriptPath.startsWith(scrapersDir + path.sep)) {
    return NextResponse.json({ error: "Invalid scraper path" }, { status: 400 });
  }

  // Route through run_all.py for INFRA-02 timeout + INFRA-04 HC.io ping
  // coverage (matches the cron pattern). Direct script invocation would
  // bypass both. "all" is the orchestrator itself — invoke directly.
  const runAllPath = path.resolve(path.join(scrapersDir, "run_all.py"));
  const args = filename === "run_all.py" ? [runAllPath] : [runAllPath, filename];

  runningScraperName = scraper;
  const child = spawn(VENV_PYTHON, args, {
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
