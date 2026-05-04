# Testing Patterns

**Analysis Date:** 2026-05-04

## Test Framework

**Runner:**
- **Not configured** — No test runner (Jest, Vitest, etc.) is installed or configured.
- No `jest.config.*`, `vitest.config.*`, or test npm scripts in `package.json`

**Assertion Library:**
- Not applicable — No testing framework in use

**Run Commands:**
- **No test commands available** — `npm run lint` is the only quality-check script configured

**Coverage:**
- **Not enforced** — No coverage tooling configured or reported

## Test File Organization

**Status:** No test files found.

**Exploration result:**
- Searched for `*.test.*` and `*.spec.*` files in `/src/`, `/scrapers/`, and root
- No test files present
- No test directories (`__tests__/`, `tests/`, `.test/`, etc.)

## Why No Tests Are Present

The codebase appears to be validation-and-error-handling-first rather than test-driven. This is reflected in:

1. **Input validation functions:** Validation is explicit and centralized (e.g., `validateForm()`, `validateId()`, `isPublicHttpUrl()`) rather than scattered across tests
2. **Type safety:** TypeScript strict mode enforces type correctness at compile time
3. **Integration testing via scrapers:** Data integrity is verified by scraper runs and database snapshots (automated via cron and manual triggers)
4. **Rate limiting and security:** Tested manually and via load testing, not unit tests
5. **API endpoint contracts:** Defined in middleware and route handlers; tested implicitly by dashboard pages and external API consumers

## Manual Testing Approach

Based on code organization, testing is performed via:

### Scraper Integration Tests
- **Location:** `scrapers/` Python modules (e.g., `social_scraper.py`, `pricing_scraper.py`)
- **Pattern:** Scrapers are run individually or via `run_all.py` and log results to `scrapers.runs` database table
- **Validation:** `detect_change()` in Python compares new snapshots to previous ones and records changes in `change_events` table
- **Trigger:** Manual via `/api/admin/run-scraper` endpoint or scheduled cron jobs (see SCRAPER_SCHEDULE.md)

### Dashboard Page Testing
- **Pages are server-rendered:** Logic is tested implicitly when pages load
- **Data integrity:** Verified by visiting market-filtered views (e.g., `/?market=sg`) to confirm `parseMarketParam()` and SQL filters work
- **Example:** Commit fb78ebe added per-market views; testing was confirming that `?market=` param filtered promos, social, and App Store ratings correctly

### API Route Testing
- **Endpoint validation:** Tested by curl/Postman or via dashboard's auto-discovery form
- **Auth and rate limiting:** Tested by repeated requests and checking 401/429 responses
- **Example:** `/api/admin/run-scraper` tested by authenticated requests with valid/invalid scraper names, rate limit checks

### Database Integrity Testing
- **Migrations:** Run on startup (`migrate.ts` runs `migrate()`); schema changes applied automatically
- **Seed data:** Initial competitor list loaded from `config.py` (Python) and synced to database

## Testing Recommendations (If Adopting Tests)

If tests are added in the future, follow these patterns based on the codebase's structure:

### Unit Test Structure (If Jest/Vitest Added)
```typescript
// File: src/lib/utils.test.ts
import { extractMaxLeverage, severityToVariant, safeParseJson } from "./utils";

describe("extractMaxLeverage", () => {
  it("parses numeric leverage as 1:X", () => {
    expect(extractMaxLeverage("1000")).toBe("1:1000");
  });

  it("handles object with leverage keys", () => {
    expect(extractMaxLeverage('{"standard": 500, "pro": 1000}')).toBe("1:1000");
  });

  it("returns '—' for null/undefined", () => {
    expect(extractMaxLeverage(null)).toBe("—");
    expect(extractMaxLeverage(undefined)).toBe("—");
  });

  it("catches invalid JSON gracefully", () => {
    expect(extractMaxLeverage("{broken json}")).toBe("—");
  });
});

describe("safeParseJson", () => {
  it("parses valid JSON", () => {
    const result = safeParseJson('[1, 2, 3]', []);
    expect(result).toEqual([1, 2, 3]);
  });

  it("returns fallback for invalid JSON", () => {
    const result = safeParseJson('not json', [42], "test");
    expect(result).toEqual([42]);
  });

  it("logs warning in development for invalid JSON", () => {
    const spy = jest.spyOn(console, "warn");
    safeParseJson("{bad}", null, "testLabel");
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("[safeParseJson]"),
      expect.stringContaining("testLabel")
    );
  });
});
```

### Validation Function Tests
```typescript
// File: src/app/(dashboard)/admin/actions.test.ts
import { validateId, validateForm } from "./actions";

describe("validateId", () => {
  it("accepts valid lowercase alphanumeric IDs", () => {
    expect(validateId("ic-markets")).toBeNull();
    expect(validateId("exness123")).toBeNull();
  });

  it("rejects uppercase", () => {
    expect(validateId("IC-Markets")).not.toBeNull();
  });

  it("rejects special characters", () => {
    expect(validateId("ic@markets")).not.toBeNull();
  });

  it("rejects IDs > 50 chars", () => {
    expect(validateId("a".repeat(51))).not.toBeNull();
  });
});

describe("validateForm", () => {
  const validData = {
    id: "test-broker",
    name: "Test Broker",
    tier: 1,
    website: "example.com",
    isSelf: false,
    scraperConfig: {
      pricing_url: null,
      entities: [{ label: "Test" }],
      // ... other required fields
    },
  };

  it("accepts valid form data", () => {
    expect(validateForm(validData)).toBeNull();
  });

  it("rejects missing entities", () => {
    expect(validateForm({ ...validData, scraperConfig: { ...validData.scraperConfig, entities: [] } })).not.toBeNull();
  });
});
```

