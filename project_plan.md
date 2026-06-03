# Accursed Tokens — Project Plan

## Overview

Accursed Tokens is a weekly scheduled automation that runs entirely server-side via Claude Code's remote agent infrastructure. It activates every Tuesday at 12:00 PM — 18 hours before the Wednesday 06:00 AM weekly token reset — assesses remaining token budget, notifies the user via SMS, waits up to 2 hours for direction, then autonomously works through a curated project agenda until the weekly token allowance is exhausted. No laptop required at runtime; all project work targets GitHub-hosted repos so the remote agent can clone, commit, and push without local filesystem access.

---

## System Architecture

### Remote-first design

The system runs entirely server-side via CronCreate. The user needs a laptop only once for the initial setup. Thereafter, everything — scheduling, email notification, project work, and digest — happens remotely.

```
[CronCreate job — server-side]
     │  fires Tuesday 12:00 PM (18h before Wednesday 06:00 AM reset)
     ▼
[Remote Agent — Claude Code harness]
     │
     ├─► read project_agenda.md (from GitHub) → pick project(s)
     │       └─► fallback: desires.md
     │
     ├─► Gmail: "Plan: [project]. Reply with /usage % to pace work. 2h to redirect."
     │
     ├─► Poll sender Gmail inbox (IMAP) every 5 min for 120 min
     │       └─► if reply → parse /usage %, redirect instructions, or "stop"
     │
     ├─► Clone target project repo → do work → commit + push → open PR if appropriate
     │       └─► repeat in new sessions until /usage ≥ 95%
     │
     └─► Gmail digest + update work_log.md + push to this repo
```

The remote agent is Claude Code itself — no Python runtime needed at execution time. Helper scripts (`calibrate.py`, `notify.py`) run once on the laptop during setup; `notify.py` is also called by the orchestrator at runtime.

---

## File Inventory

| File | Role |
|------|------|
| `project_plan.md` | This document — living specification |
| `project_agenda.md` | User/Claude-editable project list (committed to GitHub) |
| `desires.md` | High-level user goals — fallback when agenda is empty |
| `calibrate.py` | One-time laptop script: measures real 5h + weekly token limits |
| `calibration_result.json` | Output of calibrate.py — committed so remote agent can read it |
| `calibration_log.json` | Per-session pct_before/pct_after history for ongoing refinement |
| `work_log.md` | Append-only log of every session's output |
| `config.toml` | Cron schedule, stop threshold — committed, no secrets |
| `notify.py` | Gmail send + IMAP poll helpers used by the orchestrator |
| `.env` | Gmail secrets — NEVER committed; set as harness environment variables |

---

## Setup Guide (one-time, on laptop)

After setup, no laptop is required for any weekly run.

1. **Gmail accounts**: Create a dedicated sender Gmail account (e.g. `saumspam@gmail.com`) and generate app passwords for both the sender and your personal account. Add as environment variables in the Claude Code harness settings (not stored in files).

2. **GitHub repo**: Push this project to GitHub so the remote agent can access it.

3. **config.toml**: Edit and commit with your phone number and timezone.

4. **project_agenda.md**: Add your initial projects and commit.

5. **desires.md**: Write your high-level goals and commit.

6. **Calibration**: Run `python calibrate.py` on your laptop. This measures your real 5-hour and weekly token limits by consuming tokens and watching `/usage` change. Commit the resulting `calibration_result.json`.

7. **Register cron**: Use the `schedule` skill or CronCreate to register the weekly cron job:
   - **Expression**: `30 12 * * TUE`
   - **Timezone**: as set in `config.toml`
   - **Action**: trigger the orchestrator remote agent

---

## Data File Specs

### project_agenda.md

```markdown
## Active Projects

### [Project Title]
- **Repo**: https://github.com/username/repo (or "N/A" for non-code work)
- **Description**: What this project is about
- **Goal**: What "done" looks like for a session
- **Priority**: high / medium / low
- **Token appetite**: small (<50k) / medium (50k–200k) / large (200k+)
- **Status**: not started / in progress / paused / done

---
```

Claude updates `Status` and appends session notes. The user adds, edits, or removes projects freely.

### desires.md

```markdown
## Goals

- I want to build passive income streams
- I want to get fit this summer
- I want to understand what I actually want from life
```

Desires are intentionally vague. Claude synthesizes a concrete project from them when the agenda is empty or all projects are done.

---

## Orchestrator Logic

The remote agent follows this sequence each Tuesday:

### 1. ASSESS
- Run `/usage` and parse the weekly percentage used
- Load `calibration_result.json` to get `limit_weekly` and `limit_5h`
- Compute `tokens_remaining ≈ (1 - pct_used/100) × limit_weekly`
- Compute `sessions_estimated = ceil(tokens_remaining / limit_5h)`

### 2. SELECT
- Read `project_agenda.md`, filter out `status: done`
- Sort by priority (high → low), then token appetite fit to session budget
- If agenda is empty or all done → read `desires.md` → synthesize a concrete project
- Record selected project

