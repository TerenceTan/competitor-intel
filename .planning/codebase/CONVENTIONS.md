# Coding Conventions

**Analysis Date:** 2026-05-04

## Naming Patterns

**Files:**
- React components (client): PascalCase with `.tsx` extension (e.g., `MarketSelector.tsx`, `TierBadge`)
- Server components: PascalCase with `.tsx` extension (e.g., `CompetitorsPage`, `KpiRow`)
- Utilities and helpers: camelCase with `.ts` extension (e.g., `utils.ts`, `markets.ts`, `constants.ts`)
- Database schema and queries: camelCase with `.ts` extension (e.g., `schema.ts`, `migrate.ts`, `seed.ts`)
- Server actions: `actions.ts` in feature directories
- API routes: lowercase-kebab-case directory structure (e.g., `/api/v1/promotions/route.ts`, `/api/auth/login/route.ts`)
- Scrapers (Python): snake_case (e.g., `social_scraper.py`, `pricing_scraper.py`)

**Functions:**
- TypeScript: camelCase (e.g., `extractMaxLeverage()`, `safeParseJson()`, `checkRateLimit()`)
- Helper functions with leading underscore for internal/private helpers: `_fetchViaScraperapi()`
- React component functions: PascalCase for exported components (e.g., `MarketSelector()`, `TierBadge()`)
- Callbacks and event handlers: `on` prefix (e.g., `onChange()`, `onSort()`)
- Boolean checkers: `is`/`check` prefix (e.g., `isPublicHttpUrl()`, `checkRateLimit()`, `checkLoginRateLimit()`)
- Validation functions: `validate` prefix (e.g., `validateId()`, `validateForm()`)
- Derivation/parsing functions: extract/derive/parse prefix (e.g., `extractMaxLeverage()`, `deriveToken()`, `safeParseJson()`)

**Variables:**
- Local variables: camelCase (e.g., `maxLeverage`, `minDepositUsd`, `competitorMap`)
- Constants: UPPER_SNAKE_CASE (e.g., `SCRAPER_NAME`, `RATE_LIMIT_MAX`, `MAX_ATTEMPTS`)
- Map/dictionary results: descriptive camelCase with `Map` or explicit type suffix (e.g., `competitorMap`, `reputationMap`, `pricingMap`)
- Boolean variables: `is`/`has` prefix (e.g., `isPending`, `hasUnlimited`, `isSelf`)
- Type-specific suffixes for clarity in parsed JSON: `Json` suffix (e.g., `leverageJson`, `promotionsJson`, `leverageConfidence`)
- Query parameter extractions: descriptive name with `Filter` suffix (e.g., `competitorFilter`, `marketFilter`, `activeOnly`)

**Types:**
- Exported interfaces: PascalCase (e.g., `CompetitorFormData`, `CompetitorRow`)
- String union types: lowercase (e.g., `type SortKey = keyof CompetitorRow`)
- Severity values: lowercase (e.g., `"critical" | "high" | "medium" | "low"`)
- Record/enum keys: match business domain (e.g., MARKET_NAMES uses lowercase market codes as keys)

## Code Style

**Formatting:**
- ESLint 9 with Next.js core web vitals and TypeScript configs
- Config: `eslint.config.mjs` (flat config format)
- No explicit Prettier config found — relies on ESLint default formatting
- Line length: practical limits observed in code (~80-100 chars for readability)
- Indentation: 2 spaces

**Linting:**
- Framework: ESLint 9
- Extends: `eslint-config-next/core-web-vitals` and `eslint-config-next/typescript`
- Entry point: `eslint.config.mjs`
- Run: `npm run lint` (no auto-fix script configured)
- Key ignores: `.next/`, `out/`, `build/`, `next-env.d.ts`

## Import Organization

**Order:**
1. External npm packages (e.g., `react`, `next/server`, `drizzle-orm`)
2. Type imports from external packages
3. Internal absolute imports using `@/` alias (e.g., `@/db`, `@/lib/utils`, `@/components`)
4. Relative imports (rare, mostly for sibling files)

