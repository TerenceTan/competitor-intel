import { NextRequest, NextResponse } from "next/server";
import { createHash } from "crypto";

// Use Node.js runtime so we can use crypto
export const runtime = "nodejs";

/**
 * Derive a session token from the dashboard password using SHA-256.
 * Not a replacement for proper auth (no salt, no bcrypt) — but orders
 * of magnitude better than the previous Java-style bitwise hash which
 * was trivially reversible.
 */
function deriveToken(password: string): string {
  return createHash("sha256").update(password).digest("hex");
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow login page and auth API routes
  if (pathname === "/login" || pathname.startsWith("/api/auth/")) {
    return NextResponse.next();
  }

  const password = process.env.DASHBOARD_PASSWORD;
  if (!password) {
    // Refuse to serve the app rather than fall back to a known default
    return new NextResponse("Server misconfiguration: DASHBOARD_PASSWORD is not set.", {
      status: 503,
    });
  }

  const authToken = request.cookies.get("auth_token")?.value;
  const expectedToken = deriveToken(password);

  if (authToken !== expectedToken) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
