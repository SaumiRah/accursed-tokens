#!/usr/bin/env python3
"""
One-time calibration script. Run on your laptop BEFORE the first weekly run.

Measures your actual Claude Pro weekly token limit by:
1. Asking you to check /usage in your Claude Code terminal and enter the % used
2. Running a series of claude CLI calls, counting tokens from each response
3. Asking you to check /usage again and enter the new %
4. Computing: weekly_limit = tokens_consumed / (delta_pct / 100)

Writes calibration_result.json when done.
"""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

RESULT_PATH = Path(__file__).parent / "calibration_result.json"
STATS_PATH = Path.home() / ".claude" / "stats-cache.json"

CALIBRATION_PROMPT = (
    "Write a detailed 800-word analysis of any topic you find interesting. "
    "Be thorough, specific, and use concrete examples."
)

TARGET_CALLS = 5  # number of calls to make; adjust if delta is too small to read


def read_weekly_tokens_from_stats(billing_reset_weekday: int = 2) -> int:
    """
    Sum tokens from stats-cache.json for the current billing week.
    billing_reset_weekday: 0=Mon … 6=Sun. Default 2 = Wednesday.
    Returns total tokens used since the last Wednesday reset.
    """
    if not STATS_PATH.exists():
        return 0
    data = json.loads(STATS_PATH.read_text())
    today = date.today()
    days_since_reset = (today.weekday() - billing_reset_weekday) % 7
    week_start = today.toordinal() - days_since_reset

    total = 0
    for entry in data.get("dailyModelTokens", []):
        entry_ordinal = date.fromisoformat(entry["date"]).toordinal()
        if entry_ordinal >= week_start:
            total += sum(entry["tokensByModel"].values())
    return total


def ask_usage_pct(label: str) -> float:
    """Prompt user to check /usage interactively and enter the percentage."""
    print(f"\n{'='*60}")
    print(f"  ACTION REQUIRED — {label}")
    print(f"{'='*60}")
    print("  1. Open a new terminal (or another Claude Code session)")
    print("  2. Type:  /usage")
    print("  3. Find the weekly usage percentage (e.g. '14%')")
    print("  4. Enter it below.")
    print()
    while True:
        raw = input("  Weekly % used (just the number, e.g. 14): ").strip().rstrip("%")
        try:
            val = float(raw)
            if 0.0 <= val <= 100.0:
                return val
        except ValueError:
            pass
        print("  Please enter a number between 0 and 100.")


def run_claude_call(prompt: str, call_num: int, total: int) -> int:
    """Run one claude call, return tokens used (input + output)."""
    print(f"  Call {call_num}/{total}...", end=" ", flush=True)
    result = subprocess.run(
        ["claude", "--output-format", "json", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        print(f"FAILED\n  stderr: {result.stderr[:200]}")
        return 0
    try:
        data = json.loads(result.stdout)
        usage = data.get("usage", {})
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        print(f"{tokens:,} tokens")
        return tokens
    except (json.JSONDecodeError, KeyError, TypeError):
        # Try to find tokens in a different output structure
        print(f"could not parse response (output: {result.stdout[:100]!r})")
        return 0


def main():
    print("Accursed Tokens — calibration")
    print("This will consume a small portion of your weekly token allowance.\n")

    # Show current weekly usage from stats-cache as a sanity check
    weekly_so_far = read_weekly_tokens_from_stats()
    if weekly_so_far:
        print(f"stats-cache shows ~{weekly_so_far:,} tokens used so far this billing week.")
        print("(This may lag by a session or two — /usage is more accurate.)\n")

    # Step 1: get starting percentage
    pct_before = ask_usage_pct("BEFORE calibration")
    print(f"\n  Recorded: {pct_before:.1f}% used before calibration.\n")

    # Step 2: run calibration calls
    print(f"Running {TARGET_CALLS} calibration calls...\n")
    total_tokens = 0
    for i in range(1, TARGET_CALLS + 1):
        total_tokens += run_claude_call(CALIBRATION_PROMPT, i, TARGET_CALLS)

    print(f"\nTotal tokens consumed: {total_tokens:,}")

    if total_tokens == 0:
        print("\nNo tokens were counted — check that `claude --output-format json -p` works.")
        sys.exit(1)

    # Step 3: get ending percentage
    pct_after = ask_usage_pct("AFTER calibration")
    print(f"\n  Recorded: {pct_after:.1f}% used after calibration.")

    delta_pct = pct_after - pct_before
    if delta_pct <= 0:
        print(f"\nNo percentage increase detected (delta = {delta_pct:.2f}%).")
        print("The /usage percentage may not have updated yet, or the change was < 1%.")
        print(f"Try increasing TARGET_CALLS (currently {TARGET_CALLS}) at the top of this script.")
        sys.exit(1)

    weekly_limit = int(total_tokens / (delta_pct / 100.0))
    print(f"\n  Weekly limit estimate: {weekly_limit:,} tokens  ({delta_pct:.2f}% delta)")

    result = {
        "measured_on": date.today().isoformat(),
        "weekly_limit": weekly_limit,
        "calibration_tokens_consumed": total_tokens,
        "pct_before": pct_before,
        "pct_after": pct_after,
        "delta_pct": round(delta_pct, 2),
    }

    RESULT_PATH.write_text(json.dumps(result, indent=2))
    print(f"\nWritten to {RESULT_PATH}")
    print("Commit this file to your repo.\n")


if __name__ == "__main__":
    main()
