# TOOLS.md - Local Notes

IP-056 Offline-Research: `python3 infra/scripts/check-portfolio-research.py`
liest als Hostowner ausschließlich die zwei bestehenden gefrorenen
Researchdateien und vergleicht Digests/Ergebnisrecord. Kein Holdout/DB/Broker.
Gezielte gepinnte Prüfung über check-paper-storage.sh mit Filter
`TradingCoreTests or SimulatorTests or PaperRunnerTests or JointQuoteTests or PortfolioTests or test_computation`.

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

## Investalo — verified 2026-11-08

- Working checkout: `/opt/Investalo_Trading-Platform`.
- Implementation branch: `feat/m1-credential-private-transport`, based on main `c573ab3`;
  prior `cd66c3a` merged and verified;
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
  `git -c 'core.sshCommand=ssh -i /opt/github-project-ssh-key -o IdentityAgent=none -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=2' push -u origin feat/m1-credential-private-transport`.
  Never copy the private key into the repository or print its contents.
  The inherited SSH agent stalled while enumerating identities on2026-11-07;
  using the already authorized deploy identity directly completed the push.
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
  Internal target-bound proofs007 and gated proof-only browser integration are
  implemented; credential integration and physical acceptance remain IP-033.
- Checkpoint007:461 API/worker,143 Cockpit and120 credential tests passed,
  typecheck and pinned API/migrate/checks/Cockpit builds passed. Five internal
  signed-BFF POSTs; no003/004 execution. Original OIDC
  claims stay unchanged; proof checked_at is separate. Runtime containers were
  not recreated; active development preview still uses the public overlay.
  Proof contract and migration constraints: `docs/passkey-action-proofs.md`.
  CLI ticket artifacts use owned0700 directories and create-only0600 files;
  issue/revoke require explicit manual email attestation and an opaque UUID.
  Do not print ticket artifacts. Counter-CAS alone is no replay proof.
  Host TestClient can stall on sandbox sockets: run tests in the approved local
  Compose checkcontainer or request escalation; do not bypass sandbox controls.
- IP-037:265 Cockpit tests, typecheck/build,90 enabled plus9 disabled actual
  HTTPS/BFF/API/PG checks and8 preparation security tests passed.
  Opt-in overlay `infra/compose.passkey-browser-checks.yaml` adds only isolated
  `browser-proof-*` services, no host ports. Fixed state:
  `/tmp/investalo-passkey-browser-state`, prepared by
  `python3 infra/scripts/prepare-passkey-browser-checks.py`; root/session dirs
  UID10002/10003, shared GID10010, mode2770 and strict fixture marker.
  Three dedicated synthetic secrets are0440/10003:10010, never preview keys.
  Run/check/stop commands: `infra/README.md#isolierte-passkey-browserprüfung`.
  Stop only those named services; never `compose down` on the shared project.
  No environment override for fixture state. Privileged preparation uses held
  directory FDs/NOFOLLOW and rejects drift rather than repairing foreign state.
  Sandbox UID remapping can show65534 on protected host files; use an approved
  metadata-only host stat when needed. Never relax existing preview secret ACLs.
  Public proof flag remains off; physical device/email attestation unproven.
- IP-038: isolated TS signer/Python verifier, no route/DB issuer/consumer or
  broker execution. New audience/kind and purpose receipt, original OIDC time
  retained; no AMR claim. `checked_at` is not `oidc_auth_time`.
  `credential-assertion-checks` is an explicit opt-in offline Compose profile:
  no network, DB, secrets, mounts or ports. It reuses the pinned storage checks
  image and runs only offline onboarding tests; existing profiles are unchanged.
  333 Cockpit/77 offline Python/109 TS→Python checks, typecheck and pinned
  Cockpitbuild passed; all77 Python tests also passed with Python3.14.10
  in the offline container. Logs `/tmp/investalo-passkey-handoff-{cockpit-tests,
  typecheck,cockpit-build,check-image,pinned-python}.log`. Older461/120/99
  suites not rerun. Public six services unchanged/healthy, TLS200.
  Run builds serially on this host. Commands and evidence:
  `infra/README.md#isolierter-passkey-credential-vertrag`.
