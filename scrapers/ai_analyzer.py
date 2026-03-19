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

PORTFOLIO_TOOL = {
    "name": "record_portfolio_actions",
    "description": (
        "Record a single consolidated set of recommended actions for Pepperstone "
        "after reviewing all competitor intelligence from today. "
        "De-duplicate and prioritise across all competitors into the most important actions. "
        "This tool must be called once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": (
                    "One paragraph summarising the overall competitive landscape today — "
                    "which competitors are most active, what the dominant themes are, "
                    "and Pepperstone's overall position."
                ),
            },
            "recommended_actions": {
                "type": "array",
                "description": (
                    "Prioritised list of concrete actions Pepperstone should take, "
                    "synthesised across all competitors. Remove duplicates. Aim for 5–10 actions total."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "urgency": {
                            "type": "string",
                            "enum": ["immediate", "this_week", "this_month"],
                        },
                        "rationale": {
                            "type": "string",
                            "description": "One sentence explaining why this action is needed, naming the specific competitor(s) that triggered it.",
                        },
                    },
                    "required": ["action", "urgency", "rationale"],
                },
            },
        },
        "required": ["summary", "recommended_actions"],
    },
}

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
    for events detected today (UTC). Excludes self (Pepperstone).
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = conn.execute(
        """
        SELECT ce.competitor_id, ce.domain, ce.field_name, ce.old_value,
               ce.new_value, ce.severity, ce.detected_at
        FROM change_events ce
        JOIN competitors c ON c.id = ce.competitor_id
        WHERE ce.detected_at LIKE ?
          AND (c.is_self IS NULL OR c.is_self = 0)
        ORDER BY ce.competitor_id, ce.detected_at
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


def get_pepperstone_snapshot(conn) -> dict:
    """Fetch the latest scraped snapshots for Pepperstone (self-benchmark)."""
    pricing = conn.execute(
        "SELECT * FROM pricing_snapshots WHERE competitor_id = 'pepperstone' ORDER BY snapshot_date DESC LIMIT 1"
    ).fetchone()
    reputation = conn.execute(
        "SELECT * FROM reputation_snapshots WHERE competitor_id = 'pepperstone' ORDER BY snapshot_date DESC LIMIT 1"
    ).fetchone()
    return {
        "pricing": dict(pricing) if pricing else {},
        "reputation": dict(reputation) if reputation else {},
    }


def build_pepperstone_context(snap: dict) -> str:
    """Build a live-data Pepperstone context block for AI prompts."""
    p = snap.get("pricing", {})
    r = snap.get("reputation", {})
    lines = [
        "Context about Pepperstone (live scraped data):",
        "- Primary markets: Australia, UK, Europe, APAC",
        "- Regulation: ASIC, FCA, CySEC, DFSA, SCB, BaFin",
        "- Platforms: MetaTrader 4/5, cTrader, TradingView",
        "- Target clients: active retail traders, professional traders, algo traders",
    ]
    if p.get("min_deposit_usd"):
        lines.append(f"- Current min deposit: ${p['min_deposit_usd']:.0f} USD")
    if p.get("leverage_json"):
        lines.append(f"- Current leverage: {p['leverage_json']}")
    if p.get("instruments_count"):
        lines.append(f"- Instruments count: {p['instruments_count']}")
    if r.get("trustpilot_score"):
        tc = r.get("trustpilot_count", "?")
        lines.append(f"- Trustpilot: {r['trustpilot_score']:.1f} ({tc} reviews)")
    if r.get("fpa_rating"):
        lines.append(f"- ForexPeaceArmy rating: {r['fpa_rating']:.1f}")
    if r.get("ios_rating"):
        lines.append(f"- App Store rating: {r['ios_rating']:.1f}")
    if r.get("myfxbook_rating"):
        lines.append(f"- MyFXBook rating: {r['myfxbook_rating']:.1f}")
    if len(lines) == 5:
        # No live data yet — fall back to static description
        lines.append("- Key differentiators: tight spreads on major FX pairs, fast execution (<40 ms avg)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_portfolio_prompt(all_insights: list[dict], pepperstone_context: str) -> str:
    """
    Build a prompt that feeds all per-competitor insights into Claude
    to produce one consolidated recommended action list.
    """
    sections = []
    for item in all_insights:
        name = item["name"]
        summary = item["summary"]
        findings_text = "\n".join(
            f"    [{f['severity'].upper()}] {f['finding']}"
            for f in item.get("key_findings", [])
        )
        actions_text = "\n".join(
            f"    [{a['urgency']}] {a['action']}"
            for a in item.get("actions", [])
        )
        sections.append(
            f"Competitor: {name}\n"
            f"  Summary: {summary}\n"
            f"  Key findings:\n{findings_text or '    (none)'}\n"
            f"  Per-competitor actions:\n{actions_text or '    (none)'}"
        )

    competitors_block = "\n\n".join(sections)

    return f"""You are a senior competitive intelligence analyst at Pepperstone, a leading global CFD and forex broker headquartered in Melbourne, Australia, with a strong focus on the APAC region.

Below are today's competitive intelligence reports for each competitor where changes were detected:

{competitors_block}

{pepperstone_context}

Your task:
Synthesise ALL of the above into ONE consolidated, prioritised action plan for Pepperstone.
- Remove duplicate or near-duplicate actions — keep only the most impactful version.
- Elevate urgency where multiple competitors are moving in the same direction.
- Where relevant, reference specific Pepperstone metrics above (e.g. "our Trustpilot is X vs competitor Y") to make recommendations data-driven.
- Each action must name the competitor(s) that triggered it in the rationale.
- Aim for 5–10 actions total, ordered by urgency (immediate first).

Use the record_portfolio_actions tool to return your analysis."""


def build_prompt(competitor: dict, changes: list[dict], recent_news: list[dict], pepperstone_context: str) -> str:
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

{pepperstone_context}

Your task:
Analyze the competitor's changes from Pepperstone's perspective. Consider:
1. Do these changes represent a genuine competitive threat or opportunity for Pepperstone?
2. Are they becoming more aggressive on pricing (spreads, leverage, deposits)?
3. Are promotions designed to poach Pepperstone's client segments?
4. Where relevant, directly compare the competitor's metrics to Pepperstone's live data above.
5. What should Pepperstone's commercial, product, or marketing teams do in response?

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

    # Fetch live Pepperstone benchmark data for prompt context
    pepperstone_snap = get_pepperstone_snapshot(conn)
    pepperstone_context = build_pepperstone_context(pepperstone_snap)

    # Get today's changes grouped by competitor (excludes Pepperstone)
    todays_changes = fetch_todays_changes(conn)

    if not todays_changes:
        print("No change events detected today. Nothing to analyze.")
        update_scraper_run(run_id, "success", 0)
        conn.close()
        return

    print(f"Found change events for {len(todays_changes)} competitor(s).")

    generated_at = datetime.now(timezone.utc).isoformat()

    # Collect per-competitor insights for portfolio synthesis
    all_insights_for_portfolio: list[dict] = []

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
        prompt = build_prompt(competitor, changes, recent_news, pepperstone_context)

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

            # Collect for portfolio synthesis
            all_insights_for_portfolio.append({
                "name": competitor.get("name", competitor_id),
                "summary": summary,
                "key_findings": key_findings,
                "actions": actions,
            })

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

    # -----------------------------------------------------------------------
    # Portfolio synthesis — one consolidated action plan across all competitors
    # -----------------------------------------------------------------------
    if all_insights_for_portfolio:
        print(f"\nGenerating consolidated portfolio actions from {len(all_insights_for_portfolio)} competitor(s)...")
        try:
            portfolio_prompt = build_portfolio_prompt(all_insights_for_portfolio, pepperstone_context)
            portfolio_response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                tools=[PORTFOLIO_TOOL],
                tool_choice={"type": "tool", "name": "record_portfolio_actions"},
                messages=[{"role": "user", "content": portfolio_prompt}],
            )

            portfolio_data = None
            for block in portfolio_response.content:
                if block.type == "tool_use" and block.name == "record_portfolio_actions":
                    portfolio_data = block.input
                    break

            if not portfolio_data:
                raise ValueError("Model did not return a portfolio tool_use block.")

            portfolio_summary = portfolio_data.get("summary", "")
            portfolio_actions = portfolio_data.get("recommended_actions", [])

            conn.execute(
                """
                INSERT INTO ai_portfolio_insights (generated_at, summary, actions_json)
                VALUES (?, ?, ?)
                """,
                (generated_at, portfolio_summary, json.dumps(portfolio_actions)),
            )
            conn.commit()

            print(f"    Portfolio summary: {portfolio_summary[:150]}...")
            print(f"    Consolidated actions: {len(portfolio_actions)}")

        except Exception as e:
            msg = f"portfolio_synthesis: {e}"
            print(f"    ERROR: {msg}")
            error_summary.append(msg)

    conn.close()

    status = "success" if not error_summary else "partial"
    error_msg = "; ".join(error_summary) if error_summary else None
    update_scraper_run(run_id, status, total_records, error_msg)
    print(f"\nDone. Insights generated: {total_records}. Status: {status}")


if __name__ == "__main__":
    run()
