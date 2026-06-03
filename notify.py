"""
Two-way notifications for Accursed Tokens via GitHub Issues (over the `gh` CLI).

Why GitHub: the remote orchestrator environment blocks raw TCP (SMTP/IMAP),
and ntfy.sh denylists its cloud IP — but GitHub works there (the agent already
clones and pushes over it). So notifications ride on GitHub Issues:

  send(subject, body) -> opens an issue (you get a GitHub mobile push)
  poll(...)           -> polls that issue's comments for your reply

Reply by commenting on the issue (e.g. "42%") from the GitHub app or web.

Requires the `gh` CLI authenticated with `repo` scope. Auth is ambient in the
remote env and configured on the user's laptop — no secrets needed in the
routine prompt. Run from within the accursed-tokens checkout so `gh` can
resolve the repo via the {owner}/{repo} placeholders.

Usage (CLI):
  python notify.py send "<subject>" "<body>"
  python notify.py poll "<subject>" "<sent_utc_iso>" [timeout_seconds]

poll exits 0 with the reply body, or exits 1 on timeout.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# Within one orchestrator run, send() records the issue number here so poll()
# can find it without a title search. Kept in tmp so it never lands in the repo.
_STATE_FILE = Path(tempfile.gettempdir()) / "accursed_notify_issue.json"

# GitHub user to @-mention and assign on each issue so they get a notification.
# Note: GitHub suppresses notifications for your own actions, so this only pings
# the user if the issue is authored by a *different* identity (e.g. a bot/app).
MENTION = os.environ.get("NOTIFY_MENTION", "SaumiRah")


def _gh_api(path, method="GET", fields=None):
    """Call `gh api`; gh handles auth and substitutes {owner}/{repo} from cwd."""
    cmd = ["gh", "api", "-X", method, path]
    for k, v in (fields or {}).items():
        cmd += ["-f", f"{k}={v}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(
            f"gh api {method} {path} failed: {res.stderr.strip() or res.stdout.strip()}"
        )
    out = res.stdout.strip()
    return json.loads(out) if out else None


def _parse_gh_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def send(subject: str, body: str) -> datetime:
    """Open a GitHub issue and return the UTC datetime it was created."""
    sent_at = datetime.now(timezone.utc)
    full_body = f"{body}\n\ncc @{MENTION}" if MENTION else body
    issue = _gh_api("repos/{owner}/{repo}/issues", "POST",
                    {"title": subject, "body": full_body})
    # Best-effort: also assign the user (another notification trigger). Ignore
    # failures so a non-assignable user never blocks the notification itself.
    if MENTION:
        try:
            _gh_api(f"repos/{{owner}}/{{repo}}/issues/{issue['number']}/assignees",
                    "POST", {"assignees[]": MENTION})
        except Exception as e:
            print(f"[notify] could not assign @{MENTION}: {e}", file=sys.stderr)
    try:
        _STATE_FILE.write_text(json.dumps({"subject": subject, "number": issue["number"]}))
    except Exception:
        pass
    return sent_at


def _find_issue_number(subject: str) -> int:
    # Prefer the number recorded by the matching send().
    try:
        st = json.loads(_STATE_FILE.read_text())
        if st.get("subject") == subject and st.get("number"):
            return st["number"]
    except Exception:
        pass
    # Fall back to the newest issue whose title matches the subject.
    issues = _gh_api(
        "repos/{owner}/{repo}/issues?state=all&sort=created&direction=desc&per_page=50"
    )
    for i in issues or []:
        if i.get("title") == subject and "pull_request" not in i:
            return i["number"]
    raise RuntimeError(f"no issue found with title {subject!r}")


def poll(subject: str, sent_at: datetime, timeout: int = 7200) -> str | None:
    """
    Poll the issue's comments for a reply created at/after sent_at.
    Returns the latest such reply body, or None if the timeout (seconds) expires.
    """
    number = _find_issue_number(subject)
    # The issue is freshly created, so any comment is a reply; the small
    # negative buffer just absorbs clock skew vs GitHub's second-resolution times.
    cutoff = sent_at.timestamp() - 5
    deadline = time.time() + timeout
    interval = min(300, max(30, timeout // 24))

    while True:
        try:
            comments = _gh_api(
                f"repos/{{owner}}/{{repo}}/issues/{number}/comments?per_page=100"
            )
            replies = [
                c for c in (comments or [])
                if _parse_gh_time(c["created_at"]).timestamp() >= cutoff
            ]
            if replies:
                replies.sort(key=lambda c: c["created_at"])
                return (replies[-1].get("body") or "").strip()
        except Exception as e:
            print(f"[notify] github poll error: {e}", file=sys.stderr)

        if time.time() >= deadline:
            return None
        time.sleep(interval)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None

    if cmd == "send":
        subject, body = sys.argv[2], sys.argv[3]
        print(send(subject, body).isoformat())

    elif cmd == "poll":
        subject = sys.argv[2]
        sent_at = datetime.fromisoformat(sys.argv[3])
        timeout = int(sys.argv[4]) if len(sys.argv) > 4 else 7200
        reply = poll(subject, sent_at, timeout)
        if reply is None:
            sys.exit(1)
        print(reply)

    else:
        print(__doc__)
        sys.exit(1)
