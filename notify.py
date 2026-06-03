"""
Email notifications for Accursed Tokens.

Usage (CLI):
  python notify.py send "<subject>" "<body>"
  python notify.py poll "<subject>" "<sent_utc_iso>" [timeout_seconds]

poll exits 0 and prints the reply body if one arrives, exits 1 on timeout.
"""

import email.utils
import imaplib
import os
import smtplib
import sys
import time
from datetime import datetime, timezone
from email.message import EmailMessage
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
    """Send an email and return the UTC datetime it was sent."""
    _load_env()
    sender = os.environ["SENDER_EMAIL"]
    password = os.environ["SENDER_APP_PASSWORD"]
    recipient = os.environ["RECIPIENT_EMAIL"]

    msg = EmailMessage()
    msg["From"] = f"Accursed Tokens <{sender}>"
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    sent_at = datetime.now(timezone.utc)
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(sender, password)
        smtp.send_message(msg)

    return sent_at


def poll(subject: str, sent_at: datetime, timeout: int = 7200) -> str | None:
    """
    Poll the sender's inbox for a reply to subject sent after sent_at.
    Returns the reply body, or None if timeout (seconds) expires.
    """
    _load_env()
    sender = os.environ["SENDER_EMAIL"]
    password = os.environ["SENDER_APP_PASSWORD"]

    deadline = time.time() + timeout
    since = sent_at.strftime("%d-%b-%Y")

    while time.time() < deadline:
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
                imap.login(sender, password)
                imap.select("INBOX")
                _, data = imap.search(None, f'(UNSEEN SUBJECT "Re: {subject}" SINCE {since})')
                for uid in reversed(data[0].split()):
                    _, hdr_data = imap.fetch(uid, "(BODY[HEADER.FIELDS (DATE)])")
                    date_str = hdr_data[0][1].decode(errors="replace").strip().removeprefix("Date:").strip()
                    msg_time = email.utils.parsedate_to_datetime(date_str)
                    if msg_time > sent_at:
                        _, body_data = imap.fetch(uid, "(BODY[TEXT])")
                        return body_data[0][1].decode(errors="replace").strip()
        except Exception as e:
            print(f"[notify] IMAP error: {e}", file=sys.stderr)

        time.sleep(min(30, max(5, timeout // 10)))

    return None


if __name__ == "__main__":
    import json

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
