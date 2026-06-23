# Work Log

Append-only log of every Accursed Tokens session. Updated automatically by the remote agent.

---

## 2026-06-03 ABORT

**Session start**: 2026-06-03
**Selected project**: TabPls (high priority, not started)

**Reason for abort**: Twilio SMS delivery failed — HTTP 403 from Twilio API on both `messages.create` and `account.fetch`. The 403 indicates the Twilio credentials provided are either invalid, expired, or the account is suspended/restricted. Per the orchestrator spec, execution cannot proceed without successful SMS delivery.

**Error detail**:
```
twilio.base.exceptions.TwilioRestException: HTTP 403 error: Unable to create record
  Endpoint: POST https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json
  
twilio.base.exceptions.TwilioRestException: HTTP 403 error: Unable to fetch record
  Endpoint: GET https://api.twilio.com/2010-04-01/Accounts/{SID}.json
```

**Action required**: Verify that `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are correct and that the Twilio account is active. A trial Twilio account also requires the destination number (+17786835434) to be added to the Verified Caller IDs list before messages can be sent to it.

---

## 2026-06-03 ABORT (session 2)

**Session start**: 2026-06-03
**Selected project**: TabPls (high priority, not started)

**Reason for abort**: Gmail SMTP delivery failed — the remote execution environment (Claude Code on the web) blocks outbound TCP connections on port 587, so `smtplib.SMTP("smtp.gmail.com", 587)` raises `OSError: [Errno 97] Address family not supported by protocol`. Per the orchestrator spec, execution cannot proceed without successful notification delivery.

**Error detail**:
```
File "/home/user/accursed-tokens/notify.py", line 46, in send
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
OSError: [Errno 97] Address family not supported by protocol
```

**Root cause**: The remote agent container's network policy does not permit raw TCP socket connections to external SMTP servers. This affects both SMTP (port 587) and likely IMAP (port 993) as well, meaning both `notify.py send` and `notify.py poll` will fail in this environment.

**Action required**: The notification step needs to use an outbound-HTTP-based channel instead of raw TCP sockets. Options:
1. **Gmail HTTP API** via OAuth2 (uses HTTPS port 443, which is typically allowed) — requires setting up a Google Cloud project and OAuth credentials.
2. **SendGrid / Mailgun / Resend API** — simple HTTPS POST, free tiers available.
3. **Ntfy.sh or Pushover** — lightweight push notification APIs over HTTPS.
4. **Skip notification entirely** and proceed directly to project work (remove the NOTIFY/WAIT phases from the orchestrator).

The simplest fix is option 4 (proceed without notification) or option 3 (replace notify.py with an HTTPS-based push service). Update `notify.py` to use `urllib.request` with an HTTPS API before the next scheduled run.

---

## 2026-06-09

**Session start**: 2026-06-09
**Selected project**: TabPls (high priority, in progress)
**Triggered by**: User manual trigger (remote agent session)
**Token budget**: not provided (no /usage reply to notification issue)

### Work completed

**Technique detection** (`src/techniques.py` — new):
- Bend (`b`): detected from BasicPitch `pitch_bends` data; peak deviation ≥ 0.4 semitones; `bend_target_fret` computed (e.g. fret 7 bent 2 semitones → target 9)
- Vibrato (`~`): oscillating pitch_bends with ≥3 zero-crossings and peak-to-peak ≥0.3 semitones
- Hammer-on (`h`): ascending consecutive notes on same string, onset gap < 150ms
- Pull-off (`p`): descending consecutive notes on same string, onset gap < 150ms
- Slide-up (`/`): same-string movement ≥4 frets, onset gap < 300ms
- Slide-down (`\`): same, descending

**Tab renderer updated** (`src/tab.py`):
- New `_placement_cell(p)` function builds cell strings with technique notation: `h7`, `7b9`, `7~`, `5/9`, `9\5`
- Slots dict now stores `Placement` objects (not raw fret ints) so technique info carries through
- Column width calculation accounts for technique annotation characters

**Pipeline** (`src/pipeline.py`):
- Added `detect_techniques: bool = True` parameter
- Added `--no-techniques` CLI flag
- Technique annotation runs between fretboard.place() and tab.render()

**GuitarSet evaluation framework** (`tests/test_integration_guitarset.py`):
- `evaluate_transcription()`: note-level P/R/F1 with configurable onset (50ms) and pitch (±1 semitone) tolerances
- `pytest --guitarset /path/to/dataset` runs live evaluation; tests skip gracefully without the dataset
- `--slow` marker for batch evaluation (10 recordings, writes CSV)
- Offline unit tests (TestEvalMetrics): 9 tests for the metric engine, no dataset needed

**Web app scaffold** (`web/`):
- `web/backend/main.py`: FastAPI app with `POST /transcribe` (multipart upload), `GET /health`, `GET /tunings`; CORS, 50MB limit, file type validation
- `web/backend/requirements.txt`: FastAPI + uvicorn
- `web/frontend/`: Next.js 14 App Router, TypeScript, Tailwind CSS
  - `components/UploadForm.tsx`: drag-and-drop upload, tuning/BPM/techniques settings
  - `components/TabDisplay.tsx`: monospace display with Copy and Download buttons
  - `app/page.tsx`: main page with loading spinner, error display, technique notation guide
  - `app/layout.tsx`, `globals.css`: dark GitHub-style theme

**Test results**: 66 passed, 4 skipped (GuitarSet dataset tests — expected), 0 failed

### Next steps

- Download GuitarSet from zenodo.org/record/3371780 → `pytest --guitarset /path`
- Fine-tune BasicPitch on GuitarSet guitar-isolated audio (guitar_hex_cln)
- Deploy: `vercel` for frontend, `modal deploy` for GPU inference backend
- Guitar Pro (.gp5) export

---

## 2026-06-03 (session 3)

**Session start**: 2026-06-03
**Selected project**: TabPls (high priority, not started)
**Triggered by**: User manually

### Infrastructure fixes

**notify.py rewritten** — switched from Gmail SMTP/IMAP (TCP ports 465/993, blocked in
remote environment) to ntfy.sh (HTTPS push, port 443, confirmed reachable).

New mechanism:
- `send()`: POST to `https://ntfy.sh/$NTFY_TOPIC` — user receives push notification on phone
- `poll()`: GET `https://ntfy.sh/$NTFY_REPLY_TOPIC/json?poll=1&since=...` — user replies by
  publishing to the reply topic