- IP-039:008 has been applied ONLY to investalo_credentials_checks.
  Immutable checksum9328008652ad697a306093301d9488fe3e0b184a3ffd8333f7beda5924712c57.
  The development DBinvestalo remains001–007. Do not run default migrate/up:
  use explicit fixture PGDATABASE and keep runtime public overlay unchanged.
  SQL-only rollback preflight used the internal local PostgreSQL socket and
  a synthetic active fixture actor, then reset SESSION AUTHORIZATION/rolled back.
  Logs `/tmp/investalo-passkey-authorization-{preflight,fixture-migration,
  pinned-build,offline,credential-regression}.log`; no credentials in logs.
  Final271 credential tests passed (19 client,95 offline,157 actual PG);
  461 API/worker tests rerun/passed against the fixture DB. Pinned builds passed.
  Six public services unchanged/healthy; regular TLS HTTPS200 readcheck passed.
  Private consume/lock client supplies no broker or003/004 writer.
- IP-040:009 applied only to `investalo_credentials_checks` after fully
  rolled-back DDL/real failure-completion preflight. Immutable checksum
  `435d658458c6be7359ab19ad575421fb843c8756975710cc651eff41c4d62b75`.
  Old001–008 unchanged; `investalo` remains001–007. Pinned migrate/storage/API-
  check builds passed. New private executor injects transport; no runtime caller.
  Output evidence is in the task's command results, not a new log-file set.
  Preflight input: `/tmp/investalo-passkey-execution-preflight.sql`.
  Final356 pinned credential tests passed in153.42s (19 client,116 offline,
  221 actual PG).64 new PG cases and21 new offline cases. One replay test
  expectation corrected, no implementation/migration edits after application.
  Rerun461 API/worker checks passed in91.22s against fixture009.
  Six public services unchanged/healthy, regular TLS HTTPS200 verified.
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
- IP-041: private Cockpit orchestration and default-off API008 bridge,
  no browser credential route or runtime/provider activation.
  `infra/compose.passkey-credential-checks.yaml` provides separate enabled/
  disabled fixture APIs and pinned Node/Python check containers, no hostports
  or logs. `python3 tests/infra/check_passkey_credential_cockpit.py --orchestrate`
  relays bounded synthetic configuration/body/JWT only through private pipes.
  Only Pythonchild mounts fixture administrative credentials.
  299 actual integrated checks passed; fixture APIs are stopped.
  After host reboot, /tmp fixture state/logs disappeared; recreate state only
  with `python3 infra/scripts/prepare-passkey-browser-checks.py`, then explicitly
  recreate only the two fixture APIs so their synthetic secret mounts are current.
  Never run default up/down or remove-orphans for this cleanup.
  572 API/worker checks passed120.61s,385 Cockpit tests/typecheck passed.
  Pinned API/APIcheck/Cockpit/fixture builds and independent reviews passed.
  New retained build log: `/tmp/investalo-credential-cockpit-build.log`.
  Earlier /tmp logs lost at reboot; evidence remains in tool results.
  Existing001–009 immutable; development007/fixture009 verified.
  Historical356 credential suite not rerun; Python/SQL unchanged.
  Six public services healthy, regular TLS HTTPS200 verified.
