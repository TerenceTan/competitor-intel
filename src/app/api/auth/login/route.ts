import { NextRequest, NextResponse } from "next/server";
import { createHash } from "crypto";

function deriveToken(password: string): string {
  return createHash("sha256").update(password).digest("hex");
}

export async function POST(request: NextRequest) {
  const { password } = await request.json();

  const expectedPassword = process.env.DASHBOARD_PASSWORD;
  if (!expectedPassword) {
    return NextResponse.json({ error: "Server misconfiguration" }, { status: 503 });
  }

  if (password !== expectedPassword) {
    return NextResponse.json({ error: "Invalid password" }, { status: 401 });
  }

  const tokenValue = deriveToken(expectedPassword);

  const response = NextResponse.json({ success: true });
  response.cookies.set("auth_token", tokenValue, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 24 * 7, // 7 days
    path: "/",
    sameSite: "lax",
  });

  return response;
}
