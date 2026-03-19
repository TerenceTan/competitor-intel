import { sqlite } from "./index";

export function runMigrations() {
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS competitors (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      tier INTEGER NOT NULL,
      website TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS markets (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      code TEXT NOT NULL UNIQUE,
      characteristics TEXT,
      platforms TEXT
    );

    CREATE TABLE IF NOT EXISTS pricing_snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      competitor_id TEXT NOT NULL REFERENCES competitors(id),
      snapshot_date TEXT NOT NULL,
      leverage_json TEXT,
      account_types_json TEXT,
      min_deposit_usd REAL,
      instruments_count INTEGER,
      funding_methods_json TEXT
    );

    CREATE TABLE IF NOT EXISTS promo_snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      competitor_id TEXT NOT NULL REFERENCES competitors(id),
      snapshot_date TEXT NOT NULL,
      promotions_json TEXT
    );

    CREATE TABLE IF NOT EXISTS social_snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      competitor_id TEXT NOT NULL REFERENCES competitors(id),
      platform TEXT NOT NULL,
      snapshot_date TEXT NOT NULL,
      followers INTEGER,
      posts_last_7d INTEGER,
      engagement_rate REAL,
      latest_post_url TEXT
    );

    CREATE TABLE IF NOT EXISTS reputation_snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      competitor_id TEXT NOT NULL REFERENCES competitors(id),
      snapshot_date TEXT NOT NULL,
      trustpilot_score REAL,
      trustpilot_count INTEGER,
      fpa_rating REAL,
      ios_rating REAL,
      android_rating REAL
    );

    CREATE TABLE IF NOT EXISTS news_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      competitor_id TEXT NOT NULL REFERENCES competitors(id),
      title TEXT NOT NULL,
      url TEXT,
      source TEXT,
      published_at TEXT,
      sentiment TEXT
    );

    CREATE TABLE IF NOT EXISTS change_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      competitor_id TEXT NOT NULL REFERENCES competitors(id),
      domain TEXT NOT NULL,
      field_name TEXT NOT NULL,
      old_value TEXT,
      new_value TEXT,
      severity TEXT NOT NULL,
      detected_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS ai_insights (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      competitor_id TEXT NOT NULL REFERENCES competitors(id),
      generated_at TEXT NOT NULL,
      summary TEXT,
      key_findings_json TEXT,
      implications TEXT,
      actions_json TEXT
    );

    CREATE TABLE IF NOT EXISTS scraper_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      scraper_name TEXT NOT NULL,
      started_at TEXT NOT NULL,
      finished_at TEXT,
      status TEXT NOT NULL DEFAULT 'running',
      error_message TEXT,
      records_processed INTEGER DEFAULT 0
    );
  `);

  // Additive migrations — safe to run repeatedly
  try {
    sqlite.exec(`ALTER TABLE reputation_snapshots ADD COLUMN entities_breakdown_json TEXT`);
  } catch {
    // Column already exists — ignore
  }
  try {
    sqlite.exec(`ALTER TABLE reputation_snapshots ADD COLUMN myfxbook_rating REAL`);
  } catch {
    // Column already exists — ignore
  }
  sqlite.exec(`CREATE TABLE IF NOT EXISTS ai_portfolio_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    summary TEXT,
    actions_json TEXT
  )`);
  sqlite.exec(`CREATE TABLE IF NOT EXISTS wikifx_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor_id TEXT NOT NULL REFERENCES competitors(id),
    snapshot_date TEXT NOT NULL,
    wikifx_score REAL,
    accounts_json TEXT,
    marketing_strategy_json TEXT,
    biz_area_json TEXT
  )`);

  // is_self column — identifies Pepperstone as the self-benchmark (not a competitor)
  try {
    sqlite.exec(`ALTER TABLE competitors ADD COLUMN is_self INTEGER NOT NULL DEFAULT 0`);
  } catch {
    // Column already exists — ignore
  }
  // Backfill any pre-migration rows that may have NULL (SQLite allows this on some paths)
  sqlite.exec(`UPDATE competitors SET is_self = 0 WHERE is_self IS NULL AND id != 'pepperstone'`);

  // Ensure Pepperstone exists as the self-benchmark row
  sqlite.exec(`
    INSERT OR IGNORE INTO competitors (id, name, tier, website, is_self)
    VALUES ('pepperstone', 'Pepperstone', 1, 'pepperstone.com', 1)
  `);
  // Ensure existing Pepperstone row has is_self = 1 (in case it was added before this migration)
  sqlite.exec(`UPDATE competitors SET is_self = 1 WHERE id = 'pepperstone'`);
}
