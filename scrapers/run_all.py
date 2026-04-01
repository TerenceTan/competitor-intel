"""
run_all.py
----------
Runs all scraper scripts in sequence and reports overall status.
Output is printed to stdout AND written to logs/<scraper-name>.log

Run from the project root:
    python scrapers/run_all.py

Optional environment variables:
    YOUTUBE_API_KEY    - required for social_scraper.py
    ANTHROPIC_API_KEY  - required for ai_analyzer.py
"""

import subprocess
import sys
import os
import time
from datetime import datetime

# Always run from the project root so relative DB paths work correctly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRAPERS_DIR = os.path.join(PROJECT_ROOT, "scrapers")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")

SCRIPTS = [
    "pricing_scraper.py",
    "account_types_scraper.py",
    "promo_scraper.py",
    "social_scraper.py",
    "reputation_scraper.py",
    "wikifx_scraper.py",
    "news_scraper.py",
    "ai_analyzer.py",
]


def _log_name(script_name: str) -> str:
    """Convert e.g. 'pricing_scraper.py' → 'pricing-scraper'."""
    return script_name.replace("_", "-").replace(".py", "")


def run_script(script_name: str) -> tuple[bool, float, str]:
    """
    Run a single scraper script as a subprocess.
    Streams output to stdout in real-time and also writes to logs/<name>.log.
    Returns (success: bool, elapsed_seconds: float, output: str).
    """
    script_path = os.path.join(SCRAPERS_DIR, script_name)
    log_path = os.path.join(LOGS_DIR, f"{_log_name(script_name)}.log")

    start = time.time()
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    elapsed = time.time() - start

    output = result.stdout
    if result.stderr:
        output += "\n--- STDERR ---\n" + result.stderr

    # Write to per-scraper log file (append, with run timestamp header)
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"Run at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        f.write(f"Exit code: {result.returncode}\n")
        f.write(f"{'='*60}\n")
        f.write(output)
        f.write("\n")

    return result.returncode == 0, elapsed, output


def main():
    os.makedirs(LOGS_DIR, exist_ok=True)
    run_log_path = os.path.join(LOGS_DIR, "run-all.log")

    header = (
        f"\n{'='*60}\n"
        f"Competitor Intelligence Dashboard - Full Scraper Run\n"
        f"Started at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        f"Project root: {PROJECT_ROOT}\n"
        f"{'='*60}\n"
    )
    print(header, end="")

    results = []
    full_log = [header]

    for script in SCRIPTS:
        line = f"\n[{datetime.utcnow().strftime('%H:%M:%S')}] Running {script}...\n" + "-" * 40
        print(line)
        full_log.append(line + "\n")

        success, elapsed, output = run_script(script)
        status = "OK" if success else "FAILED"
        results.append((script, success, elapsed))

        for ln in output.strip().splitlines():
            indented = f"  {ln}"
            print(indented)
            full_log.append(indented + "\n")

        result_line = f"\n  -> {status} in {elapsed:.1f}s"
        print(result_line)
        full_log.append(result_line + "\n")

    # Final summary
    summary_lines = [
        "\n" + "=" * 60,
        "SUMMARY",
        "=" * 60,
    ]
    all_ok = True
    for script, success, elapsed in results:
        icon = "✓" if success else "✗"
        status = "OK" if success else "FAILED"
        summary_lines.append(f"  {icon}  {script:<30} {status:<10} {elapsed:.1f}s")
        if not success:
            all_ok = False

    overall = "ALL SCRAPERS COMPLETED SUCCESSFULLY" if all_ok else "SOME SCRAPERS FAILED"
    summary_lines += [
        "=" * 60,
        f"Result: {overall}",
        f"Finished at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "=" * 60,
    ]

    summary = "\n".join(summary_lines) + "\n"
    print(summary)
    full_log.append(summary)

    # Write combined run-all log
    with open(run_log_path, "a", encoding="utf-8") as f:
        f.writelines(full_log)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
