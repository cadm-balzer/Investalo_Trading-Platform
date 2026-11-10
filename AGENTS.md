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
  current work branch: `feat/m1-paper-preview-integration`.
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

- IP-043 checkpoint `998bb90` is merged into main `9f2a9a5` (verified).
  IP-044 replaces the synthetic service's stdlib HTTP engine with the existing
  pinned Uvicorn/h11 stack. Controlled accepted sockets bound TLS handshake
  and absolute deadlines; peer fingerprint and raw framing are checked before
  parsing. Socket and executor work capacity remain separate across disconnects.
  The launcher remains synthetic-only; no production/provider/broker/public
  activation or migration changes. See `docs/credential-asgi-transport.md`.
  419 pinned credential tests and52 subtests passed, including18 new actual
  TLS/ASGI cases and221 existing actual PG cases. 451 restricted-service/mTLS
  integration points, both Python builds and independent review passed.
  Default image rejects startup without --development. Historical440 Cockpit/
  572 API-worker and older HTTPS/pipe integrations not rerun; code unchanged.
  All migration checksums normal007/fixture009 verified, testcontainers stopped,
  six public services unchanged/healthy and cockpit/auth regular TLS HTTP200.

- IP-044 checkpoint `9555624` is merged into main `dcb9feb` (verified).
  IP-045 implements an isolated browser credential flow: bounded
  session-bound continuations, three strict HTTP phases, browser memory only
  and explicit credential consent after the passkey. Runtime providers and
  public activation remain separate gates; fixtures use synthetic keys.
  540 Cockpit tests (100 new), typecheck, pinned Cockpit/Node fixture builds,
  481 actual controller/HTTPS/restricted-service checks and six actual Next
  default-off route checks passed. Existing service regression460 checks
  passed; overlapping runs are not additive. Final independent review has
  no blocker. Python/SQL suites419/572 not rerun; no dependency/migration
  changes. Normal007/fixture009 checksums verified, testcontainers stopped,
  six public services unchanged/healthy, cockpit/auth regular TLS HTTP200.
  The runtime browser provider deliberately returns unavailable until its
  signing/mTLS identity is provisioned; no flags enable arbitrary key intake.
  The activated fixture uses an injected synthetic cookie resolver, not actual
  Next session storage, browser SameSite or physical authenticators.
  Real provider/key operation, Next/device acceptance, quotas/worker routing,
  reconciliation/recovery and real broker/egress remain open.
  See `docs/credential-browser-flow.md`.
- User confirmed IP-045 merged; checkpoint0a0751b is ancestor of main073c474
  (verified). The user explicitly asks to prioritize the actual trading and
  backtesting system. Continue IP-011/012/013 with multi-year BTC/ETH research
  and then Paper; defer further credential runtime activation. Public-data
  backtests need no private keys. IP-046 technical protocol is recorded before
  performance: fetch2022-08-01..2026-08-01, research first3y, reserve last1y
  solely as holdout. These explicit checkpoint windows are not an approved
  economic validation split or altered strategy. Previously evaluated90-day
  BTC demo is excluded; no ordinary holdout job/worker access.
  See `docs/long-history-backtests.md`.


- IP-046 complete: public BTC/ETH sources8766 H4 bars each, research6576 and
  reserved holdout2190, all gap-free. Exact immutable window CLI; operator
  holdout staging uses existing administrative rights, no new API/SQL grant.
  Both actual public-development research jobs succeeded and their net metrics
  match deterministic core replay exactly. Only research simulated; read-only
  audit confirms four window datasets, no full source import, zero holdoutjobs.
  66 pinned core tests/33 subtests,5 metadata fixturetests,572 API/worker and
  48 actual HTTPS checks per asset passed; independent review has no blocker.
  NormalDB007/fixture009 immutable; public six services unchanged/TLS200.
  Full api-checks MUST use -e PGDATABASE=investalo_credentials_checks, because
  its default normalDB lacks008; never migrate normalDB to repair tests.
  ETH HTTP fixture reads bounded pinned Next JSON clientprops, not browser
  hydration. Economic validation/costcalibration remain open. Next is IP-047:
  persistent simulated paper orders/fills/risk/journal, same core, no keys/live.
  Frozen protocol: docs/research-protocols/crypto-h4-20261108.json.


