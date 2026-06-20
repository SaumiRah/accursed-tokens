# Accursed Tokens

A weekly scheduled automation that exhausts your remaining Claude Pro token allowance before it resets — so you actually get your money's worth.

Every Tuesday at 12:00 PM, it wakes up, checks how many tokens you have left, sends you a Telegram message with a proposed plan, waits up to 2 hours for your reply, then gets to work. No laptop required.

---

## How it works

1. **Activates** 18 hours before the weekly token reset (Tuesday 12:00 PM)
2. **Assesses** remaining token budget via `/usage`
3. **Picks a project** from [`project_agenda.md`](project_agenda.md), falling back to [`desires.md`](desires.md) if the agenda is empty
4. **Sends a Telegram message** with a proposed plan — reply within 2 hours to redirect it (or your `/usage %`), or let it decide
5. **Does the work** autonomously across as many sessions as needed until usage hits ~95%
6. **Sends you a digest** of what it accomplished

All execution happens server-side via Claude Code's scheduled remote agent infrastructure. Projects are worked on via GitHub so nothing needs to be running locally.

---

## Setup

### Prerequisites
- Claude Pro subscription
- GitHub account (for remote project access)
- A Telegram account, with a bot created via [@BotFather](https://t.me/BotFather), for notifications
- `api.telegram.org` added to the remote environment's network egress allowlist (see step 3)

### One-time setup (on your laptop)

**1. Clone and push to GitHub**
```bash
git clone https://github.com/SaumiRah/accursed-tokens
```

**2. Configure `config.toml`**

Edit the timezone if needed (default: `America/Toronto`). Everything else stays as-is.

**3. Notifications — set up a Telegram bot**

Notifications use a Telegram bot via the Bot API (plain HTTPS, no extra dependencies).

1. In Telegram, message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the bot token.
2. Message your new bot anything (e.g. "hi") so it knows your chat.
3. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `result[0].message.chat.id` — that's your chat id.
4. Set these env vars in the Claude Code harness environment (Settings → Environment Variables):
   - `ACCURSED_TOKENS_NOTIFY_TELEGRAM_BOT_TOKEN`
   - `ACCURSED_TOKENS_NOTIFY_TELEGRAM_CHAT_ID`
5. **Add `api.telegram.org` to the environment's network egress allowlist.** Remote execution environments here use allowlist-based egress, so without this every notification call fails with `403 Host not in allowlist` — the same issue that previously broke ntfy.sh and GitHub Issues for this project.

The agent sends a message with its plan; you reply in the same chat (e.g. `42%`).

**4. Fill in your projects and goals**

- [`project_agenda.md`](project_agenda.md) — concrete projects with repos, priorities, and goals
- [`desires.md`](desires.md) — high-level goals used as fallback when the agenda is empty

**5. Run calibration**

Measures your actual 5-hour and weekly token limits empirically (Anthropic doesn't publish them):

```bash
python calibrate.py
```

Commit the resulting `calibration_result.json`.

**6. Register the cron job**

Use the `schedule` skill in Claude Code to register a weekly remote agent with cron expression `0 12 * * TUE`.

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