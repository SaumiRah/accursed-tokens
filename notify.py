"""
Two-way notifications for Accursed Tokens via GitHub Issues (over the `gh` CLI).

Why GitHub: the remote orchestrator environment blocks raw TCP (SMTP/IMAP),
and ntfy.sh denylists its cloud IP — but GitHub works there (the agent already
clones and pushes over it). So notifications ride on GitHub Issues:

  send(subject, body) -> opens an issue (you get a GitHub mobile push)
  poll(...)           -> polls that issue's comments for your reply

Reply by commenting on the issue (e.g. "42%") from the GitHub app or web.

Identity (why a GitHub App): GitHub suppresses notifications for your *own*
activity, so an issue authored by your account never pushes to your phone — even
if it @-mentions and assigns you. The fix is to author the issue as a *different*
identity. This module does that via a GitHub App: it signs a short-lived JWT
with the App's private key, exchanges it for a 1-hour installation token, and
opens the issue as `your-app[bot]`. That bot then assigns/@-mentions you, which
GitHub *does* push because the actor (the bot) differs from the recipient (you).

App configuration (env vars; if ACCURSED_TOKENS_NOTIFY_GITHUB_APP_ID is unset, falls back to the
ambient `gh` identity, which won't notify you but keeps the CLI working):
  ACCURSED_TOKENS_NOTIFY_GITHUB_APP_ID                  - the App's numeric ID (required to enable App mode)
  ACCURSED_TOKENS_NOTIFY_GITHUB_APP_PRIVATE_KEY         - the App private key PEM contents, OR
  ACCURSED_TOKENS_NOTIFY_GITHUB_APP_PRIVATE_KEY_PATH    - path to the App private key .pem file
  ACCURSED_TOKENS_NOTIFY_GITHUB_APP_INSTALLATION_ID     - optional; auto-discovered from the repo if unset

Either way the actual Issues API calls go through `gh` (it substitutes
{owner}/{repo} from cwd); App mode just hands `gh` the minted installation
token via GH_TOKEN. Run from within the accursed-tokens checkout.

Usage (CLI):
  python notify.py send  "<subject>" "<body>"
  python notify.py poll  "<subject>" "<sent_utc_iso>" [timeout_seconds]
  python notify.py close "<subject-or-number>" ["<closing comment>"]

poll exits 0 with the reply body, or exits 1 on timeout. close closes the issue
(by title or number), optionally leaving a final comment, so resolved plan/digest
issues don't accumulate.
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Within one orchestrator run, send() records the issue number here so poll()
# can find it without a title search. Kept in tmp so it never lands in the repo.
_STATE_FILE = Path(tempfile.gettempdir()) / "accursed_notify_issue.json"

# GitHub user to @-mention and assign on each issue so they get a notification.
# This only pings you when the issue is authored by a *different* identity than
# you — which App mode (below) ensures by authoring as the App's bot account.
MENTION = os.environ.get("NOTIFY_MENTION", "SaumiRah")

_API_ROOT = "https://api.github.com"
# Cached installation token: {"token": str, "expires": epoch_seconds}. Minting
# costs two API round-trips, so we reuse the 1-hour token within a run.
_INSTALL_TOKEN = {"token": None, "expires": 0.0}


def _app_mode() -> bool:
    """True if GitHub App credentials are configured (else fall back to gh auth)."""
    return bool(os.environ.get("ACCURSED_TOKENS_NOTIFY_GITHUB_APP_ID"))


def _private_key_pem() -> bytes:
    """Load the App private key from env: inline PEM (ACCURSED_TOKENS_NOTIFY_GITHUB_APP_PRIVATE_KEY,
    used for the remote run via the harness env block) or a local file path
    (ACCURSED_TOKENS_NOTIFY_GITHUB_APP_PRIVATE_KEY_PATH, used for local dev)."""
    pem = os.environ.get("ACCURSED_TOKENS_NOTIFY_GITHUB_APP_PRIVATE_KEY")
    if pem:
        # When the PEM is stored as a JSON string its newlines may survive as the
        # literal two-character sequence "\n"; restore real newlines so it parses.
        if "\\n" in pem and "\n" not in pem:
            pem = pem.replace("\\n", "\n")
        return pem.encode()
    path = os.environ.get("ACCURSED_TOKENS_NOTIFY_GITHUB_APP_PRIVATE_KEY_PATH")
    if path:
        return Path(path).expanduser().read_bytes()
    raise RuntimeError(
        "App mode needs ACCURSED_TOKENS_NOTIFY_GITHUB_APP_PRIVATE_KEY or ACCURSED_TOKENS_NOTIFY_GITHUB_APP_PRIVATE_KEY_PATH"
    )


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _sign_rs256(message: bytes, key_pem: bytes) -> bytes:
    """RS256-sign `message`. Prefer `cryptography`; fall back to the openssl CLI."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        key = serialization.load_pem_private_key(key_pem, password=None)
        return key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    except ImportError:
        with tempfile.NamedTemporaryFile("wb", suffix=".pem", delete=False) as kf:
            kf.write(key_pem)
            key_path = kf.name
        try:
            res = subprocess.run(
                ["openssl", "dgst", "-sha256", "-sign", key_path],
                input=message, capture_output=True,
            )
            if res.returncode != 0:
                raise RuntimeError(f"openssl signing failed: {res.stderr.decode().strip()}")
            return res.stdout
        finally:
            os.unlink(key_path)


