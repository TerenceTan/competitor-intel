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

export async function middleware(request: NextRequest) {
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
  const expectedToken = await deriveToken(password);

  if (authToken !== expectedToken) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
