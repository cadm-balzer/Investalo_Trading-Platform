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

## Investalo — verified 2026-11-07

- Working checkout: `/opt/Investalo_Trading-Platform`.
- Implementation branch: `feat/m1-credential-storage`, based on main71e57f1;
  local implementation and authorized checkpoint pushes, no production deployment.
- Read-only references: `/opt/investalo-trading-system`,
  `/opt/investalo-autotrader`. HEADs and reuse limits: `docs/inventory.md`.
- Host: Ubuntu 26.04.1 LTS, 2 vCPU, 1.9 GiB RAM, no swap.
- Present tools: Python 3.14.4, Node 26.13.0, Git 2.53.0,
  Codex 0.167.0, Gemini 0.67.0. Docker 29.9.3 / Compose 5.7.0 installed;
  GitHub CLI not found in PATH. Exact package/image pins: `docs/runtime-pins.md`.
- Local interview skill: `SKILLS/grill-me/SKILL.md`.
- Local admin skill targets Ubuntu 24.04; validate against 26.04 before use.
- User domain: `cockpit.investalo.de`; no DNS, ingress or production changes made.
- Planning tasks: `docs/tasks/board.md`; documentation index: `docs/README.md`.
- Never store access keys, passwords or tokens in these notes.
- Deployment decision 2026-11-07: Docker Compose plus local Authelia OIDC/MFA.
  Five base services: PostgreSQL, Authelia, API, cockpit and Caddy;
  optional `--profile research` adds the tenant-bound offline worker.
  Only `127.0.0.1:8443` is published. Startup/checks: `infra/README.md`.
  Q20 plans a public central HTTPS entry for invited pilot
  users; Q21 selects existing free SMTP; Q24 selects administrative email recovery.
  Q25 user-provided fact: MT5 runs on a separate server in the home network.
  Its OS/build, demo instance and actual history extent are not remotely verified.
  Plan outbound HTTPS; no home-network ingress or router port forwarding.
- `.git` is read-protected by the workspace sandbox; Git mutations may need
  tool escalation even when editing project files is allowed.
- Local credentials/certificates/state are ignored under `infra/local/`.
  Never dump that directory or use it as a whole-container/build mount.
- `bash infra/scripts/compose.sh` keeps the correct project/file/pin context.
  Use `--profile tools run --rm migrate` for checksummed migrations and
  `--profile checks run --rm api-checks` for real PostgreSQL integration tests.
- Builds run serially on this host. Host clock synchronization was checked.
- Research role preparation/binding: `infra/scripts/provision-local-research.py`.
  Public snapshots stage/import via `infra/scripts/stage-research-snapshot.py`.
  Never give the worker migration/API secrets or change its tenant binding during
  tests. Fixtures use the separate research test role.
  Applied migrations001/002 are immutable.003 is applied only in
  `investalo_credentials_checks`, and is also immutable. Ordinary DB remains002.
  Local full HTTPS test requires an imported public BTC snapshot, default
  `infra/local/research-data/btc-research.json`, alternative `--snapshot-file PATH`.
- GitHub intermediate pushes explicitly authorized. Origin:
  `github.com:cadm-balzer/Investalo_Trading-Platform.git`.
  Existing host Deploy-Key `/opt/github-project-ssh-key` is used via
  `git -c 'core.sshCommand=ssh -i /opt/github-project-ssh-key -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes' push -u origin feat/m1-foundation`.
  Never copy the private key into the repository or print its contents.
- Remote main was verified as already containing the historical credential-path
  commit. IP-005 remains open; no history rewrite/force-push was performed.
- Credential fixture preparation: `infra/scripts/provision-local-credentials-tests.py`.
  Testprofile `credential-storage-checks` deliberately mounts migration credentials.
  Three own credential LOGINs only connect to the fixture DB; the administrative
  checkcontainer has broader development DB rights. No broker or KEK secrets.
  `tests/infra/check_credentials_role_drift.py` requires valid bindings from
  preceding PG tests, verifies a permitted baseline and rolls back its test grant.
