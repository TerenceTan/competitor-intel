import { NextRequest, NextResponse } from "next/server";

function simpleHash(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(16);
}

export async function POST(request: NextRequest) {
  const { password } = await request.json();
  const expectedPassword = process.env.DASHBOARD_PASSWORD || "pepperstone2026";

  if (password !== expectedPassword) {
    return NextResponse.json({ error: "Invalid password" }, { status: 401 });
  }

  const tokenValue = simpleHash(expectedPassword);

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
