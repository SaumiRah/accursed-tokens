#!/usr/bin/env python3
"""
One-time calibration script. Run on your laptop BEFORE the first weekly run.

Measures your actual Claude Pro 5-hour and weekly token limits by:
1. Snapshotting /usage percentages
2. Running claude CLI calls and accumulating token counts
3. Detecting when each percentage ticks up by 1%
4. Computing limit = tokens_accumulated * 100

Writes calibration_result.json when done.
"""

import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

RESULT_PATH = Path(__file__).parent / "calibration_result.json"

CALIBRATION_PROMPT = (
    "Write a detailed 600-word analysis of any topic you find interesting. "
    "Be thorough and specific."
)


def get_pcts() -> tuple[float, float]:
    """Returns (pct_weekly, pct_5h) from `claude /usage`."""
    result = subprocess.run(
        ["claude", "/usage"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = result.stdout + result.stderr
    # Claude /usage outputs percentages — extract them in order
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*%", output)
    if len(matches) < 2:
        print(f"Could not parse /usage output:\n{output}")
        sys.exit(1)
    # Assumption: weekly % is listed first, 5h % second.
    # Adjust indices here if the order differs on your system.
    pct_weekly = float(matches[0])
    pct_5h = float(matches[1])
    return pct_weekly, pct_5h


def run_claude_and_count_tokens(prompt: str) -> int:
    """Runs a claude CLI call and returns input + output tokens used."""
    result = subprocess.run(
        ["claude", "--output-format", "json", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )
    try:
        data = json.loads(result.stdout)
        usage = data.get("usage", {})
        return usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
    except (json.JSONDecodeError, KeyError):
        print(f"Unexpected claude output: {result.stdout[:200]}")
        return 0


def main():
    print("Accursed Tokens — calibration starting.")
    print("This will consume some of your weekly token allowance.")
    print("Do not run this close to your Wednesday 01:30 AM reset.\n")

    pct_w0, pct_5h0 = get_pcts()
    print(f"Starting usage: {pct_w0:.1f}% weekly, {pct_5h0:.1f}% of 5h window\n")

    total_tokens = 0
    limit_5h: int | None = None
    limit_weekly: int | None = None
    iteration = 0

    while limit_5h is None or limit_weekly is None:
        iteration += 1
        tokens = run_claude_and_count_tokens(CALIBRATION_PROMPT)
        total_tokens += tokens
        print(f"  Iteration {iteration}: +{tokens:,} tokens (total: {total_tokens:,})")

        time.sleep(3)  # brief pause before re-reading /usage
        pct_w, pct_5h = get_pcts()
        print(f"  /usage: {pct_w:.1f}% weekly, {pct_5h:.1f}% 5h")

        if limit_5h is None and pct_5h - pct_5h0 >= 1.0:
            limit_5h = total_tokens * 100
            print(f"\n  [5h limit detected] {limit_5h:,} tokens\n")

        if limit_weekly is None and pct_w - pct_w0 >= 1.0:
            limit_weekly = total_tokens * 100
            print(f"\n  [Weekly limit detected] {limit_weekly:,} tokens\n")

        if iteration > 200:
            print("Too many iterations — aborting. Check /usage output format.")
            sys.exit(1)

    result = {
        "measured_on": date.today().isoformat(),
        "limit_5h": limit_5h,
        "limit_weekly": limit_weekly,
        "pct_weekly_at_calibration": pct_w,
    }

    RESULT_PATH.write_text(json.dumps(result, indent=2))
    print(f"\nCalibration complete. Results written to {RESULT_PATH}")
    print(f"  5-hour limit:  {limit_5h:,} tokens")
    print(f"  Weekly limit:  {limit_weekly:,} tokens")
    print("\nCommit calibration_result.json to your repo.")


if __name__ == "__main__":
    main()
