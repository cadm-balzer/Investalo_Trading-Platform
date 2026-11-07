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
- Implementation branch: `feat/m1-passkey-action-proof`, based on main `e741c6b`;
  local implementation and authorized checkpoint pushes, no production deployment.
- Read-only references: `/opt/investalo-trading-system`,
  `/opt/investalo-autotrader`. HEADs and reuse limits: `docs/inventory.md`.
- Host: Ubuntu 26.04.1 LTS, 2 vCPU, 1.9 GiB RAM, no swap.
- Present tools: Python 3.14.4, Node 26.13.0, Git 2.53.0,
  Codex 0.167.0, Gemini 0.67.0. Docker 29.9.3 / Compose 5.7.0 installed;
  GitHub CLI not found in PATH. Exact package/image pins: `docs/runtime-pins.md`.
- Local interview skill: `SKILLS/grill-me/SKILL.md`.
- Local admin skill targets Ubuntu 24.04; validate against 26.04 before use.
- User domains: `cockpit.investalo.de`, `auth.cockpit.investalo.de`; public
  development preview explicitly approved and active. Production remains gated.
- Planning tasks: `docs/tasks/board.md`; documentation index: `docs/README.md`.
- Never store access keys, passwords or tokens in these notes.
- Deployment decision 2026-11-07: Docker Compose plus local Authelia OIDC/MFA.
  Five base services: PostgreSQL, Authelia, API, cockpit and Caddy;
  optional `--profile research` adds the tenant-bound offline worker.
  Default profile publishes `127.0.0.1:8443`; active approved overlay publishes
  only Caddy on5.45.96.83:80/443. Startup/checks: `infra/README.md`.
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
  Applied migrations001–007 are immutable in both `investalo` and
  `investalo_credentials_checks`. The metadata checkpoint advanced the normal DB
  from002 to005; the registry checkpoint adds006 to both databases.
  Local full HTTPS test requires an imported public BTC snapshot, default
  `infra/local/research-data/btc-research.json`, alternative `--snapshot-file PATH`.
- GitHub intermediate pushes explicitly authorized. Origin:
  `github.com:cadm-balzer/Investalo_Trading-Platform.git`.
  Existing host Deploy-Key `/opt/github-project-ssh-key` is used via
  `git -c 'core.sshCommand=ssh -i /opt/github-project-ssh-key -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes' push -u origin feat/m1-passkey-action-proof`.
  Never copy the private key into the repository or print its contents.
- Remote main was verified as already containing the historical credential-path
  commit. IP-005 remains open; no history rewrite/force-push was performed.
- Credential fixture preparation: `infra/scripts/provision-local-credentials-tests.py`.
  Testprofile `credential-storage-checks` deliberately mounts migration credentials.
  Three own credential LOGINs only connect to the fixture DB; the administrative
  checkcontainer has broader development DB rights. No broker or KEK secrets.
  `tests/infra/check_credentials_role_drift.py` requires valid bindings from
  preceding PG tests, verifies a permitted baseline and rolls back its test grant.
- Onboarding checks live in `tests/credential_onboarding` and
  `tests/credentials_storage/test_onboarding_*.py`. Development KEK files are
  generated only inside test temporary directories; no broker/BFF/IdP/rootkey
  mount or network broker transport. Dedicated action assertion is separate
  from the normal BFF API assertion. No HTTP intake launcher exists yet.
- Sensitive step-up routes return503 with valid session/CSRF; no IdP redirect,
  token or credential write. Authelia preserves old MFA state across password
  reauth. Additional Cockpit passkey approved; verifier14.1.0 and durable006
  enrollment/CAS/revocation/audit plus local BFF registration implemented.
  Internal target-bound proofs007 are implemented; browser/credential integration
  and physical device acceptance remain IP-033.
- Checkpoint007:461 API/worker,143 Cockpit and120 credential tests passed,
  typecheck and pinned API/migrate/checks/Cockpit builds passed. Five internal
  signed-BFF POSTs; no browser action route or003/004 execution. Original OIDC
  claims stay unchanged; proof checked_at is separate. Runtime containers were
  not recreated; active development preview still uses the public overlay.
  Proof contract and migration constraints: `docs/passkey-action-proofs.md`.
  CLI ticket artifacts use owned0700 directories and create-only0600 files;
  issue/revoke require explicit manual email attestation and an opaque UUID.
  Do not print ticket artifacts. Counter-CAS alone is no replay proof.
  Host TestClient can stall on sandbox sockets: run tests in the approved local
  Compose checkcontainer or request escalation; do not bypass sandbox controls.
- Both public DNS names resolve to host5.45.96.83; valid LE certificates expire
  2027-02-05. Always use active `--file infra/compose.public-preview.yaml`
  for edge/application runtime changes; default `up` restores local origins/ports.
  `prepare-public-preview.py --development-preview` only creates protected
  separate config/state; it never starts services, changes DNS or provisions users.
  `provision-public-preview.py --development-preview` explicitly adds a public
  synthetic identity to the existing development tenant; original user and worker
  binding stay unchanged. Public check: `check_local_auth.py --public-preview`
  (48 passed). Access details and rollback: `docs/https-entry.md`.
  Protected output includes existing OIDC material; never dump it or run
  `authelia config template`/Compose secret expansion into public logs.