**Action required before next automated run:**
1. Install the ntfy app on your phone (iOS/Android) or use ntfy.sh in browser
2. Choose unique topic names (e.g. `accursed-tokens-saumirah-notify` and
   `accursed-tokens-saumirah-reply`)
3. Set `NTFY_TOPIC` and `NTFY_REPLY_TOPIC` as environment variables in Claude Code harness
   settings (Settings → Environment Variables)
4. Subscribe to your `NTFY_TOPIC` in the ntfy app
5. To reply: publish a message to `NTFY_REPLY_TOPIC` via the ntfy app or:
   `curl -d "42%" https://ntfy.sh/YOUR_REPLY_TOPIC`

**config.toml updated** with full setup instructions in the `[notifications]` section.

### TabPls — session output

All output in `outputs/tabpls/`.

**Files created:**
- `DESIGN.md` — full technical design: pipeline architecture, guitar theory constraints,
  fretboard mapping DP algorithm, source separation, AMT (BasicPitch), evaluation metrics,
  datasets (GuitarSet, DadaGP), development roadmap
- `BUSINESS.md` — market analysis, revenue model (Free/Solo $5/Band $12), go-to-market
  strategy, legal notes, production stack, milestones
- `src/audio.py` — audio loading, normalization, Demucs source separation wrapper
- `src/detect.py` — BasicPitch wrapper returning `NoteEvent` objects
- `src/fretboard.py` — Viterbi DP fretboard mapper; handles chords, alternate tunings,
  stretch/shift cost minimization
