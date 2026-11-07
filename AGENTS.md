# AGENTS.md

see `docs/project-info.md` for projekt details

Working Project Folder: /opt/Investalo_Trading-Platform

## Project state and navigation

- Current phase: local M1 implementation, approved in Q31.
- Confirmed Q1–Q5: private invitation pilot, cockpit/backtests/paper before live,
  independent hard risk limits, controlled AI promotion, and free external
  tools/accounts first. TradingView Essentials is the existing paid subscription.
  Do not book additional paid services without a new concrete decision.
- Confirmed Q6–Q8: plan both Bitget and MT5 for the first release; modular
  monolith with separate workers, Python/FastAPI, Next.js/TypeScript and PostgreSQL;
  separate cockpit login with MFA.
- Confirmed Q9–Q14: BTC/USDT and ETH/USDT spot without leverage on H4;
  XAUUSD trend/pullback with H1 regime and M15 entries after validation;
  written crypto prompt over older images; 25% growing quote amounts, 5% drop
  from the last actual entry, -50% stress from the first entry; Docker Compose
  from the start; local Authelia OIDC/MFA with administratively provisioned users.
  Do not infer approval for systemd deployment.
- Confirmed Q15–Q22: RSI14/Wilder closed-H4 signals; Supertrend ATR10/Wilder ×3
  protection with net-breakeven floor and no further buys; crypto paper 10,000 USDT,
  each basket 500 principal +5 costs, 6% daily/8% initial loss and -55% first-fill
  exit; independent MT5 broker demo, 0.25% idea risk, one idea, 1% daily/5% initial loss.
  The sixth tranche is a reserved manual entry as clarified by Q23.
  Plan a public central HTTPS entry for the invitation-only pilot and existing free
  SMTP. Public rollout still needs approval.
- Confirmed Q23–Q28: keep the buffer exclusively for a manual entry and inform
  the user; no automatic -40% trigger. Administrative MFA reset after email
  confirmation; MT5 is on a separate home-network server, using an outbound
  authenticated HTTPS bridge. Research targets: 3 years crypto/2 years gold,
  positive independent net holdout, PF >=1.2 and 30 baskets per crypto asset/
  100 gold trades in holdout. Pilot backup targets RPO 24h/RTO 4h with encrypted
  external and protected offline copies. M1 scope is confirmed; actual AI,
  full news/calendar feeds, live/FTMO/customer decisions follow later gates.
  Q29–Q30 confirmed: buffer after five regular stages, one manually confirmed
  entry, no RSI required but price <=95% last regular fill; preview/MFA and all
  risk/protection gates. Once-only cockpit notice plus optional user-enabled email.
  Do not simulate hindsight-selected manual fills as automated performance.
- M1 substantive interview decisions Q1–Q30 and Q31 final shared understanding
  are confirmed. The user explicitly instructed implementation to begin.
  Reviewable summary: `docs/implementation-brief.md`.
- Original requirements: `docs/project-info.md`; complete draft: `docs/concept.md`.
- Architecture/stack proposals: `docs/architecture.md`; trading: `docs/trading.md`.
- Track work in `docs/tasks/board.md`, milestones in `docs/roadmap.md`,
  deferred work in `docs/backlog.md`, and user decisions in `docs/interview.md`.
- Read `docs/memories/decision-log.md` and `docs/memories/gotchas.md` before
  implementation; consult `docs/inventory.md` before reusing legacy code.
- Preserve the original project prompt. Label unresolved requirements and
  proposed defaults explicitly; an unanswered interview question is not approval.
- Local bootstrap and M1 implementation are authorized. Keep live trading and
  public/production rollout behind their separate approvals.
- The user explicitly authorized autonomous local commands and asks for concrete
  interim acceptance notices. Continue routine local implementation without
  repeating permission questions; tool sandbox escalations still apply.
- The user explicitly authorized intermediate commits and GitHub pushes.
  Push reviewed feature checkpoints with the existing repository deploy identity;
  this does not authorize production deployment, history rewrite or force-push.
- Current foundation: `infra/README.md` starts the five loopback-only services;
  executable tests cover API/RLS, cockpit security and the deterministic crypto
  core. Queued backtests still lack their execution/data worker. Do not call this
  a released M1 pilot. Generated `infra/local/` is ignored and never a build context.
- Existing reference repositories: `/opt/investalo-trading-system` and
  `/opt/investalo-autotrader`. Treat them as read-only references unless work there
  is explicitly authorized. Their strategies need independent net-cost validation.

## Trading and implementation invariants

- Profitability is a measurable research objective, never a guarantee.
- Use one versioned deterministic strategy core for backtest, paper, and live.
- Risk limits are enforced independently of strategy/AI and before order dispatch.
- Model quote budget, position notional, usable margin, and account equity separately.
- Never retry an uncertain broker order blindly; reconcile before resubmission.
- Require authenticated tenant context for requests, jobs, files, caches, and streams.
- Broker credentials must never reach browser storage, research workers, AI, or logs.
- Default to a private user base and disabled live execution. Q20 permits planning
  a public central HTTPS pilot entry; databases/workers stay internal. Real-money activation
  requires explicit account/strategy/risk approval in addition to deployment approval.
- Never inherit loose dependency ranges or floating images from the legacy systems.
  Verify supported versions, pin exact releases/digests, and commit lockfiles.
- Keep original strategy images in `strategies/`; executable rules belong in a
  reviewed specification and immutable strategy versions.
- `secrets/` is ignored. Removing a file from tracking does not remove its history;
  potential credentials need rotation and separately authorized history remediation.

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
- work with git and save your work. you can also push your feature branches and main branch to github.com by yourself.

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


## CODEX USE
- If you need to use other Codex CLI Modells you must start codex with the AWS Bedrock Modell: example for GPT-Astra = codex --model global.openai.gpt-6-astra
