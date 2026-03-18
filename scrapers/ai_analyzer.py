"""
ai_analyzer.py
--------------
Reads today's change_events from the database, groups by competitor, and calls
the Anthropic API (Claude claude-sonnet-4-6) with tool use to generate structured
competitive intelligence insights.  Results are written to the ai_insights table.

Requires environment variable: ANTHROPIC_API_KEY

Run from the project root:
    ANTHROPIC_API_KEY=your_key python scrapers/ai_analyzer.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

_SCRAPERS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRAPERS_DIR)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env.local"))
if _SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, _SCRAPERS_DIR)

from config import COMPETITORS
from db_utils import get_db, log_scraper_run, update_scraper_run

SCRAPER_NAME = "ai_analyzer"

# ---------------------------------------------------------------------------
# Anthropic tool definition for structured output
# ---------------------------------------------------------------------------

INSIGHT_TOOL = {
    "name": "record_competitive_insight",
    "description": (
        "Record a structured competitive intelligence insight for a broker competitor. "
        "This tool must be called once with all findings."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "One paragraph executive summary of what changed and why it matters.",
            },
            "key_findings": {
                "type": "array",
                "description": "List of specific findings from the change events.",
                "items": {
                    "type": "object",
                    "properties": {
                        "finding": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"],
                        },
                        "evidence": {
                            "type": "string",
                            "description": "The specific data point(s) that support this finding.",
                        },
                    },
                    "required": ["finding", "severity", "evidence"],
                },
            },
            "pepperstone_implications": {
                "type": "string",
                "description": (
                    "One paragraph explaining what these changes mean specifically "
                    "for Pepperstone's competitive position in the APAC region."
                ),
            },
            "recommended_actions": {
                "type": "array",
                "description": "Specific actions Pepperstone should consider.",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "urgency": {
                            "type": "string",
                            "enum": ["immediate", "this_week", "this_month"],
                        },
                    },
                    "required": ["action", "urgency"],
                },
            },
        },
        "required": [
            "summary",
            "key_findings",
            "pepperstone_implications",
            "recommended_actions",
        ],
    },
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def fetch_todays_changes(conn) -> dict[str, list[dict]]:
    """
    Return a dict mapping competitor_id -> list of change_event dicts
    for events detected today (UTC).
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = conn.execute(
        """
        SELECT competitor_id, domain, field_name, old_value, new_value, severity, detected_at
        FROM change_events
        WHERE detected_at LIKE ?
        ORDER BY competitor_id, detected_at
        """,
        (f"{today}%",),
    ).fetchall()

    result: dict[str, list[dict]] = {}
    for row in rows:
        cid = row["competitor_id"]
        if cid not in result:
            result[cid] = []
        result[cid].append(dict(row))
    return result


def get_competitor_meta(conn, competitor_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM competitors WHERE id = ?", (competitor_id,)
    ).fetchone()
    return dict(row) if row else None


