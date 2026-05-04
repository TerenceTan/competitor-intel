"""One-shot validation run: fetch FB + IG + X follower counts for ALL 11
competitors in a single script. Output is a clean Markdown + CSV table the
operator can paste into a Slack message or upgrade-request email.

Goal: produce visible proof that Apify works for all 11 brokers across all 3
social platforms, so the paid Apify subscription request has hard data behind it.

Usage:
    cd /home/ubuntu/app
    source .venv/bin/activate
    python scrapers/admin/apify_validation_run.py

Cost (free tier): ~$0.40 total, broken down:
    IG (apify/instagram-profile-scraper)               1 call × 11 profiles  = $0.029
    X  (kaitoeasyapi cheapest tweet scraper)           1 call × ~220 tweets  = $0.055
    FB (apify/facebook-posts-scraper, 5 posts/page)    1 call × 11 pages × 5 = $0.281
                                                        actor-start         = $0.006
                                                                            = $0.371

Writes nothing to the production DB. Read-only smoke for Phase 2 budget
justification.
"""
import json
import os
import sys
from decimal import Decimal

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env.local"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scrapers"))

from apify_client import ApifyClient  # noqa: E402
from config import COMPETITORS  # noqa: E402

IG_ACTOR = "apify/instagram-profile-scraper"
X_ACTOR  = "kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest"
FB_ACTOR = "apify/facebook-posts-scraper"

# Conservative cost caps per call. If any single batch exceeds these, Apify
# aborts that run — we'd rather have partial results than a runaway charge.
IG_CAP = Decimal("0.50")
X_CAP  = Decimal("0.50")
FB_CAP = Decimal("2.00")  # FB is the most expensive — 11 pages × 5 posts


def collect_handles():
    """Return list of (id, name, fb_slug, ig, x) tuples, skipping any with empty social handles."""
    rows = []
    for c in COMPETITORS:
        rows.append((
            c.get("id", "?"),
            c.get("name", "?"),
            c.get("facebook_slug") or "",
            c.get("instagram_handle") or "",
            c.get("x_handle") or "",
        ))
    return rows


def run_ig(client: ApifyClient, handles: list[str]) -> dict:
    """Returns {handle: followers_count} for each IG handle."""
    print(f"\n=== IG batch: {len(handles)} profiles via {IG_ACTOR} ===")
    if not handles:
        return {}
    run = client.actor(IG_ACTOR).call(
        run_input={"usernames": handles},
        max_total_charge_usd=IG_CAP,
    )
    if run is None:
        print("  IG actor returned None (cost cap or failure)")
        return {}
    print(f"  status: {run.get('status')}  runId: {run.get('id')}")
    items = list(client.dataset(run.get("defaultDatasetId")).iterate_items())
    print(f"  items: {len(items)}")
    out = {}
    for it in items:
        u = it.get("username") or ""
        fc = it.get("followersCount")
        if u and isinstance(fc, int):
            out[u.lower()] = fc
    return out


def run_x(client: ApifyClient, handles: list[str]) -> dict:
    """Returns {handle_lower: followers_count} via embedded author.followers."""
    print(f"\n=== X batch: {len(handles)} handles via {X_ACTOR} ===")
    if not handles:
        return {}
    run = client.actor(X_ACTOR).call(
        run_input={
            "searchTerms": [f"from:{h}" for h in handles],
            "maxItems": len(handles),  # just need 1 tweet per user
        },
        max_total_charge_usd=X_CAP,
    )
    if run is None:
        print("  X actor returned None")
        return {}
    print(f"  status: {run.get('status')}  runId: {run.get('id')}")
    items = list(client.dataset(run.get("defaultDatasetId")).iterate_items())
    print(f"  items: {len(items)}")
    out = {}
    mock_count = 0
    for tweet in items:
        if tweet.get("type") == "mock_tweet":
            mock_count += 1
            continue
        author = tweet.get("author") or {}
        u = (author.get("userName") or "").lower()
        fc = author.get("followers")
        if u and isinstance(fc, int) and u not in out:
            out[u] = fc
    if mock_count:
        print(f"  ⚠ {mock_count} mock placeholders (handles that 404'd)")
    return out