- 2026-11-09: IP-046eb62176 merged into maindd1903b (verified). User explicitly
  requests lower LLM/API costs: small scoped reads/outputs, bounded checkpoints,
  no repeated broad tests or extra agent calls for routine work. Persist this
  preference; never claim a numeric cost reduction without billing evidence.
  IP-048 adds incremental PaperRunner/checkpoint/journal contract inside IP-047.
  84 pinned focused tests/48 subtests pass,14 new Runner cases. Existing defaults
  and dependencies unchanged. Restore binds actor/account/config/cost/mode;
  no DB writer/feed daemon/HTTP activation yet. Next: PostgreSQL CAS and atomic
  append-only journal, then worker/Cockpit. See docs/paper-runner.md.

- IP-048 checkpoint `fe6309a` merged into main `dc60c19` (verified).
  IP-049 implements private PaperStore and atomic010 checkpoint/journal CAS.
  Dedicated paper LOGIN uses SESSION_USER account binding; no direct tables,
  credential access or new runtime/research rights. SQL trusts Python economic
  calculations. Require fresh non-autocommit connections; unknown commits
  require readback, never automatic retry. 78 pinned tests/15 subtests passed,
  including29 actual PG cases; independent review has no remaining blocker.
  Reviewed010 applied ONLY to investalo_credentials_checks after rolled-back
  DDL/worker/failure preflight. Immutable SHA256:
  812a0a1f1702f09ef3b9410640eae7b60498320326888a86c494a83f8f3f5797.
  Development investalo remains001–007; fixture001–010 verified.
  NEVER default migrate/up to repair tests. Fixture-only TLS/SCRAM HBA added;
  PG config reloaded, public containers not recreated, cockpit TLS200.
  Synthetic fixture password rotated after a connection trace; factory errors
  now sanitized. No real credentials affected. No builds/dependencies added.
  IP-047 next: public market feed, running Paperworker and Cockpit status.
  See docs/paper-postgres-store.md.

- IP-049 checkpoint e0cfb45 merged into main1a805e5 (verified). IP-050 connects
  fixed unsigned Bitget SPOT ticker/current-candle GETs to PaperRunner/Store.
  BTC/ETH,40 closed-H4 warmup, complete coverage/revised overlap/fresh real
  bid/ask, no historical fills or manual approval. Every input commits atomically;
  unknown commit stops process, next process reads state before new inputs.
  Only explicit --once or --cycles1..100 accepted. Continuous operation gated:
  REST polling cannot reliably supply exact midnight baseline required by core;
  daily_baseline_required stays enforced, no current-equity substitution.
  Isolated fixture overlay has own Paper LOGIN/CA only, no ports/admin keys,
  separate development egress bridge, existing pinned image/readonly source.
  Real public feed40bars each; actual cycles82/84/86 then restart88, zero fills.
  151 pinned tests/48 subtests,30 actual PG; independent bounded review green.
  Normal007/fixture010/checksums unchanged, no migrations/dependencies/builds.
- IP-050 checkpoint af65c51 merged into mainb9d4b41 (verified). IP-051 adds
  read-only own-tenant Paper status/journal API and gated Cockpit panel.
  API_PAPER_STATUS_PREVIEW and COCKPIT_PAPER_STATUS_PREVIEW default off;
  Default Compose/public preview unchanged. Stored inputs do not prove a
  running worker; historical/missing valuation and absent daily baseline
  are explicit. No strategy, risk, writer or execution change.
  Reviewed011 preflight fully rolled back, then applied ONLY to
  investalo_credentials_checks; normal001–007/fixture001–011 and all applied
  checksums verified. Applied011 immutable SHA256:
  8065031b7eb57486013282e84b91bd6fb3c205155f9aec1ca81b5470b9430f72.
  Restricted runtime function rechecks active user/member, original OIDC and
  epoch; SQL trusts authenticated API and transaction-local identity GUCs.
  No direct Paper table/writer rights. 170 pinned targeted tests/48 subtests
  (37 actual PG/API),16 Cockpit contract/SSR panel tests, typecheck/pinned build
  and scoped independent review passed. No new dependencies/broad credential
  repeats. Existing public containers unchanged/healthy, cockpit TLS200.
  Q32 was pending at this checkpoint; approved and implemented by IP-052 below.
  IP-047/BL-028 continuous operation/activation still open.
  Contract: docs/paper-status-readmodel.md.