- IP-042: fixture HTTPS mode adds `--https` to the existing orchestrator.
  Python checker and Node driver communicate on the internal testnetwork
  with alias `credential-flow-executor.cockpit.local.test`; no hostports.
  Dedicated synthetic CA/client/server certificates generated in fixture
  memory/container tempfiles, no real keys/provider/production launcher.
  Administrative fixture credentials never become runtime credentials.
  Original `--orchestrate` pipe checks remain available. No simultaneous
  fixture runs or PG suites: they temporarily share the bound test LOGIN.
  Build images serially and stop only the two named fixture APIs afterward.
  376 pinned credential tests passed148.14s (including221 actual PG),
  440 Cockpit tests/typecheck and346 actual integrated mTLS checks passed.
  Existing pipe flow306 checks rerun/passed; overlap not additive.
  Prior572 API/worker cases not rerun; unchanged API and migrations.
  Fixture APIs stopped, public six services healthy, regular TLS HTTPS200,
  development007/fixture009 rechecked. Build log:
  `/tmp/investalo-credential-private-transport-build.log`.
  Pinned Python/Node fixture builds and Cockpit build passed.
- IP-043: `python3 infra/scripts/prepare-credential-runtime-checks.py` verifies
  a fixed synthetic0700 UID10003 state directory and creates no keys.
  Each `--orchestrate --service` run creates fresh UUID0400 material without
  overwriting or automatically deleting earlier runs. Never dump these files.
  Build `credential-restricted`, `credential-flow-checks`, `credential-flow-node`
  serially with `infra/compose.passkey-credential-checks.yaml`. Start only the
  two named fixture APIs. Service orchestrator starts/stops its own uniquely
  named isolated containers. Runtime receives no administrative/API password;
  service audit checker receives no credential LOGIN password.
  401 pinned credential tests/52 subtests passed154.24s, ten actual root
  preparation tests passed.440 restricted-service/mTLS and387 historical
  HTTPS checks passed; overlapping runs are not additive.
  Historical pipe329 checks rerun/passed. All owned fixture containers stopped;
  six public services unchanged, cockpit/auth regular TLS HTTP200.
  Default runtime image without `--development` exits1 before networking.
  Pinned runtime/Python/Node builds and independent review passed.
  Read-only metadata checker `/tmp/investalo-credential-development-schema-check.py`
  verifies every current SQL checksum against development007/fixture009.
  No new dependencies, migrations or preview activation.
- IP-044: same isolated `--orchestrate --service` commands, now using pinned
  Uvicorn0.54.0/h110.16.0/click8.5.1. Rebuild `credential-restricted` and
  `credential-flow-checks` serially; Node/API source and images unchanged.
  419 pinned credential tests/52 subtests passed154.35s, including18 new actual
  TLS/ASGI cases.451 restricted-service/mTLS points and independent review passed.
  Explicit debug=False/workers=1, raw headers checked before h11 normalization,
  four handshake-inclusive sockets and four separately bounded actual futures.
  Deadline/disconnect never frees still-running work or authorizes retries.
  Runtime without --development exits1 before listener; only named fixture
  APIs started/stopped. All testcontainers stopped, public six services healthy,
  regular cockpit/auth TLS200; all normal007/fixture009 checksums verified.
  No migration/public flag; old Cockpit/API/extra HTTPS/pipe suites not rerun.
  Existing Uvicorn protocol coupling needs TLS/framing/deadline review on upgrades.
- IP-045: rebuild only Cockpit and `credential-flow-node`, serially. Python
  checker remains a read-only bind mount; Python runtime/SQL/dependencies
  unchanged. Start only named fixture APIs, run
  `python3 tests/infra/check_passkey_credential_cockpit.py --orchestrate --service --browser`,
  then historical `--orchestrate --service`, and stop only those APIs.
  `python3 tests/infra/check_credential_browser_disabled.py` starts a unique
  hardened no-network/no-host-mount/no-port Next image and always attempts
  cleanup, including ambiguous detached-run acknowledgment.
  540 Cockpit tests/typecheck/builds passed;481 browser-HTTPS/service points,
  460 existing service points and six actual Next default-off routes passed.
  Activated fixture cookie resolver is synthetic; physical/actual activated
  Next session acceptance remains open. Public services/flags unchanged,
  all testcontainers stopped, checksums normal007/fixture009 verified.
  Independent review has no blocker. Final code guards session inline after
  origin/session awaits; async assertion helpers introduce stale microtasks.