### 3. NOTIFY
```
Accursed Tokens activated.
Plan: {project_name} — {short_description}.

Reply to this email within 2h to:
- Give your current /usage % (e.g. "42%") so I can pace the work
- Redirect to a different project
- "stop" to cancel this week
Or ignore this to let me run until I run out of tokens.
```
Send via `python notify.py send` using the sender Gmail account.

### 4. WAIT
- Poll sender Gmail inbox (IMAP) every 5 minutes for up to 120 minutes via `python notify.py poll`
- Parse reply for: usage % → compute token budget; redirect → update selected project; "stop" → cancel
- If no reply after 120 minutes → proceed with no token budget constraint

### 5. EXECUTE
- Clone or access the target project repo (via GitHub)
- Do the work — Claude uses judgment on what type of output fits the project (see Work Execution Model)
- Commit and push changes; open a PR if appropriate
- Append a `## YYYY-MM-DD` session block to `work_log.md` and push
- Update project status in `project_agenda.md` and push
- Re-check `/usage`; if < 95%, schedule or begin next session
- Stop when `/usage` ≥ 95%

### 6. DIGEST
```
Accursed Tokens — done.
Projects: {project_a} ✓, {project_b} (partial)
See work_log.md on GitHub for details.
```
Send via `python notify.py send`. Append digest to `work_log.md` and push.

---

## Token Budget Algorithm

`/usage` shows a percentage only — Anthropic does not publish absolute weekly limits. The system uses a **self-calibrating, percentage-based** approach.

### Calibration (one-time, laptop)

`calibrate.py` runs `claude --output-format json -p "<prompt>"` in a loop, accumulates token counts from each response's `usage.input_tokens + usage.output_tokens`, and monitors `/usage` after each call.

- When `pct_5h` rises by ≥ 1% → `limit_5h = tokens_accumulated × 100`
- When `pct_weekly` rises by ≥ 1% → `limit_weekly = tokens_accumulated × 100`

This uses Claude Code (subscription tokens), not the Anthropic API.

`calibration_result.json`:
```json
{
  "measured_on": "2026-06-02",
  "limit_5h": 450000,
  "limit_weekly": 4200000,
  "pct_weekly_at_calibration": 14.3
}
```

### Ongoing refinement

After each session, append to `calibration_log.json`:
```json
[
  {"date": "2026-06-03", "pct_before": 12.0, "pct_after": 27.5, "project": "my_project"},
  ...
]
```

Average `pct_after - pct_before` across entries to refine session cost estimates over time.

### Stop condition

Never schedule a new session when `/usage` ≥ `stop_at_pct` (default: 95.0). This leaves a safety margin to avoid a mid-session cutoff at the reset boundary.

---

## Notification Protocol

All email sending and reply polling is handled by `notify.py` using Python's built-in `smtplib` and `imaplib` — no third-party packages needed.

**Send email:**
```bash
sent_at=$(python notify.py send "subject" "body")
```

**Poll for reply:**
```bash
reply=$(python notify.py poll "subject" "$sent_at" 7200)
# exits 0 with reply body, or exits 1 on timeout
```

**Environment variables** (set in harness, never in committed files):
- `SENDER_EMAIL` — Gmail address that sends notifications (e.g. `saumspam@gmail.com`)
- `SENDER_APP_PASSWORD` — app password for the sender account
- `RECIPIENT_EMAIL` — your personal Gmail address that receives notifications

---

## Work Execution Model

Claude uses judgment to match output type to the project:

| Project type | Output |
|---|---|
| Code project (has repo) | Write code, commit, push, open PR |
| Research / learning | Write markdown findings in this repo's `outputs/` dir |
| Planning / design | Create spec or decision document |
| Desires-derived | Produce a tangible artifact (workout plan, income ideas doc, etc.) |

All outputs are pushed to GitHub so the user can review them from any device.

---

## Scheduling

- **Weekly reset**: Wednesday ~06:00 AM (confirmed from `/usage`)
- **Cron fires**: Tuesday 12:00 PM — 18 hours before reset
- **Cron expression**: `0 12 * * TUE`
- **Timezone**: configured in `config.toml`
- **Reply window**: 2 hours → ~16 hours of work time before reset

---

## Digest Format (SMS)

```
Accursed Tokens — done.
Projects: [Project A] ✓, [Project B] (partial)
Usage: 89% (was 14% at noon)
See work_log.md on GitHub for details.
```

---

## Open Questions / Future Work

- **Dynamic scheduling**: if `pct_used` is very low on Tuesday at noon, automatically push cron start to an earlier hour or day
- **Reply parsing**: NLP intent detection vs. simple keyword matching for user's SMS redirect
- **Multi-project sessions**: interleave smaller projects within a session to granularly fill remaining budget
- **Web UI**: a simple interface for editing `project_agenda.md` instead of raw markdown on GitHub
