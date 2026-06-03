"""
Push notifications for Accursed Tokens via ntfy.sh (HTTPS, no auth required).

SETUP (one-time on your phone):
  1. Install the ntfy app (iOS or Android) — or use ntfy.sh in a browser.
  2. Subscribe to your $NTFY_TOPIC to receive orchestrator notifications.
  3. To reply, publish a message to $NTFY_REPLY_TOPIC via the ntfy app or:
       curl -d "42%" https://ntfy.sh/$NTFY_REPLY_TOPIC

Environment variables (set in Claude Code harness settings, never in files):
  NTFY_TOPIC        — topic the orchestrator publishes to (you subscribe here)
  NTFY_REPLY_TOPIC  — topic the orchestrator polls for your replies (you publish here)

Usage (CLI):
  python notify.py send "<subject>" "<body>"
  python notify.py poll "<subject>" "<sent_utc_iso>" [timeout_seconds]

poll exits 0 with the reply body, or exits 1 on timeout.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path


def _load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def send(subject: str, body: str) -> datetime:
    """Publish a push notification to NTFY_TOPIC and return UTC datetime sent."""
    _load_env()
    topic = os.environ["NTFY_TOPIC"]
    reply_topic = os.environ.get("NTFY_REPLY_TOPIC", "")
    reply_hint = (
        f"\n\nTo reply, post to: https://ntfy.sh/{reply_topic}"
        if reply_topic
        else ""
    )

    sent_at = datetime.now(timezone.utc)
    data = (body + reply_hint).encode("utf-8")
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=data,
        headers={
            "Title": subject,
            "Priority": "high",
            "Content-Type": "text/plain; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()

    return sent_at


def poll(subject: str, sent_at: datetime, timeout: int = 7200) -> str | None:
    """
    Poll NTFY_REPLY_TOPIC for a message posted after sent_at.
    Returns the message body on success, or None on timeout.
    """
    _load_env()
    reply_topic = os.environ["NTFY_REPLY_TOPIC"]

    deadline = time.time() + timeout
    since_ts = int(sent_at.timestamp())
    interval = min(300, max(30, timeout // 24))

    while time.time() < deadline:
        try:
            url = f"https://ntfy.sh/{reply_topic}/json?poll=1&since={since_ts}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                for raw in resp:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("event") == "message" and msg.get("message"):
                        return msg["message"]
        except urllib.error.URLError as e:
            print(f"[notify] poll error: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[notify] unexpected error: {e}", file=sys.stderr)

        remaining = deadline - time.time()
        if remaining > 0:
            time.sleep(min(interval, remaining))

    return None


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None

    if cmd == "send":
        subject, body = sys.argv[2], sys.argv[3]
        sent_at = send(subject, body)
        print(sent_at.isoformat())

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
