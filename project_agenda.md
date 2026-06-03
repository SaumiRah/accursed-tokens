# Project Agenda

Projects for Accursed Tokens to work through. Both you and Claude can edit this file.

Edit `Priority` and `Token appetite` to influence which project gets picked each week.
Set `Status: done` when a project is complete — Claude will skip it automatically.

---

<!-- Add your projects below. Copy the template for each one. -->

### [Your Project Title]
- **Repo**: https://github.com/username/repo (or "N/A")
- **Description**: What this project is about
- **Goal**: What "done" looks like for a session
- **Priority**: high / medium / low
- **Token appetite**: small (<50k) / medium (50k–200k) / large (200k+)
- **Status**: not started

---

## Active Projects

### Token Quantization Project
- **Repo**: TBD
- **Description**: something like RTK or Caveman; a Claude Code config that reduces the number of tokens used while using Claude Code.
- **Goal**: A unique method that reliably reduces the number of tokens used for Claude Code sessions, which can be reproduced for others.
- **Priority**: medium
- **Token appetite**: depends on research; likely large
- **Status**: not started

### Stockbird
- **Repo**: TBD
- **Description**: A bot that plays Super Smash Brothers Melee at super human level as Falco. A rival to the bot "Philip" who plays Fox.
- **Goal**: A Melee bot that can reliably win against even high tier players, and can rival Philip.
- **Priority**: medium
- **Token appetite**: Large
- **Status**: not started

### TabPls
- **Repo**: TBD
- **Description**: A machine learning project that transcribes a song into guitar tab for songs with guitars in it. Can try isolating guitar section in the song to get a clearer signal to transcribe.
- **Goal**: A program that can reliably create accurate tablature at a reasonable speed. Ideally have a business model and plans to deploy/monitize it.
- **Priority**: high
- **Token appetite**: medium (50k–200k); mostly needs training time
- **Status**: not started

### Computer, surprise me 
- **Repo**: TBD
- **Description**: 
  - Searches the internet to find events near you (or within a specified radius/location/city) and orders you an Uber to the location without telling you where you're going.
- **Goal**: Works for me, locally; don't want to publish this for others to use (probably a legal nightmare)
- **Priority**: high
- **Token appetite**: small (<50k) to medium (50k–200k)
- **Status**: not started

### Accursed Tokens
- **Repo**: https://github.com/SaumiRah/accursed-tokens
- **Description**:
  - A weekly scheduled event that instructs Claude to expend all remaining weekly tokens before they're refreshed.
  - Getting your money's worth out of your Claude subscription.
  - Determines how many tokens it has left, and determines what it can accomplish with that amount.
  - Pulls possible projects from a list of prospective/ongoing projects `project_agenda.md`. This file is editable by both the user and Claude.
  - If the user runs out of projects to accomplish, fallback to `desires.md`: a semi-static list of high-to-medium-level goals of the user. Example: "I want money", "I want to lose fat and gain muscle this summer", "I want ... to figure out what I want".
  - When the schedule is activated, it sends a notification to your phone where you can decide what you want it to work on, and if it doesn't receive an answer in 2 hours, it decides by itself.
    - I want this to be entirely remote; I don't want to be at my laptop for this.
  - Sends you a digest of it's progress once it's maximized it's token usage
  - Depending on how many tokens you have remaining near the end of the billing week, will have to decide when to start the event. You might have so many weekly tokens remaining that you can't finish them in one 5 hour allowance; you'd need to start with 10 or 15 hours instead.
    - Probably best to just schedule the event to start 20 hours before the weekly cycle resets to assess how many remaining tokens it has; gives the program four 5-hour token allowances to finish it's weekly token allowance.
- **Goal**: A seamless, once a week scheduled event that works for me alone. Once that works; a plan to deploy and monitize it.
- **Priority**: high
- **Token appetite**: small
- **Status**: in progress