- IP-051 checkpoint05ea009 merged into main5d5c61e (verified).
  User explicitly approved Q32 H4-close midnight Paper model valuation and
  reminded RSI relevance. IP-052 adds day input paper-h4-close/1 before any
  new-day quote/fill. Prior persisted cash/inventory, exact BTC/ETH midnight
  bars, committed evidence and replay-stable baseline; no retroactive repair
  of already changed post-midnight inventory. Missing evidence blocks buys.
  RSI14/Wilder closed-H4 automatic entry/rearm rules,6%/8%, real quote fills,
  protection and latched halts unchanged. Manual sixth-stage Q29 unchanged.
  Historical simulator/frozen Research results unchanged. No competing Paper
  quote-driven day reset.012 guards frozen midnight candle digests across
  restart and exposes model label through default-off status API/Cockpit.
  Fully rolled-back actual writer/replay preflight and scoped review passed;
  012 applied ONLY to fixture, now immutable SHA256:
  b79857a01fa9eba1dbac5d9d46a10432723b4bd97e2b9ad89ca47c1198b2fa0a.
  Normal007/fixture012; no new dependencies/normal migration/public activation.
  190 distinct targeted Python/PG cases/48subtests passed (43 actual PG/API):
  full189 plus corrected invalid test OHLC/targeted3;17 Cockpit SSR/contracts
  and typecheck/pinned Cockpitbuild passed. Normal007/fixture012/all hashes
  verified; existing public containers unchanged/healthy/cockpit TLS200.
  Continuous service still gated on operational
  acceptance; bounded once/cycles remain. Contract: docs/paper-midnight-basis.md.
  Public six services unchanged/Cockpit TLS200; one-off fixtures stopped.
  Tests rebind fixed investalo_paper_tests LOGIN: prepare a new fixture/env after tests,
  never blindly reuse older account configuration. Next IP-047: safe daily
  baseline operation, dedicated persistent development identity and Cockpit.
  See docs/paper-market-worker.md; cost preference remains scoped work.


- IP-052 checkpointc1703c1 merged into maina996bf2 (verified).
  IP-053 adds fixed local fixture LOGIN investalo_paper_development and stable
  protected prepared/bound manifest; never rebind/rotate/unpause automatically.
  Repeated provisioning and four rolled-back privilege/binding drift probes pass.
  Explicit paper-development profile: no ports, own password/CA, readonly code,
  bounded resources/logs and restart:no. Strict development-loop fixes PG
  identity/config and rejects extra PG variables. Separate autocommit advisory
  singleton session with guards before writes/health; lost session/unknown
  commit terminal. CAS remains authoritative across cooperative check/write gap.
  Six consecutive failures stop; max24h for new cycle starts, not hard wall
  for already-running work.44 targeted pinned worker cases/3 provisioning units
  and actual restricted TLS/duplicate/release/session-loss/normal-DB denial pass.
  Real feed revisions82/84/86, fresh process88; no fills. Local service healthy,
  duplicate process rejected, controlled restart continued102+ after100.
  Synthetic account separate from rebinding tests; RSI/Q32/risk unchanged.
  No migration/dependency/public activation; normal007/fixture012 hashes verified.
  Public six services unchanged/TLS200, status flags off, fixture has no public
  user. Retention/quota/Egress/monitoring/recovery and actual midnight observation
  remain BL-028; next IP-047 user/status integration. Keep scoped checks for cost.
  Contract: docs/paper-development-runtime.md.


