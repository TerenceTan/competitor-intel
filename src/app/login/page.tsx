"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });

      if (res.ok) {
        router.push("/");
        router.refresh();
      } else {
        setError("Incorrect password. Please try again.");
      }
    } catch {
      setError("An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="w-full max-w-md px-8">
        {/* Logo / Branding */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-3 mb-4">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center font-bold text-white text-lg"
              style={{ backgroundColor: "#0064FA" }}
            >
              P
            </div>
            <span className="text-gray-900 text-2xl font-semibold tracking-tight">
              Pepperstone
            </span>
          </div>
          <h1 className="text-gray-900 text-xl font-medium mt-2">
            Competitor Intelligence Dashboard
          </h1>
          <p className="text-gray-500 text-sm mt-1">APAC Marketing Team</p>
        </div>

        {/* Login Card */}
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-8">
          <h2 className="text-gray-900 text-lg font-semibold mb-6">
            Sign in to continue
          </h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-gray-500 mb-2"
              >
                Dashboard Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                className="w-full px-4 py-3 rounded-lg text-gray-900 placeholder-gray-400 text-sm outline-none transition-colors border border-gray-200 bg-white focus:border-blue-500"
                onFocus={(e) => {
                  e.target.style.borderColor = "#0064FA";
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = "#e5e7eb";
                }}
                required
                autoFocus
              />
            </div>

            {error && (
              <div className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg px-4 py-3">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !password}
              className="w-full py-3 rounded-lg font-semibold text-sm text-white transition-opacity disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-700"
              style={{ backgroundColor: "#0064FA" }}
            >
              {loading ? "Authenticating..." : "Enter Dashboard"}
            </button>
          </form>
        </div>

        <p className="text-center text-gray-400 text-xs mt-6">
          Internal tool — authorized personnel only
        </p>
      </div>
    </div>
  );
}
