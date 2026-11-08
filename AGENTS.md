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
  Reconfirmed2026-11-08: execute local commands independently, without renewed
  routine approval questions. Production deployment remains separately gated.
- The user explicitly authorized intermediate commits and GitHub pushes.
  Push reviewed feature checkpoints with the existing repository deploy identity;
  this does not authorize production deployment, history rewrite or force-push.
- Default foundation: `infra/README.md` starts five services behind loopback and
  the optional offline research worker. Immutable H4 snapshots, frozen jobs and
  persisted net results/equity charts are implemented. A real 90-day BTC import
  tests the workflow; it does not satisfy the three-year/holdout validation gate.
  Broker execution, recovery and pilot operation remain unfinished.
  Generated `infra/local/` is ignored and never a build context.
- Existing reference repositories: `/opt/investalo-trading-system` and
  `/opt/investalo-autotrader`. Treat them as read-only references unless work there
  is explicitly authorized. Their strategies need independent net-cost validation.
- Bitget account clarification after Q31: the user's funded account is Classic
  with separate spot/futures wallets. Each platform user creates a dedicated key
  in their own Bitget account (API key, secret and passphrase). Initial private
  adapter is Classic V2. Keep wallet capital separate; do not infer permission
  for futures trading, transfers or real-money activation from funded balances.
  Connection/onboarding scope: `docs/bitget-connection.md`.
  Isolated stdlib Classic read core: `integrations/bitget/README.md`, 24 offline
  tests in `tests/bitget`. Private store/onboarding integration exists below;
  actual user keys, HTTP/UI and broker calls remain IP-009/IP-015.
  Only three fixed GET paths.
  User accepted checkpoint `3052560` and will merge it themselves.
  GitHub default branch is `main`; verify merge state before changing branches.
  Main now contains accepted checkpoint and acceptance note (`3fd95b1`), verified
  at `d3b31e2`; envelope checkpoint `7f83b33` merged into main, verified at
  `71e57f1`; store checkpoint `46860ab` merged into main, verified at `b3030de`;
  onboarding checkpoint `69a1f8b` merged into main, verified at `56070ba`;
  step-up checkpoint `d57bd56` merged into main, verified at `b6198f7`;
  registry checkpoint `6a18102` merged into main, verified at `f422a90`;
  current work branch: `feat/m1-credential-development-service`.
  Isolated AEAD core: `packages/credentials/README.md`, 20 offline tests with
  pinned cryptography and a separate hardened Compose check.
  Credential store: `services/credentials/README.md`; migration003 and current
  AAD/CAS/rotation/revocation verified with 19 client +18 actual PostgreSQL tests,
  four provisioning tests and a rolled-back role-drift probe. Both local DBs
  `investalo` and `investalo_credentials_checks` now have001–007 applied.
  Applied migrations are immutable in either database.
  Credential LOGINs are bound through SESSION_USER to one active tenant/user;
  runtime/research cannot read tables or execute credential functions.
  The administrative check profile mounts migration credentials; it is not a
  restricted runtime service.
  Private `BitgetOnboarding` connects the existing Classic probe, canonical
  triple codec, store and dedicated request-bound one-use assertions.
  Migration004 commits a globally unique JTI before probing, rechecks actor/
  epoch/reauth/account/versions/time and finishes write/audit in one transaction.
  SQL trusts Python signature verification; direct003 functions remain trusted
  primitives, without a universal MFA guarantee. The007 proof remains separate
  from003/004 credential execution.
  `DevelopmentKeyFileProvider` explicitly requires development mode and fixed
  trusted fingerprints, ownership/modes and 32-byte KEKs; no production provider.
  Tests use synthetic assertions/keys/broker responses with actual PG.
  120 checkcontainer tests passed: 19 client, 41 onboarding units, 60 actual PG
  (18 store, 30 authorization, 12 synthetic Bitget/AEAD flows). IP-030 complete.
  Credential HTTP/UI, physical browser step-up and actual user credentials remain unfinished.
  Additive005 exposes only authenticated own account/connection metadata to
  the runtime LOGIN; no UID/envelope/key material or direct private-table rights.
  112 API/worker and120 credential regression tests passed after005.
  Prepared BFF state binds session/CSRF/actor/tenant/epoch/target/CAS and an
  opaque preview token against stale tabs. All sensitive HTTP/UI steps stay off.
  Authelia4.39.28 password reauth preserves old second-factor state; auth_time
  plus amr=mfa proves no fresh second factor. Do not weaken this release gate.
  User explicitly approved additional free Cockpit passkeys for account changes.
  SimpleWebAuthn14.1.0 checks UV/UP/exactRP/origin/challenge/owner/key/counter.
  Additive006 implements durable FORCE-RLS registry, one factor per tenant/user/
  RP and RP-wide credential uniqueness including revoked rows. Administrative
  enrollment uses manually attested email approval plus opaque confirmation UUID;
  32-byte bearer ticket is stored only as hash, max600s, with claim committed
  before crypto and max120s enrollment. Local BFF/UI enrollment binds current
  actor/epoch/session/CSRF/Origin and consumes each attempt once.
  ES256/UV/UP/fmt=none registration is a candidate, not first-use private-key
  proof; a fresh assertion remains mandatory before sensitive actions.
  Admin revocation advances global user auth_epoch/reauth_after and invalidates
  all tenant sessions. Terminal tombstones prevent recovery/re-enrollment;
  BL-025 remains open. SQL assertion CAS is a trusted primitive without challenge
  replay proof; no unbound HTTP CAS endpoint. Physical browser acceptance and
  credential integration remain IP-033; account changes stay disabled.
  Migration006 passed293 API/worker checks including67 actual registry/API PG
  cases;120 credential regressions and115 cockpit tests passed. Typecheck,
  builds and48 real HTTPS checks passed; two independent reviews found no blockers.
  A complete synthetic BFF enrollment is now verified in IP-037; physical device
  proof remains IP-033.
  Applied001–007 are immutable.
  Session TTL store holds enrollment attempts only;
  preserve original OIDC claims. See `docs/passkey-step-up.md`.
