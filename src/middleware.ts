import { NextRequest, NextResponse } from "next/server";

/**
 * Derive a session token from the dashboard password using SHA-256.
 * Uses Web Crypto API (available in the Edge runtime).
 */
async function deriveToken(password: string): Promise<string> {
  const encoded = new TextEncoder().encode(password);
  const hashBuffer = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** Constant-time string comparison to prevent timing attacks. */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  const encoder = new TextEncoder();
  const bufA = encoder.encode(a);
  const bufB = encoder.encode(b);
  let result = 0;
  for (let i = 0; i < bufA.length; i++) {
    result |= bufA[i] ^ bufB[i];
  }
  return result === 0;
}

/**
 * Fixed-window rate limiter for /api/v1/* requests.
 *
 * Keyed on the caller's Bearer token (or falls back to the client IP) so a
 * leaked key can't be used to flood the scrapers. In-memory and per-edge
 * instance — good enough for a single-host deployment behind PM2; if we
 * ever scale horizontally we'll need to move this into Redis or similar.
 */
const RATE_LIMIT_WINDOW_MS = 60_000; // 1 minute
const RATE_LIMIT_MAX = 60; // 60 requests per window per key
const rateLimitBuckets = new Map<string, { count: number; resetAt: number }>();

function rateLimitCheck(key: string): { ok: boolean; remaining: number; resetAt: number } {
  const now = Date.now();
  const bucket = rateLimitBuckets.get(key);
  if (!bucket || bucket.resetAt <= now) {
    const resetAt = now + RATE_LIMIT_WINDOW_MS;
    rateLimitBuckets.set(key, { count: 1, resetAt });
    // Opportunistic cleanup so the Map doesn't grow unbounded.
    if (rateLimitBuckets.size > 1000) {
      for (const [k, v] of rateLimitBuckets) {
        if (v.resetAt <= now) rateLimitBuckets.delete(k);
      }
    }
    return { ok: true, remaining: RATE_LIMIT_MAX - 1, resetAt };
  }
  bucket.count += 1;
  return {
    ok: bucket.count <= RATE_LIMIT_MAX,
    remaining: Math.max(0, RATE_LIMIT_MAX - bucket.count),
    resetAt: bucket.resetAt,
  };
}

function getClientKey(request: NextRequest): string {
  // Prefer Bearer token (identifies the caller regardless of proxy IP).
  const authHeader = request.headers.get("authorization") ?? "";
  const match = authHeader.match(/^Bearer\s+(.+)$/i);
  if (match) return `k:${match[1].slice(0, 16)}`; // prefix keeps map small
  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0].trim() ||
    request.headers.get("x-real-ip") ||
    "unknown";
  return `ip:${ip}`;
}

/**
 * Validate Bearer API key for /api/v1/ routes.
 * Uses constant-time comparison to prevent timing attacks.
 */
function validateApiKey(request: NextRequest): boolean {
  const apiKey = process.env.API_KEY;
  if (!apiKey) return false;

  const authHeader = request.headers.get("authorization") ?? "";
  const match = authHeader.match(/^Bearer\s+(.+)$/i);
  if (!match) return false;

  return timingSafeEqual(match[1], apiKey);
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow login page and auth API routes
  if (pathname === "/login" || pathname.startsWith("/api/auth/")) {
    return NextResponse.next();
  }

  // Allow /api/v1/ routes with valid API key (for external integrations),
  // gated by a per-caller rate limit to make key leaks or buggy clients
  // harder to turn into a denial-of-service against our scraper DB.
  if (pathname.startsWith("/api/v1/")) {
    if (!validateApiKey(request)) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    const { ok, remaining, resetAt } = rateLimitCheck(getClientKey(request));
    if (!ok) {
      const retryAfter = Math.max(1, Math.ceil((resetAt - Date.now()) / 1000));
      return NextResponse.json(
        { error: "Rate limit exceeded" },
        {
          status: 429,
          headers: {
            "Retry-After": String(retryAfter),
            "X-RateLimit-Limit": String(RATE_LIMIT_MAX),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": String(Math.ceil(resetAt / 1000)),
          },
        }
      );
    }
    const res = NextResponse.next();
    res.headers.set("X-RateLimit-Limit", String(RATE_LIMIT_MAX));
    res.headers.set("X-RateLimit-Remaining", String(remaining));
    res.headers.set("X-RateLimit-Reset", String(Math.ceil(resetAt / 1000)));
    return res;
  }

  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) {
    // Refuse to serve the app rather than fall back to a known default
    return new NextResponse("Server misconfiguration: DASHBOARD_PASSWORD is not set.", {
      status: 503,
    });
  }

  const authToken = request.cookies.get("auth_token")?.value;
  const expectedToken = await deriveToken(password);

  if (!authToken || !timingSafeEqual(authToken, expectedToken)) {
    // Return 401 JSON for API routes so programmatic clients get a clear signal
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
