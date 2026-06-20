"""
Two-way notifications for Accursed Tokens via Telegram (Bot API over plain HTTPS).

Why Telegram: every earlier mechanism broke on this project's restrictive remote
network policy — Gmail SMTP/IMAP needs raw TCP sockets (blocked), ntfy.sh's cloud
IP got denylisted (403), and GitHub Issues needed a `gh`-authenticated identity
that some remote sessions simply didn't have (403 from the sandbox's egress
proxy on api.github.com/cli.github.com, no ambient `gh auth`). Telegram's Bot
API is a single HTTPS host (api.telegram.org) reachable with nothing but
urllib and a bot token — no CLI, no OAuth dance, and no separate "actor"
identity to fake: a bot message always pushes a notification, so there's no
GitHub-style suppression of "your own" activity to work around.

  send(subject, body) -> sends a Telegram message to your chat (push to phone)
  poll(...)           -> polls getUpdates for your reply in that chat
  close(...)          -> sends a short follow-up message (chats don't have a
                         "closed" state like GitHub issues; this just keeps the
                         orchestrator's existing call sites working unchanged)

Reply by just typing in the chat with the bot (e.g. "42%") from the Telegram
app or web.

IMPORTANT — network egress allowlist: this project's remote execution
environments use allowlist-based egress. `api.telegram.org` must be added to
the environment's network egress settings or every call below fails with
"Host not in allowlist" (403), the same way api.github.com/ntfy.sh did before
they were replaced. Add it under the harness's network/egress configuration
before the first scheduled run.

Setup (one-time, via @BotFather in Telegram):
  1. Message @BotFather -> /newbot -> follow the prompts -> copy the bot token
  2. Message your new bot anything (e.g. "hi") so it can see your chat
  3. Visit https://api.telegram.org/bot<TOKEN>/getUpdates to find your chat id
     (result[0].message.chat.id)
  4. Set env vars in the harness environment:
       ACCURSED_TOKENS_NOTIFY_TELEGRAM_BOT_TOKEN
       ACCURSED_TOKENS_NOTIFY_TELEGRAM_CHAT_ID

Usage (CLI):
  python notify.py send  "<subject>" "<body>"
  python notify.py poll  "<subject>" "<sent_utc_iso>" [timeout_seconds]
  python notify.py close "<subject>" ["<closing comment>"]

poll exits 0 with the reply body, or exits 1 on timeout.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

_API_ROOT = "https://api.telegram.org"
_MAX_MESSAGE_LEN = 4096  # Telegram's hard limit on sendMessage text length


def _bot_token() -> str:
    token = os.environ.get("ACCURSED_TOKENS_NOTIFY_TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "ACCURSED_TOKENS_NOTIFY_TELEGRAM_BOT_TOKEN is not set — create a bot via "
            "@BotFather in Telegram and set its token in the harness environment"
        )
    return token


def _chat_id() -> str:
    chat_id = os.environ.get("ACCURSED_TOKENS_NOTIFY_TELEGRAM_CHAT_ID")
    if not chat_id:
        raise RuntimeError(
            "ACCURSED_TOKENS_NOTIFY_TELEGRAM_CHAT_ID is not set — message your bot once, "
            "then read result[0].message.chat.id from "
            "https://api.telegram.org/bot<TOKEN>/getUpdates"
        )
    return chat_id


def _tg_api(method: str, params: dict | None = None, http_method: str = "POST"):
    """Minimal Telegram Bot API call via urllib (no extra dependencies)."""
    url = f"{_API_ROOT}/bot{_bot_token()}/{method}"
    data = None
    if http_method == "GET":
        if params:
            url += "?" + urllib.parse.urlencode(params)
    elif params:
        data = json.dumps(params).encode()
    req = urllib.request.Request(url, data=data, method=http_method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode().strip()
        raise RuntimeError(f"{http_method} {method} -> {e.code}: {detail}") from None
    if not out.get("ok"):
        raise RuntimeError(f"{method} failed: {out}")
    return out["result"]


def send(subject: str, body: str) -> datetime:
    """Send a Telegram message and return the UTC datetime it was sent."""
    sent_at = datetime.now(timezone.utc)
    text = f"{subject}\n\n{body}" if body else subject
    while text:
        chunk, text = text[:_MAX_MESSAGE_LEN], text[_MAX_MESSAGE_LEN:]
        _tg_api("sendMessage", {"chat_id": _chat_id(), "text": chunk})
    return sent_at


def poll(subject: str, sent_at: datetime, timeout: int = 7200) -> str | None:
    """
    Poll the chat for a reply sent at/after sent_at.
    Returns the latest such reply's text, or None if the timeout (seconds) expires.
    """
    cutoff = sent_at.timestamp() - 5
    deadline = time.time() + timeout
    chat_id = str(_chat_id())
    interval = min(300, max(30, timeout // 24))

    while True:
        try:
            updates = _tg_api(
                "getUpdates",
                {"timeout": 0, "allowed_updates": json.dumps(["message"])},
                http_method="GET",
            )
            replies = [
                u for u in updates
                if str(u.get("message", {}).get("chat", {}).get("id")) == chat_id
                and u["message"].get("date", 0) >= cutoff
                and u["message"].get("text")
            ]
            if replies:
                replies.sort(key=lambda u: u["message"]["date"])
                latest = replies[-1]
                # Ack past this update so future polls don't replay it.
                try:
                    _tg_api(
                        "getUpdates",
                        {"offset": latest["update_id"] + 1, "timeout": 0},
                        http_method="GET",
                    )
                except Exception:
                    pass
                return latest["message"]["text"].strip()
        except Exception as e:
            print(f"[notify] telegram poll error: {e}", file=sys.stderr)

        if time.time() >= deadline:
            return None
        time.sleep(interval)


def close(subject: str, comment: str | None = None) -> None:
    """Send a short follow-up message. Chats have no 'closed' state like GitHub
    issues did, so this just keeps the orchestrator's existing call sites
    (`notify.py close ...` after a plan is acknowledged) working unchanged."""
    if comment:
        _tg_api("sendMessage", {"chat_id": _chat_id(), "text": comment})


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

    elif cmd == "close":
        target = sys.argv[2]
        comment = sys.argv[3] if len(sys.argv) > 3 else None
        close(target, comment)

    else:
        print(__doc__)
        sys.exit(1)