## IP-046 long-history development research

Protocol: `docs/research-protocols/crypto-h4-20261108.json`. Real public BTC/ETH
source2022-08-01..2026-08-01:8,766 H4 candles each. Local ignored files:
`infra/local/research-data/{btc,eth}-research-three-year-20261108.json`
(6,576 bars,2022-08-01..2025-08-01) and
`{btc,eth}-holdout-one-year-20261108.json` (2,190, reserved only).
Root source files are in `/tmp/investalo-{btc,eth}-four-year-20261108.json`.
Never ordinary research-import the full source or simulate the reserved year.

Actual development workflow: `python3 tests/infra/check_local_auth.py
--public-preview --snapshot-file infra/local/research-data/<research-file>`.
Uses existing protected pilot fixtures; no password/TOTP/token output.
Audit/replay: `python3 tests/infra/check_long_research.py` (read-only DB,
research-only core replay, no holdoutperformance).
Full API suite: `bash infra/scripts/compose.sh --profile checks run --rm
--no-deps -T -e PGDATABASE=investalo_credentials_checks api-checks`.
Do not omit the fixture DB override or migrate normalDB to repair a test.
Public running services need no recreate for staged research data.

## IP-048 focused pinned Paper check

Use the existing api-checks image with readonly mounts for current
`packages/trading/src` and `tests/trading` at their `/app/` paths. Run
`python -m pytest /app/tests/trading /app/tests/marketdata
/app/tests/workers/test_computation.py -q -p no:cacheprovider`.
No DB access, rebuild or dependency download needed for this domain checkpoint.
Log: `/tmp/investalo-paper-pinned-tests.log` (84tests/48subtests).
PaperRunner is a checkpoint contract, not a provisioned Paperwriter/daemon.

## IP-049 atomic PostgreSQL Paper checks

`python3 infra/scripts/prepare-paper-storage-checks.py` provisions only the
fixed synthetic Paper LOGIN and preflights010 in a rolled-back transaction.
`--apply-reviewed` applies reviewed010 ONLY to investalo_credentials_checks;
`--rotate-test-secret` rotates ONLY this fixture LOGIN/password file.
Fixture TLS/SCRAM HBA is required; normalDB remains007, fixture now010.
The read-only `/tmp/investalo-credential-development-schema-check.py` expects
007/010 and checks every applied checksum. Never default migrate/up.
`bash infra/scripts/check-paper-storage.sh` reuses the pinned api-checks image
with readonly current source/tests and protected Paper test secret.
78tests/15subtests,29actualPG; log `/tmp/investalo-paper-postgres-tests.log`
mode0600. Sanitize connection failures; pytest traces can expose conninfo.
No builds, host ports, daemon, public recreate or real credentials.

## IP-050 bounded public-feed worker

Read-only actual venue check: `python3 infra/scripts/check-public-paper-feed.py`.
Focused pinned suite: `bash infra/scripts/check-paper-storage.sh`
(151tests/48subtests,30actualPG). Log `/tmp/investalo-paper-feed-tests.log`.
Then `python3 infra/scripts/prepare-paper-feed-check.py` creates one fixture
account/binding and prints its protected infra/local/paper-feed-UUID.env.
Use this as additional --env-file, plus --file infra/compose.paper-checks.yaml,
--profile paper-checks run --rm --no-deps -T paper-fixture.
Default command --once; optionally python -m investalo_workers.paper_main
--cycles 3. No indefinite runs until BL-028 daily baseline.
PG tests rebind same synthetic LOGIN; prepare new fixture/env after tests.
Real run82/84/86, new process88; zero fills. All one-offs stopped.

## IP-051 Paper status

