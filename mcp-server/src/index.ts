#!/usr/bin/env node
/**
 * Competitor Intelligence MCP Server
 *
 * Exposes competitor promotions, pricing, and change data from the
 * dashboard's SQLite database as MCP tools.
 *
 * Transport: stdio (works with Claude Code, Claude Desktop, etc.)
 *
 * Usage:
 *   DB_PATH=/path/to/competitor-intel.db node dist/index.js
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import Database from "better-sqlite3";
import path from "path";

// ---------------------------------------------------------------------------
// Database
// ---------------------------------------------------------------------------
const DB_PATH =
  process.env.DB_PATH ||
  path.join(process.cwd(), "..", "data", "competitor-intel.db");

function getDb(): Database.Database {
  const db = new Database(DB_PATH, { readonly: true });
  db.pragma("journal_mode = WAL");
  return db;
}

// ---------------------------------------------------------------------------
// MCP Server
// ---------------------------------------------------------------------------
const server = new McpServer({
  name: "competitor-intel",
  version: "1.0.0",
});

// ---- Tool: get_promotions ------------------------------------------------
server.tool(
  "get_promotions",
  "Retrieve competitor promotions. Returns the latest scraped promotions for all or a specific competitor, optionally filtered by market.",
  {
    competitor_id: z
      .string()
      .optional()
      .describe("Filter by competitor ID (e.g. 'icmarkets'). Omit for all competitors."),
    market: z
      .string()
      .optional()
      .describe("Filter by market code (e.g. 'global', 'au', 'uk'). Omit for all markets."),
    active_only: z
      .boolean()
      .optional()
      .default(false)
      .describe("If true, only return promotions marked as active."),
  },
  async ({ competitor_id, market, active_only }) => {
    const db = getDb();
    try {
      // Build query for latest snapshot per competitor (+market)
      let query = `
        SELECT ps.*, c.name AS competitor_name, c.tier, c.website
        FROM promo_snapshots ps
        JOIN competitors c ON c.id = ps.competitor_id
        WHERE ps.id IN (
          SELECT MAX(id) FROM promo_snapshots
          WHERE 1=1
          ${competitor_id ? "AND competitor_id = @competitor_id" : ""}
          ${market ? "AND market_code = @market" : ""}
          GROUP BY competitor_id
        )
      `;
      if (!competitor_id) {
        query += " AND (c.is_self = 0 OR c.is_self IS NULL)";
      }
      query += " ORDER BY c.tier, c.name";

      const rows = db.prepare(query).all({
        competitor_id: competitor_id ?? null,
        market: market ?? null,
      }) as Array<Record<string, unknown>>;

      const results: Array<Record<string, unknown>> = [];
      for (const row of rows) {
        const promos = JSON.parse((row.promotions_json as string) || "[]") as Array<
          Record<string, unknown>
        >;
        const filtered = active_only
          ? promos.filter((p) => {
              const status = String(p.status ?? p.active ?? "").toLowerCase();
              return status === "active" || status === "true" || status === "1";
            })
          : promos;

        for (const promo of filtered) {
          results.push({
            competitor_id: row.competitor_id,
            competitor_name: row.competitor_name,
            tier: row.tier,
            website: row.website,
            market: row.market_code,
            snapshot_date: row.snapshot_date,
            ...promo,
          });
        }
      }

      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify({ total: results.length, promotions: results }, null, 2),
          },
        ],
      };
    } finally {
      db.close();
    }
  }
);

// ---- Tool: list_competitors -----------------------------------------------
server.tool(
  "list_competitors",
  "List all tracked competitors with their tier and website.",
  {},
  async () => {
    const db = getDb();
    try {
      const rows = db
        .prepare(
          "SELECT id, name, tier, website, is_self FROM competitors ORDER BY tier, name"
        )
        .all() as Array<Record<string, unknown>>;

      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify(rows, null, 2),
          },
        ],
      };
    } finally {
      db.close();
    }
  }
);

// ---- Tool: get_recent_changes ---------------------------------------------
server.tool(
  "get_recent_changes",
  "Get recent competitor changes (pricing, promos, features). Useful for spotting what competitors have changed recently.",
  {
    competitor_id: z.string().optional().describe("Filter by competitor ID. Omit for all."),
    domain: z
      .string()
      .optional()
      .describe("Filter by domain (e.g. 'pricing', 'promotions', 'reputation')."),
    days: z
      .number()
      .optional()
      .default(7)
      .describe("How many days back to look. Default: 7."),
    limit: z.number().optional().default(50).describe("Max results. Default: 50."),
  },
  async ({ competitor_id, domain, days, limit }) => {
    const db = getDb();
    try {
      const cutoff = new Date(Date.now() - days * 86400000).toISOString();
      let query = `
        SELECT ce.*, c.name AS competitor_name
        FROM change_events ce
        JOIN competitors c ON c.id = ce.competitor_id
        WHERE ce.detected_at >= @cutoff
      `;
      if (competitor_id) query += " AND ce.competitor_id = @competitor_id";
      if (domain) query += " AND ce.domain = @domain";
      query += " ORDER BY ce.detected_at DESC LIMIT @limit";

      const rows = db.prepare(query).all({
        cutoff,
        competitor_id: competitor_id ?? null,
        domain: domain ?? null,
        limit: Math.min(limit, 200),
      });

      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify({ total: (rows as unknown[]).length, changes: rows }, null, 2),
          },
        ],
      };
    } finally {
      db.close();
    }
  }
);

// ---- Tool: get_pricing_snapshot -------------------------------------------
server.tool(
  "get_pricing_snapshot",
  "Get the latest pricing data (leverage, spreads, min deposit, instruments) for a competitor.",
  {
    competitor_id: z.string().describe("The competitor ID (e.g. 'icmarkets')."),
  },
  async ({ competitor_id }) => {
    const db = getDb();
    try {
      const row = db
        .prepare(
          `SELECT ps.*, c.name AS competitor_name
           FROM pricing_snapshots ps
           JOIN competitors c ON c.id = ps.competitor_id
           WHERE ps.competitor_id = ?
           ORDER BY ps.id DESC LIMIT 1`
        )
        .get(competitor_id) as Record<string, unknown> | undefined;

      if (!row) {
        return {
          content: [{ type: "text" as const, text: `No pricing data found for '${competitor_id}'.` }],
        };
      }

      // Parse JSON fields for readability
      const parsed: Record<string, unknown> = { ...row };
      for (const key of [
        "leverage_json",
        "account_types_json",
        "funding_methods_json",
        "spread_json",
      ]) {
        if (typeof parsed[key] === "string") {
          try {
            parsed[key] = JSON.parse(parsed[key] as string);
          } catch {}
        }
      }

      return {
        content: [{ type: "text" as const, text: JSON.stringify(parsed, null, 2) }],
      };
    } finally {
      db.close();
    }
  }
);

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error(`Competitor Intel MCP server running (DB: ${DB_PATH})`);
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