### Security & Rate Limiting Tests
```typescript
// File: src/middleware.test.ts
import { POST } from "@/app/api/auth/login/route";
import { NextRequest } from "next/server";

describe("checkLoginRateLimit", () => {
  beforeEach(() => {
    // Clear in-memory rate limit state
    jest.clearAllMocks();
  });

  it("allows requests under limit", () => {
    const { allowed } = checkLoginRateLimit("192.168.1.1");
    expect(allowed).toBe(true);
  });

  it("blocks after MAX_ATTEMPTS", () => {
    const ip = "192.168.1.2";
    for (let i = 0; i < 5; i++) {
      recordFailedAttempt(ip);
    }
    const { allowed, retryAfterSecs } = checkLoginRateLimit(ip);
    expect(allowed).toBe(false);
    expect(retryAfterSecs).toBeGreaterThan(0);
  });
});

describe("POST /api/auth/login", () => {
  it("returns 401 for invalid password", async () => {
    const request = new NextRequest("http://localhost/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ password: "wrong" }),
    });
    const response = await POST(request);
    expect(response.status).toBe(401);
  });

  it("sets httpOnly cookie on success", async () => {
    process.env.DASHBOARD_PASSWORD = "correct";
    const request = new NextRequest("http://localhost/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ password: "correct" }),
    });
    const response = await POST(request);
    expect(response.status).toBe(200);
    expect(response.cookies.get("auth_token")).toBeDefined();
    expect(response.cookies.get("auth_token")?.httpOnly).toBe(true);
  });

  it("rejects overly long passwords", async () => {
    // Should be capped at MAX_PASSWORD_LENGTH before comparison
    const longPassword = "a".repeat(501);
    // Test that it doesn't crash and compares safely
  });
});
```

### API Route Tests
```typescript
// File: src/app/api/v1/promotions.test.ts
import { GET } from "@/app/api/v1/promotions/route";
import { NextRequest } from "next/server";

describe("GET /api/v1/promotions", () => {
  it("returns empty data when no competitors exist", async () => {
    const request = new NextRequest("http://localhost/api/v1/promotions", {
      headers: { Authorization: "Bearer valid-key" },
    });
    const response = await GET(request);
    const json = await response.json();
    expect(json.data).toEqual([]);
  });

  it("filters by competitor ID", async () => {
    const request = new NextRequest(
      "http://localhost/api/v1/promotions?competitor=ic-markets",
      { headers: { Authorization: "Bearer valid-key" } }
    );
    const response = await GET(request);
    const json = await response.json();
    expect(json.data.every((p) => p.competitorId === "ic-markets")).toBe(true);
  });

  it("filters by market code", async () => {
    const request = new NextRequest(
      "http://localhost/api/v1/promotions?market=sg",
      { headers: { Authorization: "Bearer valid-key" } }
    );
    const response = await GET(request);
    const json = await response.json();
    expect(json.data.every((p) => p.market === "sg")).toBe(true);
  });

  it("respects limit parameter", async () => {
    const request = new NextRequest(
      "http://localhost/api/v1/promotions?limit=10",
      { headers: { Authorization: "Bearer valid-key" } }
    );
    const response = await GET(request);
    expect(response.status).toBe(200); // Limit is capped at 50 internally
  });
});
```

### Integration Test Pattern (E2E via Dashboard)
```bash
# Manual test: Verify per-market filtering works
# 1. Create a test scraper run
curl -X POST http://localhost/api/admin/run-scraper \
  -H "Cookie: auth_token=$AUTH_TOKEN" \
  -d '{"scraper": "promo-scraper"}' \

# 2. Wait for scraper to complete and DB to update
sleep 30

# 3. Visit dashboard with market filter
curl "http://localhost/?market=sg" -H "Cookie: auth_token=$AUTH_TOKEN"

# 4. Verify promo counts change when filtering by market
# (Inspect page HTML or inspect Network tab for API calls)
```

## Current State: Validation-First Design

Given the absence of tests, the codebase relies on:

1. **Type checking** — TypeScript strict mode catches most issues at compile time
2. **Input validation** — Explicit validation functions return error objects
3. **Database constraints** — Foreign keys and schema design enforce data integrity
4. **Middleware guards** — Rate limiting and auth checked before handlers execute
5. **Scraper idempotency** — Snapshots can be re-run safely; `detect_change()` compares against history
6. **Code review** — Manual testing before deploy (e.g., testing market param filters per commit fb78ebe)

This approach works well for a small team but should transition to automated tests if:
- Codebase grows beyond ~20 API routes
- Multiple developers work concurrently
- Regression risk increases with feature churn

---

*Testing analysis: 2026-05-04*