- User explicitly approved the public development preview on2026-11-07 after
  adding auth DNS. Both cockpit.investalo.de and auth.cockpit.investalo.de now
  resolve to5.45.96.83 and serve valid Let's Encrypt certificates through Caddy.
  Active opt-in `--file infra/compose.public-preview.yaml` exposes only edge80/443;
  default Compose remains local and must not accidentally replace the overlay.
  Twelve preparation/provisioning tests and48 real public HTTPS checks passed;
  certificate persistence after restart and original identity/data bindings verified.
  The separate public-issuer synthetic user explicitly shares the existing
  development tenant; old user, worker, keys and factors remain unchanged.
  RP/credential ownership is not migrated. IP-035 complete; BL-026 TLS operations
  and full pilot/production acceptance remain open. Account changes/live remain off.
  See `docs/https-entry.md`.
- HTTPS checkpoint `35960f3` is merged into main `e741c6b` (verified).
  User confirmed successful public browser login and Google Authenticator setup,
  accepted the visible progress, and instructed continued M1 work.
  IP-036 implements the internal durable target-bound passkey proof in additive007:
  committed one-use claim before crypto, RP-wide unique challenge, immutable
  actor/session/CSRF/origin/old OIDC time/metadata/factor bindings, atomic
  counter/version CAS plus grant, and own-preview confirmation consumed once.
  API/SQL trust the authenticated BFF crypto verdict; original OIDC claims stay
  unchanged and checked_at is separate. Confirm reports execution_enabled=false;
  no account-action browser routes or003/004 credential execution enabled.
  Full regression:461 API/worker (70 new actual PG),143 cockpit (28 new crypto),
  120 credential checks, typecheck and pinned builds passed; independent reviews
  found no blockers. Both DBs001–007 immutable. Running preview containers were
  not recreated. Hardware/browser acceptance and credential integration remain
  IP-033; retention/rate operation BL-017, recovery BL-025.
  See `docs/passkey-action-proofs.md`.
  Implementation checkpoint `9b47ae1` and acceptance note `4c9f63f` are merged
  into main `2c996d5` (verified). If the inherited SSH agent stalls, use the existing deploy identity
  with IdentityAgent=none and strict host-key checking (see `TOOLS.md`).
- IP-037 connects007 to gated proof-only `/security/passkeys/verify` and four
  `/api/passkeys/actions/` POST routes. Explicit
  `COCKPIT_PASSKEY_PROOF_PREVIEW=1` is required; default and public Compose keep
  it off. Pass the immutable session that authorized HTTP CSRF to the adapter;
  recheck identity/epoch/original OIDC time/expiry/CSRF/origin after awaits.
  Browser receives only safe preview/options/grant fields; tokens remain in
  page memory. Enrollment preserves original expiry and requires authoritative
  factor readback after write. 265 Cockpit tests, typecheck and pinned build,
  90 isolated HTTPS/BFF/API/PG checks, nine disabled checks and eight fixture
  preparation security tests passed; independent review has no remaining blocker.
  Test services use dedicated synthetic keys, fixed protected `/tmp` state and
  the fixture DB, no host ports; all are stopped. Running public services were
  unchanged and remain healthy (HTTPS200). No migrations/dependencies changed.
  These checks use synthetic P256/approval, not physical devices or real email
  attestation. Public activation, physical acceptance,003/004 integration,
  recovery and pilot operation remain open. See `docs/passkey-browser-proof.md`.