def get_recent_news(conn, competitor_id: str, limit: int = 5) -> list[dict]:
    rows = conn.execute(
        """
        SELECT title, source, published_at, sentiment
        FROM news_items
        WHERE competitor_id = ?
        ORDER BY published_at DESC
        LIMIT ?
        """,
        (competitor_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(competitor: dict, changes: list[dict], recent_news: list[dict]) -> str:
    tier_labels = {1: "Tier 1 (major global broker)", 2: "Tier 2 (regional broker)", 3: "Tier 3 (smaller/niche broker)"}
    tier_desc = tier_labels.get(competitor.get("tier", 1), "Unknown tier")

    changes_text = "\n".join(
        f"  - [{c['severity'].upper()}] {c['domain']}.{c['field_name']}: "
        f"{c['old_value'] or 'N/A'} → {c['new_value']} (detected: {c['detected_at']})"
        for c in changes
    )

    news_text = ""
    if recent_news:
        news_text = "\n\nRecent news headlines:\n" + "\n".join(
            f"  - [{n['sentiment']}] {n['title']} ({n['source']}, {n['published_at'][:10]})"
            for n in recent_news
        )

    return f"""You are a senior competitive intelligence analyst at Pepperstone, a leading global CFD and forex broker headquartered in Melbourne, Australia, with a strong focus on the APAC region.

Competitor under analysis:
  Name: {competitor.get('name', 'Unknown')}
  Classification: {tier_desc}
  Website: {competitor.get('website', 'N/A')}

Change events detected today ({datetime.now(timezone.utc).strftime('%Y-%m-%d')}):
{changes_text}
{news_text}

Context about Pepperstone:
- Primary markets: Australia, UK, Europe, APAC
- Key differentiators: tight spreads on major FX pairs, fast execution, strong regulation (ASIC, FCA, CySEC, DFSA, SCB, BaFID)
- Target clients: active retail traders, professional traders, algo traders
- Strong in MetaTrader 4/5 and cTrader platforms

Your task:
Analyze the competitor's changes from Pepperstone's perspective. Consider:
1. Do these changes represent a genuine competitive threat or opportunity for Pepperstone?
2. Are they becoming more aggressive on pricing (spreads, leverage, deposits)?
3. Are promotions designed to poach Pepperstone's client segments?
4. What should Pepperstone's commercial, product, or marketing teams do in response?

Use the record_competitive_insight tool to return your analysis in structured JSON format.
Be specific, evidence-based, and commercially focused. Avoid generic observations."""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        sys.exit(1)

    try:
        from anthropic import Anthropic
    except ImportError:
        print("ERROR: anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    client = Anthropic(api_key=api_key)

    run_id = log_scraper_run(SCRAPER_NAME, "running")
    total_records = 0
    error_summary = []

    conn = get_db()

    # Build a lookup for competitor config (from COMPETITORS list)
    comp_config = {c["id"]: c for c in COMPETITORS}

    # Get today's changes grouped by competitor
    todays_changes = fetch_todays_changes(conn)

    if not todays_changes:
        print("No change events detected today. Nothing to analyze.")
        update_scraper_run(run_id, "success", 0)
        conn.close()
        return

    print(f"Found change events for {len(todays_changes)} competitor(s).")

    generated_at = datetime.now(timezone.utc).isoformat()

    for competitor_id, changes in todays_changes.items():
        print(f"Processing {competitor_id} ({len(changes)} change events)...")

        # Get competitor metadata — try DB first, fall back to config
        competitor = get_competitor_meta(conn, competitor_id)
        if not competitor:
            cfg = comp_config.get(competitor_id)
            if cfg:
                competitor = {"id": cfg["id"], "name": cfg["name"], "tier": cfg["tier"], "website": cfg["website"]}
            else:
                competitor = {"id": competitor_id, "name": competitor_id, "tier": 1, "website": ""}

        recent_news = get_recent_news(conn, competitor_id)
        prompt = build_prompt(competitor, changes, recent_news)

        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                tools=[INSIGHT_TOOL],
                tool_choice={"type": "tool", "name": "record_competitive_insight"},
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract tool use block
            insight_data = None
            for block in response.content:
                if block.type == "tool_use" and block.name == "record_competitive_insight":
                    insight_data = block.input
                    break

            if not insight_data:
                raise ValueError("Model did not return a tool_use block.")

            summary = insight_data.get("summary", "")
            key_findings = insight_data.get("key_findings", [])
            implications = insight_data.get("pepperstone_implications", "")
            actions = insight_data.get("recommended_actions", [])

            conn.execute(
                """
                INSERT INTO ai_insights
                    (competitor_id, generated_at, summary, key_findings_json, implications, actions_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    competitor_id,
                    generated_at,
                    summary,
                    json.dumps(key_findings),
                    implications,
                    json.dumps(actions),
                ),
            )
            conn.commit()
            total_records += 1

            # Print summary to stdout
            print(f"    Summary: {summary[:150]}...")
            for finding in key_findings:
                sev = finding.get("severity", "?").upper()
                print(f"    [{sev}] {finding.get('finding', '')[:100]}")
            print(f"    Actions: {len(actions)} recommended")

        except Exception as e:
            msg = f"{competitor_id}: {e}"
            print(f"    ERROR: {msg}")
            error_summary.append(msg)

    conn.close()

    status = "success" if not error_summary else "partial"
    error_msg = "; ".join(error_summary) if error_summary else None
    update_scraper_run(run_id, status, total_records, error_msg)
    print(f"\nDone. Insights generated: {total_records}. Status: {status}")


if __name__ == "__main__":
    run()
