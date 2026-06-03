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

