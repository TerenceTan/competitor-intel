# Competitor Analysis Dashboard — External API Guide

## Connection

**Base URL:** `https://<your-dashboard-domain>` (or `http://localhost:3000` for local dev)

**Authentication:** Bearer token via the `API_KEY` environment variable.

Every request must include:
```
Authorization: Bearer <your-api-key>
```

The API key is set in the server's `.env.local` file as `API_KEY`. If `API_KEY` is not set, all `/api/v1/` requests return 401.

**Example (curl):**
```bash
curl -H "Authorization: Bearer your-api-key-here" \
  https://your-dashboard.com/api/v1/promotions
```

---

## Endpoints

### GET /api/v1/promotions

Returns competitor promotional offers scraped from official broker pages and aggregator sites (BrokersOfForex, BestForexBonus).

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `competitor` | string | all | Filter by competitor ID (e.g. `icmarkets`, `exness`, `xm`, `vantage`, `fbs`, `hfm`, `pepperstone`) |
| `market` | string | all | Filter by market code (e.g. `global`, `sg`, `th`, `vn`, `au`) |
| `active` | string | `"false"` | If `"true"`, only return promos with status/active marked as active |
| `limit` | number | 1 | Max snapshots per competitor (1 = latest only, max 50) |

**Response format:**
```json
{
  "data": [
    {
      "competitorId": "exness",
      "competitorName": "Exness",
      "market": "global",
      "snapshotDate": "2026-04-03",
      "name": "No Deposit Bonus",
      "type": "deposit_bonus",
      "value": "$30",
      "markets": ["th", "my", "id"],
      "endDate": "2026-04-30",
      "status": "active"
    }
  ],
  "meta": {
    "total": 12,
    "competitors": 5,
    "generatedAt": "2026-04-14T10:00:00.000Z"
  }
}
```

Each object in `data` is a single promotion. The fields within each promotion vary by source but commonly include: `name`, `type` (deposit_bonus, cashback, competition, referral, spread_discount, ib), `value`, `markets` (array of market codes), `endDate`, `status`, `source`, `source_url`.

**Example requests:**
```bash
# All latest promotions across all competitors
GET /api/v1/promotions

# Only Exness promotions
GET /api/v1/promotions?competitor=exness

# Only active promos in Thailand market
GET /api/v1/promotions?market=th&active=true

# Last 5 snapshots per competitor (historical)
GET /api/v1/promotions?limit=5
```

---

### GET /api/v1/trends

Returns aggregated market intelligence — promo activity, spread direction, reputation moves, and the latest AI morning brief summary. **No competitor names are exposed** — safe for external consumption.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | number | 7 | Lookback window in days (1–90) |
| `market` | string | all | Filter by market code (e.g. `th`, `sg`, `global`) |

**Response format:**
```json
{
  "period": "2026-04-07 to 2026-04-14",
  "days": 7,
  "promos": {
    "total": 12,
    "active": 8,
    "by_market": { "th": 3, "global": 5, "sg": 2, "vn": 2 },
    "by_type": { "deposit_bonus": 5, "cashback": 3, "competition": 2, "referral": 2 },
    "avg_bonus_value": "$50",
    "trend": "up",
    "vs_previous_period": { "current": 12, "previous": 9 }
  },
  "spreads": {
    "direction": "tightening",
    "avg_spread_pips": 0.85,
    "change_pct": -2.1,
    "avg_min_deposit": 45,
    "brokers_reporting": 8
  },
  "reputation": {
    "avg_trustpilot": 4.12,
    "trustpilot_change": 0.05,
    "snapshots_in_period": 10
  },
  "changes": {
    "high_severity": 3,
    "total": 18
  },
  "summary": "3 brokers launched deposit bonuses in Thailand this week...",
  "summary_generated_at": "2026-04-14T08:00:00.000Z",
  "meta": {
    "market_filter": "all",
    "generated_at": "2026-04-14T10:00:00.000Z"
  }
}
```

**Key fields:**
- `promos.trend`: `"up"`, `"down"`, or `"flat"` vs previous period
- `spreads.direction`: `"tightening"`, `"widening"`, `"stable"`, or `"insufficient_data"`
- `summary`: The latest AI-generated morning brief (natural language overview)
- All data excludes Pepperstone (self-benchmark) unless explicitly requested

**Example requests:**
```bash
# Last 7 days, all markets
GET /api/v1/trends

# Last 30 days, Thailand only
GET /api/v1/trends?days=30&market=th

# Last 14 days, global market
GET /api/v1/trends?days=14&market=global
```

---

## Competitor IDs

These are the valid `competitor` filter values:

| ID | Name | Tier |
|----|------|------|
| `ic-markets` | IC Markets | 1 |
| `exness` | Exness | 1 |
| `vantage` | Vantage Markets | 1 |
| `xm` | XM Group | 1 |
| `hfm` | HFM | 1 |
| `fbs` | FBS | 2 |
| `iux` | IUX | 2 |
| `fxpro` | FxPro | 2 |
| `mitrade` | Mitrade | 2 |
| `tmgm` | TMGM | 2 |
| `pepperstone` | Pepperstone (self) | 1 |

By default, Pepperstone (self-benchmark) is excluded from results unless you explicitly pass `?competitor=pepperstone`.

---

## Market Codes

| Code | Market |
|------|--------|
| `global` | Global (default) |
| `sg` | Singapore |
| `hk` | Hong Kong |
| `th` | Thailand |
| `vn` | Vietnam |
| `id` | Indonesia |
| `my` | Malaysia |
| `jp` | Japan |
| `mn` | Mongolia |
| `in` | India |
| `ph` | Philippines |
| `tw` | Taiwan |
| `cn` | China |

---

## Error Responses

| Status | Meaning |
|--------|---------|
| 401 | Missing or invalid `Authorization: Bearer <key>` header |
| 503 | Server misconfiguration (API_KEY not set) |

---

## Setup Checklist

1. Add `API_KEY=<generate-a-secret>` to `.env.local` on the server
2. Restart the Next.js app so the env var is picked up
3. Share the API key with the connecting tool/agent
4. The connecting tool sends `Authorization: Bearer <key>` on every request

To generate a secure key:
```bash
openssl rand -base64 32
```

---

## Data Freshness

Promo data is scraped every ~48 hours. The `snapshotDate` field in each response tells you when the data was last collected. The `meta.generatedAt` field is the timestamp of the API response itself.

More endpoints (pricing, reputation, social, changes) can be added to `/api/v1/` following the same authentication pattern.