- `src/tab.py` — ASCII guitar tab renderer (quantized + compact modes)
- `src/pipeline.py` — end-to-end CLI (`tabpls transcribe input.mp3 [--separate] [--bpm N]`)
- `tests/test_fretboard.py` — 21 unit tests for fretboard mapper
- `tests/test_tab.py` — 11 unit tests for tab renderer
- `requirements.txt`

**Test results:** 32/32 passed

**What's left for Phase 2:**
- Download GuitarSet, run integration test on a real recording
- Fine-tune BasicPitch on GuitarSet guitar-isolated audio
- Technique detection (hammer-on, pull-off, bends)
- Web app (FastAPI + Next.js) + GPU inference endpoint (Modal.com)

### Accursed Tokens infrastructure

- `notify.py` rewritten to use ntfy.sh (HTTPS)
- `config.toml` updated with ntfy.sh setup instructions

### Digest

```
Accursed Tokens — done (session 3, 2026-06-03).
Projects: TabPls ✓ (MVP, 32/32 tests), Accursed Tokens notify.py ✓ (fixed)
See outputs/tabpls/ on GitHub for all files.
Action required: set up ntfy.sh before next Tuesday run (see config.toml).
```

---

## 2026-06-16 ABORT

**Session start**: 2026-06-16
**Selected project**: TabPls (high priority, in progress) — selection completed, but execution never started because the NOTIFY preflight failed.

**Reason for abort**: `gh auth status` fails — the remote execution environment for this session has no authenticated GitHub CLI identity, and none of the `ACCURSED_TOKENS_NOTIFY_GITHUB_APP_*` secrets that `notify.py` falls back from are set either. Per the orchestrator spec, execution cannot proceed without a working notification channel.

**Diagnostics:**
- `gh` was not even installed in this container (`command not found`); installing it via `apt-get install -y gh` succeeded (network egress to `archive.ubuntu.com` is allowed), but `gh auth status` then reported `You are not logged into any GitHub hosts.`
- No `GH_TOKEN`, `GITHUB_TOKEN`, `ACCURSED_TOKENS_NOTIFY_GITHUB_APP_ID`, `ACCURSED_TOKENS_NOTIFY_GITHUB_APP_PRIVATE_KEY`, or `ACCURSED_TOKENS_NOTIFY_GITHUB_APP_PRIVATE_KEY_PATH` present in the environment.
- Direct egress to `api.github.com` returns HTTP 403 (Varnish) and to `cli.github.com` returns `403 host_not_allowed` from the sandbox's network proxy — this session's network policy does not appear to permit unauthenticated/direct calls to those hosts.
- This session's git remote is itself proxied through a local helper (`http://local_proxy@127.0.0.1:.../git/...`), which handles push/pull/clone auth transparently but exposes no token usable by `gh` or for generic GitHub REST calls.
- This session's system prompt states explicitly that direct `gh`/GitHub API access is unavailable here and that GitHub interactions should go through a `github` MCP server's tools instead — a different mechanism than what `notify.py` was built against.

**Action required before next automated run:** Either (a) provision the `ACCURSED_TOKENS_NOTIFY_GITHUB_APP_*` secrets (App ID + private key) in the harness environment so `notify.py`'s installation-token path works regardless of ambient `gh` auth, or (b) confirm whether the production cron-triggered runtime actually provides ambient `gh` auth (this interactive/manual session may simply lack it) before assuming `notify.py` is broken outright. If neither holds, `notify.py` will need a rewrite against the `github` MCP server tools (`mcp__github__issue_write`, `mcp__github__add_issue_comment`, etc.) to match what's actually available in this environment.

No project work was performed this session — the notify preflight check blocked execution before SELECT/EXECUTE began.

---

## 2026-06-23 NO REPLY

