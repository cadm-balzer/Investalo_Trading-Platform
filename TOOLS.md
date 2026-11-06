# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff unique to your setup.

## What Goes Here

Things like:

- SSH hosts and aliases
- API endpoints specific to this deployment
- Anything environment-specific
- bash commands
- service commands

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes.

---

_Add whatever helps you do your job. This is your cheat sheet._

## Investalo — verified 2026-11-06

- Working checkout: `/opt/Investalo_Trading-Platform`.
- Planning branch: `docs/project-foundation`; local Git saves, no production deployment.
- Read-only references: `/opt/investalo-trading-system`,
  `/opt/investalo-autotrader`. HEADs and reuse limits: `docs/inventory.md`.
- Host: Ubuntu 26.04.1 LTS, 2 vCPU, 1.9 GiB RAM, no swap.
- Present tools: Python 3.14.4, Node 26.13.0, Git 2.53.0,
  Codex 0.167.0, Gemini 0.67.0. Docker/gh not found in PATH.
- Local interview skill: `SKILLS/grill-me/SKILL.md`.
- Local admin skill targets Ubuntu 24.04; validate against 26.04 before use.
- User domain: `cockpit.investalo.de`; no DNS, ingress or production changes made.
- Planning tasks: `docs/tasks/board.md`; documentation index: `docs/README.md`.
- Never store access keys, passwords or tokens in these notes.
- Deployment decision 2026-11-07: Docker Compose plus local Authelia OIDC/MFA.
  Nothing installed yet. Q20 plans a public central HTTPS entry for invited pilot
  users; Q21 selects existing free SMTP; Q24 selects administrative email recovery.
  Q25 user-provided fact: MT5 runs on a separate server in the home network.
  Its OS/build, demo instance and actual history extent are not remotely verified.
  Plan outbound HTTPS; no home-network ingress or router port forwarding.
- `.git` is read-protected by the workspace sandbox; Git mutations may need
  tool escalation even when editing project files is allowed.