- IP-053 checkpoint03fee1e merged into mainb0827ba (verified).
  IP-054 activates read-only own Paper display within the already approved
  public DEVELOPMENT preview. Normal investalo and fixture now001–012;
  reviewed008–012 applied atomically only after full rolled-back DDL and actual
  own/foreign/epoch/old-OIDC/revoked-membership runtime preflight. Immutable files
  unchanged.008/009 expand private capabilities; actual sensitive flags/routes
  remain off, no credential launcher or key/broker/live activation.
  Stable investalo_paper_preview LOGIN/account under protected existing public
  owner tenant; prepared recovery verifies existing grants before mutation.
  No fixture copying/rebinding, no original user/tenant/research/factor changes.
  Exact normal TLS/SCRAM HBA, fixture/direct-table/other-definer denial tested.
  Strict paper_preview_once --once fixed normal DB/role/CA/secret; no retry or
  listener. Real run revision82/zero fills; RSI/Q32/risk/costs unchanged.
  Only API/Cockpit rebuilt/recreated. For future preview updates use BOTH
  --file infra/compose.public-preview.yaml and --file infra/compose.paper-preview.yaml
  with --env-file infra/local/paper_preview.env. Naked public overlay keeps
  display off and is its fallback; default Compose unchanged. Caddy/Auth/PG/
  Research and separate healthy fixture observation were not recreated.
  34 targeted pinned Pythoncases,5 stdlib provisions,17 Cockpit SSR/contracts,
  pinned builds and scoped review passed.29 real HTTPS/OIDC/MFA/BFF checkpoints
  show own state on overview/portfolio/journal, no cache, sensitive routes503,
  logout only test session/no research job. Both012 hashes and original stable
  fixture identity verified. This is a saved bounded-run state, not a confirmed
  continuously running preview worker or profitability proof. Next IP-047:
  own bounded preview observation; BL-028 midnight/Egress/quota/retention/recovery.
  Contract: docs/paper-preview-integration.md. Keep cost-sensitive scoped work.

- IP-054 checkpoint b48be7d merged into main 2a9efe0 (verified).
  User accepts the visible Cockpit progress and asks to prioritize planned
  strategy fine-tuning because absolute returns are small. IP-013 first
  diagnoses exposure/capital use, RSI entries, exits, costs and a comparable
  benchmark, then bounded chronological candidate validation. Stored IP-046
  research spans three years: BTC +132.63 / ETH +96.09 USDT per separate
  10,000-USDT account (~1.33% /0.96% total). No invested-capital return or
  independent profitability proof inferred. Holdout stays sealed until frozen
  selection; this request does not approve changing strategy/budgets/risk.
  Plan: docs/long-history-backtests.md#geplantes-feintuning.

- Q33 (2026-11-09): user plans 3–5 different crypto baskets concurrently,
  full account capital allocation and later AI evaluation after RSI signals.
  On explicit follow-up user confirms daily6% / initial8% remain binding.
  Allocation is not full investment authority; shared equity/reservations/
  portfolio risk can prevent stages or close baskets early. IP-055 prepares
  joint portfolio research, not an addition of separate asset simulations.
  Additional assets, exact budgets/reservation/priority rules remain to be
  specified. Current BTC/ETH500+5 spot profile and immutable results unchanged.
  AI market phase/Fear & Greed/news/halving context first in shadow mode with
  as-of information, versioned decisions and bounded token costs. Variable
  leverage/fewer stages are future candidates needing separate validated
  strategy/margin rules; no AI override of limits or delay of protection.
  Plan: docs/multi-basket-ai-plan.md; D-059 / BL-029 / IP-021/022/055.