**Session start**: 2026-06-23 19:04 UTC (Tue 12:04 PM Pacific — on schedule)
**Selected project**: TabPls (high priority, in progress) — GuitarSet download attempt, Guitar Pro (.gp5) export, pipeline/web app hardening per the 2026-06-09 "next steps".

### Infra: notify.py's `gh` path is confirmed broken in this remote/MCP session type; switched to the `github` MCP server tools

This continues the diagnosis from the 2026-06-16 ABORT. This time `gh` could be installed (`apt-get install -y gh` succeeded) and `GH_TOKEN`/`GITHUB_TOKEN` *are* present in the environment and do authenticate — `gh api user` and a raw `curl -H "Authorization: token $GH_TOKEN" https://api.github.com/user` both return 200 as `SaumiRah`. But repo-scoped calls fail:

```
$ gh api repos/SaumiRah/accursed-tokens
{"message":"GitHub access is not enabled for this session. An org admin must
connect the Claude GitHub App for this organization.","documentation_url":
"https://docs.anthropic.com/en/docs/claude-code/github-actions"}
```

That response shape (and `docs.anthropic.com` URL) is the agent proxy intercepting the call, not GitHub itself — confirming part (b) of the 06-16 action item: this session type's network policy blocks `gh`/raw REST for repo operations outright, regardless of token validity. `notify.py` as written cannot work here.

**Resolution this session**: bypassed `notify.py` and called the `github` MCP server tools (`mcp__github__issue_write`, `mcp__github__issue_read`, `mcp__github__add_issue_comment`) directly from the orchestrator agent instead of shelling out. This worked — issue #10 was created successfully.

**New caveat found — likely explains the no-reply below**: `mcp__github__get_me` shows the MCP connection is authenticated as **SaumiRah's own account**, not a separate bot identity:
```json
{"login":"SaumiRah", "id":77644712, ...}
```
This is exactly the failure mode `notify.py`'s docstring warns about: "GitHub suppresses notifications for your own activity, so an issue authored by your account never pushes to your phone — even if it @-mentions and assigns you." Issue #10 (below) was created and self-assigned by `SaumiRah` via this MCP identity, so it may never have generated a mobile push at all, independent of whether the user was available to reply.

**Action required before next run**: Either (a) get the `ACCURSED_TOKENS_NOTIFY_GITHUB_APP_*` secrets provisioned so a true bot identity authors the issue (now actually actionable — `notify.py`'s App-mode code path is unchanged and should still work if those secrets are set, since App auth happens at the JWT/installation-token level, separate from the proxy restriction observed here — though this hasn't been verified in this session type and may hit the same proxy wall), or (b) accept GitHub issues as a "check when convenient" channel rather than a phone-push channel, and have the user proactively check `github.com/SaumiRah/accursed-tokens/issues` on/after Tuesdays, or (c) re-home notify on a channel this session's proxy doesn't intercept (the proxy denylist appears scoped to direct GitHub REST egress, not necessarily other HTTPS APIs — worth re-testing ntfy.sh from *this* session type specifically, since the 06-16 finding that ntfy denylists "the remote cloud IP" may have been from a different network policy/session type than this one).

### NOTIFY

Opened issue [#10](https://github.com/SaumiRah/accursed-tokens/issues/10) "Accursed Tokens - week of Jun 23" at `2026-06-23T19:05:09Z` via the MCP path above. Asked for `/usage` %, offered redirect to another agenda project, or "stop".

### WAIT

Polled `mcp__github__issue_read` (`get_comments`) every 10 minutes for 2 hours (12 checks, 19:05–21:07 UTC). No comment was posted on issue #10 in that window.

### Outcome

Per the orchestrator spec, a WAIT timeout with no reply means: log NO REPLY and stop — no project work performed this run. **TabPls status in `project_agenda.md` is unchanged** (still "in progress", same next-steps as the 2026-06-09 session). Issue #10 left open in case of a late reply.