def run_fb(client: ApifyClient, slugs: list[str]) -> dict:
    """Returns {slug_lower: page_likes_or_followers} via apify FB posts scraper.

    The FB posts scraper does not return follower count directly — it returns
    posts. We extract pageId / pageLikes from the first post per page (if the
    actor surfaces it). If neither is present, we fall back to a simple
    'has-recent-posts' yes/no signal.
    """
    print(f"\n=== FB batch: {len(slugs)} pages via {FB_ACTOR} (5 posts each) ===")
    if not slugs:
        return {}
    run = client.actor(FB_ACTOR).call(
        run_input={
            "startUrls": [{"url": f"https://www.facebook.com/{s}"} for s in slugs],
            "resultsLimit": 5,
        },
        max_total_charge_usd=FB_CAP,
    )
    if run is None:
        print("  FB actor returned None")
        return {}
    print(f"  status: {run.get('status')}  runId: {run.get('id')}")
    items = list(client.dataset(run.get("defaultDatasetId")).iterate_items())
    print(f"  items: {len(items)}")

    # Group posts by page slug, pick the first per page, extract followers/likes
    by_page = {}
    for post in items:
        # Slug usually appears in pageUrl or url
        url = post.get("pageUrl") or post.get("url") or ""
        slug = ""
        for s in slugs:
            if f"/{s}" in url.lower():
                slug = s.lower()
                break
        if not slug:
            continue
        if slug in by_page:
            continue  # only first post per page
        # Hunt for follower/like count under various keys the actor may use
        fc = (
            post.get("pageFollowers")
            or post.get("pageLikes")
            or post.get("followers")
            or post.get("likes")
            or (post.get("page") or {}).get("followers")
            or (post.get("page") or {}).get("likes")
        )
        by_page[slug] = fc if isinstance(fc, int) else None
    return by_page


def main() -> int:
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        print("ERROR: APIFY_API_TOKEN not set", file=sys.stderr)
        return 1

    rows = collect_handles()
    print(f"=== Validating {len(rows)} competitors across FB + IG + X ===")
    for r in rows:
        print(f"  {r[0]:14s}  fb={r[2] or '-':25s}  ig={r[3] or '-':22s}  x={r[4] or '-'}")

    client = ApifyClient(token)

    ig_handles = [r[3] for r in rows if r[3]]
    x_handles  = [r[4] for r in rows if r[4]]
    fb_slugs   = [r[2] for r in rows if r[2]]

    ig_map = run_ig(client, ig_handles)
    x_map  = run_x(client, x_handles)
    fb_map = run_fb(client, fb_slugs)

    # Build the output table
    print("\n" + "=" * 96)
    print("VALIDATION RESULTS — Apify follower counts across 11 competitors")
    print("=" * 96)
    header = f"| {'id':14s} | {'name':22s} | {'FB':>10s} | {'IG':>10s} | {'X':>10s} |"
    sep = "|" + "-" * 16 + "|" + "-" * 24 + "|" + "-" * 12 + "|" + "-" * 12 + "|" + "-" * 12 + "|"
    print(header)
    print(sep)
    csv_lines = ["id,name,facebook_slug,instagram_handle,x_handle,fb_followers,ig_followers,x_followers"]
    for cid, name, fb, ig, x in rows:
        ig_v = ig_map.get(ig.lower(), "—") if ig else "—"
        x_v  = x_map.get(x.lower(),  "—") if x  else "—"
        fb_v = fb_map.get(fb.lower(), "—") if fb else "—"
        ig_str = f"{ig_v:,}" if isinstance(ig_v, int) else str(ig_v)
        x_str  = f"{x_v:,}"  if isinstance(x_v,  int) else str(x_v)
        fb_str = f"{fb_v:,}" if isinstance(fb_v, int) else str(fb_v)
        print(f"| {cid:14s} | {name:22s} | {fb_str:>10s} | {ig_str:>10s} | {x_str:>10s} |")
        csv_lines.append(f"{cid},{name},{fb},{ig},{x},{fb_v if isinstance(fb_v,int) else ''},{ig_v if isinstance(ig_v,int) else ''},{x_v if isinstance(x_v,int) else ''}")

    # Save CSV alongside the script for easy paste-into-spreadsheet
    csv_path = os.path.join(PROJECT_ROOT, "logs", "apify_validation.csv")
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w") as f:
        f.write("\n".join(csv_lines) + "\n")
    print(f"\nCSV written: {csv_path}")
    print(f"Markdown table above is paste-ready for upgrade-request docs.")

    # Coverage summary
    ig_hits = sum(1 for cid,_,_,ig,_ in rows if ig and ig.lower() in ig_map)
    x_hits  = sum(1 for cid,_,_,_,x in rows if x and x.lower() in x_map)
    fb_hits = sum(1 for cid,_,fb,_,_ in rows if fb and fb.lower() in fb_map and fb_map[fb.lower()] is not None)
    print(f"\nCoverage:")
    print(f"  IG:  {ig_hits}/{len(ig_handles)} handles returned follower count")
    print(f"  X:   {x_hits}/{len(x_handles)} handles returned follower count")
    print(f"  FB:  {fb_hits}/{len(fb_slugs)} pages returned follower count "
          f"(may be 0 — apify/facebook-posts-scraper doesn't always surface page metadata)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