def _app_jwt() -> str:
    """Build a short-lived JWT that authenticates as the App itself."""
    app_id = os.environ["ACCURSED_TOKENS_NOTIFY_GITHUB_APP_ID"]
    now = int(time.time())
    # iat backdated 60s for clock skew; exp within GitHub's 10-minute ceiling.
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {"iat": now - 60, "exp": now + 540, "iss": app_id}
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64url(json.dumps(payload, separators=(",", ":")).encode())
    )
    sig = _sign_rs256(signing_input.encode(), _private_key_pem())
    return signing_input + "." + _b64url(sig)


def _http_json(url, method="GET", token=None, bearer=None):
    """Minimal GitHub REST call via urllib (used only for App auth round-trips)."""
    req = urllib.request.Request(url, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "accursed-tokens-notify")
    if bearer:
        req.add_header("Authorization", f"Bearer {bearer}")
    elif token:
        req.add_header("Authorization", f"token {token}")
    try:
        with urllib.request.urlopen(req) as r:
            out = r.read().decode()
            return json.loads(out) if out else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode().strip()
        raise RuntimeError(f"{method} {url} -> {e.code}: {detail}") from None


def _repo_slug() -> str:
    """Derive owner/repo from the origin remote (for installation discovery)."""
    res = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        capture_output=True, text=True,
    )
    url = res.stdout.strip()
    # Handle git@github.com:owner/repo.git and https://github.com/owner/repo.git
    slug = url.split("github.com")[-1].lstrip(":/").removesuffix(".git")
    if slug.count("/") != 1:
        raise RuntimeError(f"could not parse owner/repo from remote url {url!r}")
    return slug


def _installation_token() -> str:
    """Mint (and cache) a 1-hour installation token from the App credentials."""
    now = time.time()
    if _INSTALL_TOKEN["token"] and now < _INSTALL_TOKEN["expires"] - 300:
        return _INSTALL_TOKEN["token"]

    jwt = _app_jwt()
    inst_id = os.environ.get("ACCURSED_TOKENS_NOTIFY_GITHUB_APP_INSTALLATION_ID")
    if not inst_id:
        # Discover the installation on this repo using the App JWT.
        inst = _http_json(
            f"{_API_ROOT}/repos/{_repo_slug()}/installation", bearer=jwt
        )
        inst_id = str(inst["id"])

    tok = _http_json(
        f"{_API_ROOT}/app/installations/{inst_id}/access_tokens",
        method="POST", bearer=jwt,
    )
    _INSTALL_TOKEN["token"] = tok["token"]
    _INSTALL_TOKEN["expires"] = _parse_gh_time(tok["expires_at"]).timestamp()
    return tok["token"]


def _gh_api(path, method="GET", fields=None):
    """Call `gh api`; gh substitutes {owner}/{repo} from cwd. In App mode, hand
    gh the minted installation token via GH_TOKEN so issues are authored by the
    App's bot (which is what lets GitHub notify you); otherwise use ambient auth."""
    cmd = ["gh", "api", "-X", method, path]
    for k, v in (fields or {}).items():
        cmd += ["-f", f"{k}={v}"]
    env = None
    if _app_mode():
        env = {**os.environ, "GH_TOKEN": _installation_token()}
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
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


def close(subject_or_number, comment: str | None = None) -> int:
    """Close an issue (by title or issue number), optionally leaving a final
    comment first. Lets the orchestrator tidy up resolved plan/digest issues so
    they don't pile up week over week. Returns the closed issue number."""
    s = str(subject_or_number)
    number = int(s) if s.isdigit() else _find_issue_number(s)
    if comment:
        _gh_api(f"repos/{{owner}}/{{repo}}/issues/{number}/comments", "POST",
                {"body": comment})
    _gh_api(f"repos/{{owner}}/{{repo}}/issues/{number}", "PATCH", {"state": "closed"})
    return number


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
        target = sys.argv[2]  # issue title or number
        comment = sys.argv[3] if len(sys.argv) > 3 else None
        print(close(target, comment))

    else:
        print(__doc__)
        sys.exit(1)