- IP-037 checkpoint `84f7633` is merged into main `512c096` (verified).
  IP-038 adds an isolated versioned TS/Python passkey credential assertion
  contract: distinct audience/kind, purpose receipt, actor/session/target/CAS,
  metadata digest and exact body bytes. Preserve original OIDC time; fresh
  passkey check and credential consent times are separate. Do not fabricate AMR.
  The receipt parser accepts trusted server inputs; it cannot prove durable
  issuance. Signing and verification are repeatable, with no DB consumer.
  A007 proof-only confirmation is not credential consent. Explicit purpose
  authority and global consumption are implemented by IP-039 below; final
  credential writer integration remains open.
  New signer/verifier have no HTTP/runtime caller; old contracts and001–007
  remain unchanged. Optional `credential-assertion-checks` runs offline tests
  without network, secrets, mounts, ports or DB dependencies; existing services
  are unchanged. Physical acceptance, integration and recovery remain IP-033.
  333 Cockpit tests,77 offline onboarding tests on host and pinned Python3.14.10,
  109 actual TS/Jose/Python checks, typecheck and pinned Cockpit build passed.
  Independent review has no remaining blocker. Historical461 API/worker,
  120 credential and99 HTTPS fixture cases were not rerun. Public services
  remain unchanged/healthy/TLS200, proof flag off.
  Contract and validation: `docs/passkey-credential-assertions.md`.
- IP-038 checkpoint `8bb64db` is merged into main `13ba2e2` (verified).
  IP-039 adds explicit purpose authority in008: purpose/origin/body digest
  frozen at prepare, explicit consent only from a still-granted007 proof,
  global one-use consume and a separate final transaction lock.
  A proof-only007 confirmation cannot be converted into credential consent.
  The private client verifies the dedicated30-claim assertion before DB access
  and returns a client-bound handle only after acknowledged consume commit.
  Unknown commits never trigger automatic retries. SQL trusts authenticated
  Python/BFF crypto; it is not a signature verifier. Current SESSION_USER actor,
  epoch/reauth/original OIDC, factor, metadata/CAS and clock are checked at both
  boundaries. Final lock is terminal across commits, repeatable within its TX.
  No003/004 executor, HTTP route, broker or runtime activation is connected.
  Reviewed008 was preflighted in a fully rolled-back transaction, including
  actual runtime preparation, then applied ONLY to investalo_credentials_checks.
  Its immutable checksum is9328008652ad697a306093301d9488fe3e0b184a3ffd8333f7beda5924712c57.
  Development DB investalo remains001–007; never blindly run default migrate/up.
  271 credential tests (19 client,95 offline,157 actual PG,97 new PG cases),
  rerun461 API/worker checks and pinned migrate/storage/API-check builds passed.
  Independent review has no blocker. Public services unchanged/healthy/TLS200.
  Historical333 Cockpit/109 interop checks were not rerun; TS signer unchanged.
  Validation and remaining integration: `docs/passkey-credential-authorizations.md`.
- IP-039 checkpoint `389082a` is merged into main `be13145` (verified).
  IP-040 connects the private `PasskeyBitgetOnboarding` executor:
  committed008 consume before any read/probe, separate008 lock +003 AEAD
  mutation +009 terminal completion in one final transaction. Exact verified
  claims/SESSION_USER/current lock XID and permitted postmutation CAS state
  are required; actor/factor/account/time remain current. Clock is checked
  after audit/FK waits. Failures roll back final write/lock/completion while
  consume remains; unknown commits never retry or overwrite completed audit.
  Revoke needs no key read/decryption/probe and permits paused accounts.
  009 passed fully rolled-back DDL and actual failed-completion preflight,
  then applied ONLY to investalo_credentials_checks. Its immutable checksum:
  435d658458c6be7359ab19ad575421fb843c8756975710cc651eff41c4d62b75.
  Old001–008 unchanged; development investalo remains001–007. No HTTP caller,
  real broker transport/key intake or public flag activation. 356 pinned
  credential tests passed (19 client,116 offline,221 actual PG;64 new PG),
  including real signed receipts, AEAD writes, audit-wait expiry and unknown
  commit cases. Pinned builds and independent review passed. Public services
  unchanged/healthy/TLS200. Rerun461 API/worker tests passed against fixture009.
  Contract: `docs/passkey-credential-execution.md`.