`python3 infra/scripts/prepare-paper-status-checks.py` checks ledger001–010
and fully rolled-back011/runtime/tenant preflight; --apply-reviewed applies
ONLY fixture011. Now immutable, checksum in docs/paper-status-readmodel.md.
Read-only schema checker now expects normal007/fixture011, all hashes verified.
Focused suite `bash infra/scripts/check-paper-storage.sh`:170/48subtests,
37actualPG/API; readonly current API source mount reuses pinned image.
Cockpit: node --experimental-strip-types --test --test-isolation=none
tests/paper-status.test.ts (16), npm run typecheck, pinned compose build cockpit.
Logs /tmp/investalo-paper-status-tests.log, -cockpit-tests.log, -cockpit-build.log.
No public recreate; API_PAPER_STATUS_PREVIEW/COCKPIT_PAPER_STATUS_PREVIEW off.
Q32 pending; do not implement modeled midnight valuation without approval.

## IP-052 approved day basis

Q32 now approved. `python3 infra/scripts/prepare-paper-day-checks.py` preflights
actual writer/day/replay in rolled-back012, --apply-reviewed only fixture.
012 applied/immutable; normal007/fixture012 expected by read-only ledgerchecker.
Checksum b79857a01fa9eba1dbac5d9d46a10432723b4bd97e2b9ad89ca47c1198b2fa0a.
Focused check script now accepts pytest args; select repeats with -k.
190 distinct cases/48subtests: full189 + invalid test OHLC corrected and targeted3.
43actualPG/API,17status SSR/contracts, typecheck. Logs
/tmp/investalo-paper-midnight-tests.log and -targeted.log; pinned build
-cockpit-build.log. Default/public services/flags unchanged; daemon gated.
Pinned build passed; normal007/fixture012/all checksums verified.
Ledger read timeout during CPU-heavy build; single post-build read passed.
Public containers unchanged/healthy, cockpit TLS200.

## IP-053 local Paper observation

Fixed fixture LOGIN investalo_paper_development, protected infra/local/
paper_development.json/password/env. provision-paper-development.py verify or
refuse, no migrations/rebinding/password rotation. check-paper-development.py
requires stopped service; actual duplicate/loss test acquires singleton.
Compose always --env-file infra/local/paper_development.env --file
infra/compose.paper-development.yaml --profile paper-development and only
paper-development target. Local service started2026-11-09 15:59Europe/Berlin;
controlled restart, healthy;24h cycle-start budget, restart:no. Safe logs only.
Public overlay/services unchanged; user/status flags off. Fixture012/normal007.
Runtime checks44 cases in /tmp/investalo-paper-runtime-worker-tests.log;
3 stdlib provisioning units; actual acceptance script passed. Feed82/84/86,
new process88, controlled service restart100→102+, no fills. Stop explicitly
before session checker; never --remove-orphans or blanket compose up/down.

## IP-054 own Paper display active

Normal/fixture001–012 expected. prepare-paper-preview-schema.py is current
read-only ledger check (returns early at012); old /tmp007 checker obsolete.
Protected infra/local/paper_preview.json/password/env, LOGIN investalo_paper_preview,
existing protected public owner tenant, no fixture copying/rebinding. --once only.
Normal HBA exactrole TLS/SCRAM checked/reloaded. API/Cockpit updates ALWAYS
--env-file infra/local/paper_preview.env --file infra/compose.public-preview.yaml
--file infra/compose.paper-preview.yaml, up -d --no-deps api cockpit.
Naked public overlay restores display-off; migrations stay immutable.
check-paper-preview.py --active checks actual flags/isolation; full read-only
HTTPS/MFA check: check_local_auth.py --public-preview --paper-preview.29 checks,
no research job, own checker session logout. Build log /tmp/investalo-paper-preview-build.log,
target34 /tmp/investalo-paper-preview-targeted.log, HTTPS -https.log.
17 Cockpit/5 stdlib units, scoped review passed. Other services untouched;
fixture observation healthy. No normal continuous worker yet; first run82/0fills.