**Path Aliases:**
- `@/*` maps to `./src/*` (configured in `tsconfig.json`)
- Consistently used throughout codebase for internal imports
- No nested aliases observed

**Examples:**
```typescript
// External packages
import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { eq, or, isNull, sql, and, desc, inArray } from "drizzle-orm";

// Internal utilities
import { safeParseJson, extractMaxLeverage } from "@/lib/utils";
import { SCRAPERS, STALE_MULTIPLIER } from "@/lib/constants";
import { parseMarketParam, MARKET_NAMES } from "@/lib/markets";

// Components
import { Card } from "@/components/ui/card";
import { KpiRow } from "@/components/charts/kpi-row";
```

## Error Handling

**HTTP API Routes (Next.js):**
- Return `NextResponse.json({ error: "message" }, { status: CODE })` for client errors
- Status codes: `400` (invalid input), `401` (unauthorized), `403` (forbidden), `409` (conflict), `429` (rate limit), `503` (server misconfiguration)
- Include descriptive error messages in response body (e.g., "Too many requests — try again in 15 minutes")
- Rate limit responses include headers: `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- Pattern: Check conditions, return error response early; no deep nesting

**Input Validation:**
- Server actions: explicit validation function (e.g., `validateId()`, `validateForm()`) returns `null` on success or error string on failure
- API query parameters: type coercion with defaults (e.g., `Math.min(Math.max(parseInt(...) || 1, 1), 50)`) to enforce bounds
- Request bodies: `.catch(() => ({}))` fallback for JSON parse errors; property type checks before use (e.g., `typeof body?.scraper === "string"`)
- Path traversal guard: verify resolved path stays within expected directory (e.g., `!scriptPath.startsWith(scrapersDir + path.sep)`)
- URL validation: `isPublicHttpUrl()` checks protocol (http/https), rejects localhost/metadata IPs, private ranges (10.x, 127.x, 169.254.x)

**Authentication & Security:**
- Timing-safe comparison: `timingSafeEqual()` from `crypto` module (Node.js) or custom implementation in `middleware.ts` (Edge runtime)
- Rate limiting: per-IP or per-Bearer-token in-memory Map with sliding window (configurable `RATE_LIMIT_WINDOW_MS`, `RATE_LIMIT_MAX`)
- Password length cap: `MAX_PASSWORD_LENGTH = 500` before hashing to prevent DoS
- Brute-force protection: failed login attempts tracked by IP, lockout after `MAX_ATTEMPTS` (5 for login, 10 for scraper runs)
- SSRF mitigation: reject URLs with private/loopback hostnames or IPs before issuing outbound requests
- Cookies: `httpOnly`, `secure` (in production), `sameSite: "strict"`

**Database Operations:**
- Use Drizzle ORM query builders to prevent SQL injection
- Batch queries with `Promise.all()` instead of sequential loops (e.g., 4 parallel queries instead of N*4)
- Fallback parsing: `safeParseJson(json, fallback, label?)` returns fallback if JSON is invalid; logs warning in development
- Null coalescing for optional fields: `field ?? null` or `field ?? "—"` for display

**Server Actions:**
- Return `{ error: string }` on validation failure or `{ success: true }` on success
- No exceptions thrown; validation errors returned as object properties
- Call `revalidatePath()` on success to invalidate cached pages

**Client-side Error Handling:**
- Components use conditional rendering for null/undefined fields
- Display "—" (em-dash) for missing/null values consistently
- Severity indicators (color-coded dots, badges) for status/health
- Fallback states for loading/skeleton states

## Logging

**Framework:** Native `console` methods (no dedicated logger)

**Patterns:**
- `console.warn()` in development for malformed data (e.g., `[safeParseJson] Malformed JSON in promotionsJson`)
- API routes log status/errors via `console.log()` or `print()` (for Python scrapers)
- Rate limit and auth failures log via response HTTP status (implicit, no explicit logging)
- Scraper runs logged to database via `log_scraper_run()`, `update_scraper_run()` Python functions
- Keywords in CLI output: `[module-name]` prefix for origin context (e.g., `[ScraperAPI]`, `[Thunderbit]`)

## Comments

**When to Comment:**
- **Security/validation logic:** Always document the threat model (e.g., "Path traversal guard", "Timing-safe comparison to prevent timing attacks", "SSRF guard")
- **Non-obvious algorithms:** Complex business logic or data transformations (e.g., leverage extraction, change detection heuristics)
- **Configuration & defaults:** Constants and their purpose (e.g., rate limit windows, cadence hours for stale data detection)
- **Workarounds:** Temporary fixes or known limitations (e.g., DNS rebinding not fully mitigated)
- **External dependencies:** Where external APIs/scrapers are used and why (e.g., Thunderbit for social extraction, YouTube API for subscriber counts)

**Avoid:**
- Obvious code (e.g., `// increment counter` for `count++`)
- Restating variable names

