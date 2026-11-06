# AGENTS.md

see `docs/project-info.md` for projekt details

## Subagents
- wenn du deine Arbeit an spezialisten abgeben kannst, spawne Subagents mit einem für die Aufgabe passenden Modell
- dir steht zusätzlich die GEMINI CLI auf dem System zur Verfügung

## Boundaries

Always do

- Keep security defaults: private deployment, encryption, and least privilege.
- Use exact version pins
- Keep docs concise and update them when architecture or process changes.
- Keep all general documentation up to date including all AGENTS.md files
- Document significant design decisions in `docs/memories/decision-log.md` and
  technical pitfalls in `docs/memories/gotchas.md` — both are committed to Git so
  colleagues (not just the current agent session) benefit from them.
- Add deferred follow-ups to `docs/backlog.md` and remove items once done.
- Follow best practice. If a requirement goes against best practice, point this out. Consult official documentation to verify best practice.
- use SKILLS to get more specialist skills, if you need more SKILLs get the right one from https://www.skills.sh/

Ask first

- Change key structures and strategy.
- Introduce new CI/CD tooling dependencies.
- Execute external-facing actions outside this repository (publishing, posting, messaging).
- before deploying to production ask for approval

Never do

- Never commit hardcoded secrets, access keys, or tokens.
- Do not expose resources directly to the public without a central entry point.
- Do not expose sensible resources such as databases to the public internet.
- Do not run destructive commands without explicit user approval.
- Don't exfiltrate private data. Ever.
- Don't run destructive commands without asking.
- `trash` > `rm` (recoverable beats gone forever)
- When in doubt, ask.

## Memory

You wake up fresh each session. These files are your continuity:

- **Daily notes:** `memory/YYYY-MM-DD.md` (create `memory/` if needed) — raw logs of what happened
- **Long-term:** `MEMORY.md` — your curated memories, like a human's long-term memory

Capture what matters. Decisions, context, things to remember. Skip the secrets unless asked to keep them.

### 🧠 MEMORY.md - Your Long-Term Memory

- **ONLY load in main session** (direct chats with your human)
- **DO NOT load in shared contexts** (Discord, group chats, sessions with other people)
- This is for **security** — contains personal context that shouldn't leak to strangers
- You can **read, edit, and update** MEMORY.md freely in main sessions
- Write significant events, thoughts, decisions, opinions, lessons learned
- This is your curated memory — the distilled essence, not raw logs
- Over time, review your daily files and update MEMORY.md with what's worth keeping


### 📝 Write It Down - No "Mental Notes"!

- **Memory is limited** — if you want to remember something, WRITE IT TO A FILE
- "Mental notes" don't survive session restarts. Files do.
- When someone says "remember this" → update `memory/YYYY-MM-DD.md` or relevant file
- When you learn a lesson → update AGENTS.md, TOOLS.md, or the relevant skill
- When you make a mistake → document it so future-you doesn't repeat it
- **Text > Brain** 📝


## Tools

Skills provide your tools. When you need one, check its `SKILL.md`. Keep local notes (SSH details, commands, jobs, etc.) in `TOOLS.md`.

