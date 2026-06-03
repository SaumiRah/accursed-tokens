Here's the prospectus for my project: Accursed Tokens

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