**JSDoc/TSDoc:**
- Used for complex functions: `/** Returns HTML string or None on failure. */`
- Used for security/validation: `/** Reject URLs that point at private/loopback/link-local hosts... */`
- Function signature comments: single-line JSDoc when it clarifies intent
- Type parameter documentation: when types are complex or domain-specific

**Example:**
```typescript
/**
 * Validate Bearer API key for /api/v1/ routes.
 * Uses constant-time comparison to prevent timing attacks.
 */
function validateApiKey(request: NextRequest): boolean {
  // ...
}

/**
 * Safely parse JSON with fallback. Logs malformed data in development.
 */
export function safeParseJson<T>(json: string | null | undefined, fallback: T, label?: string): T {
  // ...
}
```

## Function Design

**Size:** 
- Prefer functions under ~50 lines
- Longer functions acceptable for data fetching (e.g., page components with multiple `Promise.all()` queries)
- Break out validation/helper functions into separate named functions for clarity

**Parameters:**
- Destructure object parameters for readability (e.g., `{ searchParams }` instead of passing entire context)
- Use type aliases for complex parameter objects (e.g., `CompetitorFormData` interface)
- Optional parameters: use `?:` in types, not function overloads
- Maximum 3-4 parameters; beyond that, use object destructuring

**Return Values:**
- Functions return rich objects with semantic names (e.g., `{ allowed: boolean; retryAfterSecs?: number }`)
- Null-safe: functions return `null` or fallback for missing data rather than throwing
- Boolean checkers return `boolean` directly (e.g., `checkRateLimit()`)
- Server actions return `{ error: string }` or `{ success: true }`

**Examples:**
```typescript
function checkRateLimit(ip: string): boolean {
  // ...
  return entry.count <= RATE_LIMIT_MAX;
}

function checkLoginRateLimit(ip: string): { allowed: boolean; retryAfterSecs?: number } {
  // ...
  return { allowed: false, retryAfterSecs: Math.ceil((entry.resetAt - now) / 1000) };
}

export async function createCompetitor(data: CompetitorFormData) {
  const error = validateForm(data);
  if (error) return { error };
  // ...
  return { success: true };
}
```

## Module Design

**Exports:**
- Named exports for utilities (e.g., `export function cn(...) {}`, `export function timeAgo(...) {}`)
- Default export for page components (e.g., `export default function CompetitorsPage() {}`)
- Default export for API routes (e.g., `export async function GET() {}`)
- Type exports: `export interface CompetitorFormData {}`, `export type SortKey = ...`

**Barrel Files:**
- Not heavily used; most imports are direct from source files
- Component libraries (`/ui/`, `/charts/`) export individual components
- Type definitions co-located with feature files

**Internal/Private Convention:**
- Leading underscore for private helper functions (e.g., `_fetch_via_scraperapi()`, `_FB_SCHEMA`)
- No explicit "private" exports; convention is that underscore-prefixed items are internal

---

*Convention analysis: 2026-05-04*