- IP-040 checkpoint `3476f74` is merged into main `0fd25b6` (verified).
  IP-041 implements private BFF orchestration and default-off008 API
  prepare/authorize routes, preserving the original session and explicit
  credential consent. Integration checks use synthetic keys and the isolated
  fixture database. No browser credential intake, runtime credential service,
  public flag or migration activation is included in this checkpoint.
  Original session/CSRF/Origin/OIDC and current actor/factor/metadata remain
  bound after awaits; explicit credential consent cannot reuse007 proof-only
  confirmation. Exact private body stays solely in trusted caller memory.
  572 API/worker tests (111 new:87 unit,24 actual PG),385 Cockpit tests
  (52 new),299 real synthetic TS/WebAuthn/HTTPS/API/PG/Jose/Python/AEAD/009
  checks, typecheck, pinned builds and independent reviews passed.
  Existing001–009 immutable; investalo001–007, fixture001–009 verified.
  Historical356 credential tests were not rerun; private Python/SQL unchanged.
  User restarted host; protected synthetic /tmp state regenerated by the
  existing preparation script, then fixture completed. Fixture APIs stopped;
  six public services healthy, regular TLS HTTPS200. See
  `docs/passkey-credential-cockpit.md` for remaining browser/runtime gates.

- IP-041 checkpoint `cd66c3a` is merged into main `c573ab3` (verified).
  IP-042 implements an injected private development HTTPS transport with mutual
  TLS, a dedicated CA and pinned BFF client certificate. Trusted original
  session context is separate from the opaque credential JWT; actor/role/DSN
  selection remains fixed server configuration. Only synthetic fixture checks;
  no production launcher, runtime key provider, browser intake or public flag.
  The stdlib HTTP server is development-only, never a production acceptance.
  User reconfirmed continuing M1 and the need for longer BTC backtests:
  three-year BTC/ETH research and independent holdout remain IP-011/IP-013/BL-018;
  the current90-day snapshot is only workflow proof.
  376 pinned credential tests (20 new HTTP/mTLS),440 Cockpit tests (55 new),
  typecheck and346 real mTLS/HTTPS/WebAuthn/API/PG/AEAD checks passed.
  Existing pipe flow306 checks rerun/passed; overlapping runs are not additive.
  Independent review has no remaining blocker; prior572 API/worker tests
  were not rerun (API/migrations unchanged). Fixture APIs stopped, six public
  services healthy, regular TLS HTTPS200; DB007/fixture009 verified.
  Pinned Python/Node fixture and Cockpit builds passed; running preview
  containers were not recreated. No new dependencies or migrations.
  Contract: `docs/passkey-credential-https.md`.

- IP-042 checkpoint `94fb73b` is merged into main `6300971` (verified).
  IP-043 adds an explicit synthetic-only development credential launcher and
  isolated container. Fixed fixture DB/LOGIN, actor and008/009 capabilities
  are verified before listening; ambient PG options are rejected. Owned0400
  files pin separate signing/KEK identities and the mTLS client certificate.
  Exact synthetic canaries are required before verifier/consume; broker is
  synthetic. Runtime mounts no migration/API/research password or BFF client
  private key. Administrative setup/audit mode mounts no credential LOGIN
  password and never calls the executor. New per-run UUID state is create-only;
  no new dependencies or migrations. Stdlib HTTPS/file provider remain
  development-only; production server/provider, physical/browser acceptance
  and real keys/broker remain open. See `docs/credential-development-service.md`.
  401 pinned credential tests with52 subtests (25 new launcher cases),10 host
  preparation tests and440 integrated restricted-service/mTLS checks passed.
  Default image without development opt-in rejects before network startup.
  Pinned runtime/Python/Node builds and independent review passed.
  Historical injected HTTPS387 and pipe329 checks rerun/passed; overlap is
  not additive. Prior440 Cockpit/572 API-worker suites not rerun; app code
  unchanged. All migration checksums normal007/fixture009 verified.
  Fixture containers stopped, six public services unchanged/healthy,
  cockpit/auth regular TLS HTTP200.

## Trading and implementation invariants

- Profitability is a measurable research objective, never a guarantee.
- Use one versioned deterministic strategy core for backtest, paper, and live.
- Risk limits are enforced independently of strategy/AI and before order dispatch.
- Model quote budget, position notional, usable margin, and account equity separately.
- Never retry an uncertain broker order blindly; reconcile before resubmission.
- Require authenticated tenant context for requests, jobs, files, caches, and streams.
- Broker credentials must never reach browser storage, research workers, AI, or logs.
- Research workers use a dedicated LOGIN role bound to one tenant through
  `SESSION_USER`, bounded fenced leases and restricted database functions.
  Never give them API/migration credentials or evaluate protected holdout datasets.
  Snapshots, frozen job inputs and terminal results are immutable. Applied SQL
  migrations are checksum-protected; extend them with a new numbered migration.
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
