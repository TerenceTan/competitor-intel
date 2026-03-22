import { NextRequest, NextResponse } from "next/server";
import { createHash } from "crypto";

function deriveToken(password: string): string {
  return createHash("sha256").update(password).digest("hex");
}

// Brute-force rate limiter: max 5 failed attempts per IP per 15 minutes
const failedAttempts = new Map<string, { count: number; resetAt: number }>();
const MAX_ATTEMPTS = 5;
const LOCKOUT_MS = 15 * 60 * 1000;

function checkLoginRateLimit(ip: string): { allowed: boolean; retryAfterSecs?: number } {
  const now = Date.now();
  const entry = failedAttempts.get(ip);
  if (!entry || now > entry.resetAt) return { allowed: true };
  if (entry.count >= MAX_ATTEMPTS) {
    return { allowed: false, retryAfterSecs: Math.ceil((entry.resetAt - now) / 1000) };
  }
  return { allowed: true };
}

function recordFailedAttempt(ip: string) {
  const now = Date.now();
  const entry = failedAttempts.get(ip);
  if (!entry || now > entry.resetAt) {
    failedAttempts.set(ip, { count: 1, resetAt: now + LOCKOUT_MS });
  } else {
    entry.count++;
  }
}

export async function POST(request: NextRequest) {
  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0].trim() ?? "unknown";

  const { allowed, retryAfterSecs } = checkLoginRateLimit(ip);
  if (!allowed) {
    return NextResponse.json(
      { error: `Too many failed attempts — try again in ${retryAfterSecs} seconds` },
      { status: 429 }
    );
  }

  const body = await request.json().catch(() => ({}));
  const password = typeof body?.password === "string" ? body.password : "";

  const expectedPassword = process.env.DASHBOARD_PASSWORD;
  if (!expectedPassword) {
    return NextResponse.json({ error: "Server misconfiguration" }, { status: 503 });
  }

  if (password !== expectedPassword) {
    recordFailedAttempt(ip);
    return NextResponse.json({ error: "Invalid password" }, { status: 401 });
  }

  // Successful login — clear any failed attempt record for this IP
  failedAttempts.delete(ip);

  const tokenValue = deriveToken(expectedPassword);

  const response = NextResponse.json({ success: true });
  response.cookies.set("auth_token", tokenValue, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 24 * 7, // 7 days
    path: "/",
    sameSite: "strict",
  });

  return response;
}
