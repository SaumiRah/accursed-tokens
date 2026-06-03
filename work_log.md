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