- Plan9455bfe merged into mainef18d74 (verified). IP-056 prepares IP-055
  with separate offline
  joint BTC/ETH research on unchanged500+5 budgets/10k equity, not the expanded
  allocator. Complete atomic on_quotes validates all prices before shared risk;
  explicit historical midnight close checks previous6% before baseline reset.
  Single-quote/Paper/worker paths unchanged. Canonical aligned H4 and separate
  frozen policy digest; passive benchmark shares max budgets/costs/rounding/bid
  terminal valuation, without strategy risk exits or exposure matching.
  Actual6576 researchbars/asset: net228.716909USDT, maxDD0.6143546%,
  held principal time-average72.5594567USDT (0.7255946% initial). Benchmark
  net2577.902525, peakDD12.1144932%, initial loss3.4806339%/daily3.1920850%.
  Peak DD is NOT loss against8% INITIAL limit.56 baskets (BTC24/ETH32) do not
  prove per-asset holdout targets. Fixed file/hash/window replay uses research
  ONLY, no DB/broker/holdout access, migrations/dependencies/public changes.
  New coins requested; expanded budgets/stress/reservations/priority remain
  IP-055. Contract: docs/portfolio-reference.md.
  65 targeted pinned cases/26subtests +4 host inputguards, exact real research
  replay including benchmark loss bases and read-only final review passed.
  No new holdout/selection/physical-browser/public activation claim.

- IP-056 checkpoint698146f merged into main3bb0d0c (verified).
  IP-057 adds an unconnected stdlib proposal
  for equal3–5 slots, explicit cost reserve and bound immutable buy reservations.
  Shared cash/lifetime budget/min6%/8% headroom; proposed correlated50% stress
  counts holdings/pending/candidate plus unused fees once. Further-buy price
  caps <=first fill; no gain offset/silent clipping. Unknown/cancel-requested
  buys stay reserved and deny new purchases. No release/retry/reset or durable
  CAS/execution/authentication claim; caller supplies complete authoritative
  account evidence.10k/1% reserve permits~1002 initial aggregate principal;
  five first stages fit, later buys can fail. Larger budget/stress profile
  explicitly asked before research integration; no answer inferred, coins also
  undecided. Budgets do not renew on sale; cycle reuse/priority/research adapter
  remain IP-055.85 pinned targeted tests/65subtests,81 host tests/review passed.
  Existing strategy/DB/holdout/broker/public runtime unchanged.
  Contract: docs/portfolio-allocation.md; D-061.

- IP-057 checkpointd31dcf3 merged into main1f44b7f (verified). Q34:
  user explicitly accepts equal3–5 slots/1% principal cost reserve/additional
  correlated50% stress for offline research, retaining6%/8%. Reminds staged
  buys lower average cost.
  IP-058 connects the allocator to existing deterministic RSI/fill/portfolio
  core with its own allocated-rsi-research/1 config/state/report. Two closed
  RSI<30 bars first; further buys rearm>30 then<30 and >=5% below last actual
  regular fill;25% growing stages, five regular plus explicit manual sixth.
  Complete intent/dispatch assessment; own pending buy excluded at dispatch.
  Actual buy principal/all fees retained across partial/closed sales and
  duplicate fills. No cycles replenished yet; one full cycle per synthetic
  slot until its next contract. User explicitly asked now for coin selection
  and same nominal slot reuse after normal fully reconciled exits, no budget
  growth/partial-release/risk-stop automatic resume. Answers still pending;
  do not infer them from profile approval.97 targeted pinned cases/65subtests,
  93 host cases,12 final adapter cases repeated pinned/host and scoped review
  passed. No extra-market assets, profitability/MFAhardware proof, new
  dependencies, DB/holdout/broker/normal runtime or snapshot activation.
  docs/staged-portfolio-research.md; D-062.

- IP-058 checkpoint4f56024 merged into main7ec9b41 (verified). Current branch:
  feat/m1-portfolio-history-preflight. User asks clarification of coin and
  reuse questions; clarified both, answers remain pending. IP-059 public
  metadata/readiness only: five proposed SPOT USDT instruments online, exact
  first two2022-08-01 H4 bars/asset parsed (10 total). No complete three-year
  history/performance/holdout/market approval inferred. Current ETH minimum
  quantity0.0005 needs a separate future research constraint; don't add fields
  to frozen v1 rules/digests or treat current metadata as historical facts.
  Actual responses/timestamps/hashes in docs/research-protocols/
  portfolio-candidates-preflight-20261110.json. No runtime/DB/private/broker/
  strategy change. docs/portfolio-history-preflight.md; D-063.

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
- Make sure you work efficiently and avoid unnecessary long-running LLM tasks. Keep the LLM context efficient and save on token costs.

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
