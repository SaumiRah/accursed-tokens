# Accursed Tokens

A weekly scheduled automation that exhausts your remaining Claude Pro token allowance before it resets — so you actually get your money's worth.

Every Tuesday at 12:30 PM, it wakes up, checks how many tokens you have left, texts you a proposed plan, waits up to 2 hours for your input, then gets to work. No laptop required.

---

## How it works

1. **Activates** 13 hours before the weekly token reset (Tuesday 12:30 PM)
2. **Assesses** remaining token budget via `/usage`
3. **Picks a project** from [`project_agenda.md`](project_agenda.md), falling back to [`desires.md`](desires.md) if the agenda is empty
4. **Texts you** a proposed plan via SMS — reply within 2 hours to redirect it, or let it decide
5. **Does the work** autonomously across as many sessions as needed until usage hits ~95%
6. **Texts you a digest** of what it accomplished

All execution happens server-side via Claude Code's scheduled remote agent infrastructure. Projects are worked on via GitHub so nothing needs to be running locally.

---

## Setup

### Prerequisites
- Claude Pro subscription
- Twilio account (for SMS notifications)
- GitHub account (for remote project access)

### One-time setup (on your laptop)

**1. Clone and push to GitHub**
```bash
git clone https://github.com/SaumiRah/accursed-tokens
```

**2. Configure `config.toml`**

Edit the timezone if needed (default: `America/Toronto`). Everything else stays as-is.

**3. Set environment variables in the Claude Code harness**

```
TWILIO_ACCOUNT_SID      your Twilio account SID
TWILIO_AUTH_TOKEN       your Twilio auth token
TWILIO_FROM_NUMBER      your Twilio phone number  (E.164: +16135550123)
USER_PHONE_NUMBER       your personal phone number (E.164: +16135550123)
```

**4. Fill in your projects and goals**

- [`project_agenda.md`](project_agenda.md) — concrete projects with repos, priorities, and goals
- [`desires.md`](desires.md) — high-level goals used as fallback when the agenda is empty

**5. Run calibration**

Measures your actual 5-hour and weekly token limits empirically (Anthropic doesn't publish them):

```bash
pip install twilio
python calibrate.py
```

Commit the resulting `calibration_result.json`.

**6. Register the cron job**

Use the `schedule` skill in Claude Code to register a weekly remote agent with cron expression `30 12 * * TUE`.

---

## Files

| File | Purpose |
|---|---|
| `project_agenda.md` | Your project list — edit freely |
| `desires.md` | High-level goals — fallback when agenda is empty |
| `work_log.md` | Append-only log of every session |
| `config.toml` | Schedule and notification config (safe to commit) |
| `calibrate.py` | One-time script to measure your token limits |
| `calibration_result.json` | Output of calibrate.py — commit this |
| `project_plan.md` | Full technical specification |

---

## Project Agenda

See [`project_agenda.md`](project_agenda.md) to view or add projects. Each entry has a priority, token appetite, and status. Claude updates status and adds session notes automatically.