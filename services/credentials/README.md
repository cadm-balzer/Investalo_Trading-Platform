# Credential storage and Bitget onboarding

Isolated Python client for migration 003's fixed PostgreSQL functions, using the
AEAD core in `packages/credentials`. The trusted onboarding layer connects it
to the Classic Bitget identity probe, a versioned private triple codec and
one-use action assertions. No HTTP/API/CLI launcher or real credentials are
accepted. The file provider is explicitly for development, not a production
root-of-trust.

## Persistence primitive

`CredentialStore(StoreContext(...), trusted_keyring, connect=...)` accepts a
trusted factory returning a transactional connection context manager with a
default tuple-row cursor. The factory must provide a fresh dedicated PostgreSQL
LOGIN connection, commit on success, roll back on errors and close/release it.
The client rejects `autocommit=True`. A normal non-autocommit `psycopg.connect`
connection supports this contract; exact dependency pins and wheel hashes are in
this service's `requirements.lock` and `requirements-test.lock`.

Every operation checks actual `session_user == current_user == expected_login_role`,
LOGIN capability, and absence of superuser, CREATEROLE, CREATEDB, REPLICATION and
BYPASSRLS privileges. `platform.credential_context()` then resolves actual
`SESSION_USER` to active database-bound tenant/user UUIDs, which must match the
expected context. Caller UUIDs, tenant GUCs or `SET ROLE` do not establish
authorization. SQL additionally enforces active user/membership, role bindings,
ownership and account gates; connection factory/session identity and KEKs are
trusted server responsibilities.

The client uses one fixed PostgreSQL role-metadata projection and only these
fixed parameterized functions. No dynamic SQL identifiers or caller table names:

| Method | Database action |
| --- | --- |
| `register(binding, payload)` | `credential_create`, revision/storage version 1 |
| `read(connection_id)` | `credential_read`, authoritative current AAD and decryption |
| `replace(..., expected_revision, expected_storage, payload)` | authenticate old payload, seal revision +1, `credential_replace` CAS |
| `rewrap(..., expected_revision, expected_storage)` | authenticate old payload, rewrap, `credential_rewrap` CAS; revision unchanged |
| `revoke(..., expected_revision, expected_storage)` | irreversible `credential_revoke` CAS; no plaintext required |

Function inputs use placeholders and canonical ciphertext-only envelope JSON.
Register first verifies owner/revision and the authenticated database context,
then seals. Current records reconstruct every AAD field solely from authoritative
database metadata. Writes verify returned binding, storage version and exact
canonical envelope before transaction commit. Replacement and rewrap require
both caller-observed revision and storage version and authenticate the entire
current envelope before producing a new one. SQL locks and atomic CAS handle
concurrent calls; conflicts fail without a blind retry.
If a transport failure occurs during commit, its outcome may be unknown:
reconcile authoritative database state before attempting another mutation.

Create/read/replace/rewrap require a usable Classic Bitget read-only account.
Paused accounts can still be revoked as a protective action; database ownership,
active user and owner/trader authorization remain required. Revoke neither
deletes nor reactivates a connection. Reading revoked/unowned data is rejected
by SQL; there is no list operation or plaintext database column here.

`read` returns private `OpenedCredential(snapshot, payload)`; `payload.reveal()`
is explicitly for trusted server use. `StoredSnapshot` contains only an immutable
binding, storage version, active status and ciphertext envelope. Snapshot/client
repr is redacted, pickle/dataclass serialization is denied, and no logger is
implemented. SQLSTATEs 42501/40001/23505/22023 map to static access/conflict/
identity/record codes; unknown driver errors map to unavailable. Provider/driver
messages, DSNs, SQL parameters and secret bytes are never copied into errors.

Expected revision prevents stale normal updates when authoritative current
database state is trusted. It does not detect an attacker restoring the database
and ciphertext together to a mutually consistent older state. Revocation blocks
future database reads; it cannot erase plaintext already returned into memory
or prevent a later dispatch race by itself. Future locking/revalidation before
broker dispatch is required. KEK provisioning, process/root isolation, memory
wiping, real credentials, actual broker verification, physical browser MFA
acceptance and browser credential intake/executor HTTP remain pending. The onboarding layer below
checks the assertion/probe contract with synthetic fixtures; the persistence
primitive itself does not establish those higher-level proofs.

## Onboarding contract

`BitgetOnboarding` in `investalo_credential_store.onboarding` takes trusted
`StoreContext`, keyring, connection factory, `RequestVerifier`, transport and
one server-configured egress IP. `apply(action, token=..., body=...)` supports
only `register`, `replace` and `revoke`. It never creates a network transport
implicitly. Account provisioning is administrative and precedes registration.

`RequestVerifier` requires a separately provisioned BFF-to-credential HS256 key,
exact audience `investalo-credentials`, issuer `investalo-bff`, and configured
OIDC issuer. Every assertion binds POST, the exact `/v1/credentials/bitget/ACTION`
target and SHA256 of the unchanged body. These are contract targets, not
implemented HTTP routes. Strict canonical UUIDs, integer times/epoch, unique
bounded AMR including `mfa`, and exact claims are required. Token lifetime is at
most 60 seconds; authentication must be within 120 seconds and at or after
`step_up_started_at`, whose age is at most 300 seconds. Future skew is at most 5
seconds and never excuses authentication predating step-up.

Bodies contain canonical `platform_account_id` and `connection_id` UUIDs.
Register/replace additionally contain `credentials` with exactly `api_key`,
`secret`, `passphrase`; replace/revoke additionally require positive
`expected_revision`, `expected_storage`. Revoke accepts no credentials.
Unknown fields, duplicate keys, unsafe strings, excessive sizes and
browser-selected UID/egress configuration are rejected.

Migration 004 commits a globally unique JTI and static authorization audit before
the private accountinfo probe. Issuer/subject/epoch must match the actual
SESSION_USER-bound DB user. The existing adapter checks Classic schema, read
rights and IP; onboarding additionally requires the whitelist to contain exactly
the configured IP. Register learns UID/parent from that probe. Replacement must
preserve the current stored UID/parent and both observed versions.

After the probe, grant lock, current actor/epoch/reauth/account/time checks,
store mutation and terminal audit run in one transaction. The grant's transaction
marker and final stored state prevent a completion receipt without the matching
write. Failure consumes the JTI permanently; a failed audit is best-effort after
rollback, so a crash can leave an authorized-but-consumed row. Reusing its signed
request never re-dispatches the probe. Unknown commit outcomes require
reconciliation, not automatic retry. Revoke can protect a paused account without
decrypting old credentials or contacting Bitget.

SQL trusts this service to verify signatures and MFA; it does not validate JWTs
or prove a browser interaction. Migration 003's direct private store functions
remain trusted server primitives. This contract does not impose MFA on every
possible direct SQL call. The existing BFF login/assertion is insufficient for
this new action contract: it still needs an action-bound browser flow, separate
signing identity, CSRF checks and final user-facing authorization. No such
endpoint is enabled by this checkpoint.

The explicit `OnboardingResult.public()` projects only connection UUID,
revision, storage version and status. It contains no UID, KEK, envelope or triple.
Private codec `bitget_payload.encode_credentials/decode_credentials` preserves
exact signing bytes in canonical `bitget-credentials/1` JSON inside `SecretPayload`.
It rejects unsafe controls, extras, duplicates and noncanonical stored JSON.

## Isolated passkey assertion contract (IP-038)

`passkey_request_assertion.py` verifies a separate assertion audience
`investalo-credentials-passkey` and authorization kind
`passkey-credential-authorization/1`. The matching trusted TypeScript signer
is `apps/cockpit/src/lib/passkey-credential-token.ts`; the existing signer,
`RequestVerifier`, onboarding executor and migration004 remain unchanged.

This contract requires three distinct purpose-bound authorization/proof/grant
IDs, trusted actor and original OIDC/session context, separate fresh passkey and
receipt times, exact target/CAS, unchanged raw-body SHA256 and an opaque frozen
metadata digest. It does not fabricate `amr` or replace OIDC authentication time.
Origins must be canonical HTTPS DNS origins without paths or explicit default
port 443. Key/secret/passphrase limits are 256/1024/256 UTF-8 bytes; CAS values
require strict integer wire lexemes. JWT validity is at most 60 seconds and never
extends beyond passkey freshness of 120 seconds, the original session or the receipt.

Signing and verification remain repeatable authentication primitives without
persistence or execution. Existing007 proof-only confirmations cannot mint this
token kind. IP-039 adds the separate durable boundary below; the signer/verifier
and legacy003/004 contracts remain unchanged.
[Contract and remaining gates](../../docs/passkey-credential-assertions.md).

## Durable purpose authorization boundary (IP-039)

Additive008 freezes credential purpose and raw-body/metadata digests at prepare,
then requires explicit authorization from a still-granted007 proof.
An already confirmed proof-only receipt cannot be converted into credential
consent. The private receipt matches the IP-038 contract, including immutable
actor/session/original OIDC, factor, Origin/RP and exact target/CAS.

`passkey_authorization.PasskeyAuthorizationClient` requires the private Python
verifier before DB access and a dedicated SESSION_USER-bound credential LOGIN.
`consume` returns a private handle only after acknowledged global one-use
authorization/proof consumption commits. `lock` uses that same handle in a
separate transaction and rechecks current authority, factor, metadata/CAS and
time for a future final write. A successful final-lock commit is terminal;
rechecking within that same final transaction is allowed. Unknown commits return
no handle and are never retried automatically. SQL trusts the mandatory verifier and trusted BFF
cryptographic verdict; it does not verify signatures itself.

Reviewed008 DDL and actual runtime prepare passed in a fully rolled-back
preflight.008 is applied only to `investalo_credentials_checks`;
`investalo` remains001–007; applied008 is checksum-protected and immutable.
This client supplies no003/004 executor, credential mutation, broker transport or
HTTP route. IP-040 connects it to the separate private executor below.
[Contract and acceptance gates](../../docs/passkey-credential-authorizations.md).

## Private passkey-authorized execution (IP-040)

`passkey_onboarding.PasskeyBitgetOnboarding` connects verified purpose receipts
to008 consumption, the Classic identity probe and the existing003 AEAD store.
It requires trusted original session context, verifier, keyring, transactional
connection factory, explicitly injected transport and fixed egress IP.
Register/replace require the same read-only rights, exact IP whitelist and
UID/Parent checks as the legacy core; replacement preserves broker identity.
Consumption must commit before any old-key read or probe.

008's separate final lock,003 store mutation and009 terminal completion audit
share one transaction.009 verifies the permitted final revision/storage/status,
current actor/session/factor/account and expiry after the audit insert.
Write, audit or expiry failure rolls back the whole final transaction while
the earlier consumption remains committed. Failure audit is best effort after
rollback; unknown commits never return success or trigger automatic retries.
Revoke uses neither decryption nor a broker probe and supports paused accounts.
Public results expose only connection ID, revision, storage version and status.

001–008 remain unchanged.009 DDL and actual failed completion using the same
LOGIN as committed synthetic008 consumption passed a fully rolled-back preflight.
009 is applied only to `investalo_credentials_checks`; `investalo` remains001–007.
Pinned migrate/storage/API-check builds and 356 credential checks passed,
including 221 actual PostgreSQL cases. No HTTP caller, real keys,
configured real-broker transport or public activation is added. Physical-device/
email acceptance, dedicated operational identity, key provider, egress/quotas,
recovery and pilot operation remain separate gates.
[Execution contract](../../docs/passkey-credential-execution.md).

## Private Cockpit orchestration and purpose API (IP-041)

The injected `passkey-credential-flow.ts` now joins008 purpose preparation,
007 crypto/claim/grant, explicit008 consent, the separate TS signer and a
private executor port. Exact body bytes stay with the trusted caller; handle
storage retains only digests and correlation. The existing verifier and
`PasskeyBitgetOnboarding` still enforce signature verification, committed
consumption before probing, final locks and atomic completion themselves.

The two internal API routes under `/v1/passkey-credential-authorizations/`
are absent by default. `API_PASSKEY_CREDENTIAL_AUTHORIZATIONS=1` enables only
prepare/authorize with a configured canonical HTTPS `API_PASSKEY_ORIGIN`
matching the RP. They take a body digest, never raw credential bodies.
The private receipt preserves original OIDC time and separates passkey check
and consent times. No credential executor HTTP endpoint, browser intake,
operational signing identity/provider, real keys or broker transport is installed.
Applied001–009 and the running public preview remain unchanged;008/009 stay
fixture-only. [Flow and remaining gates](../../docs/passkey-credential-cockpit.md).

## Injected development HTTPS transport

IP-042 adds the injected development-only `private_http` adapter. A dedicated
client CA and mandatory peer certificate SHA256 pin authenticate the BFF before
HTTP parsing. Its exact seven-field original-session context is independent
of the opaque passkey JWT and must match the fixed `StoreContext` actor.
Three fixed POST paths forward unchanged body bytes to the existing executor.
No provider, runtime launcher, public route or real broker is enabled.
The stdlib server is a development test boundary, not a production HTTP stack.
The matching private TS client uses independent mTLS and never retries an
uncertain response. [Transport contract](../../docs/passkey-credential-https.md).

## Development file provider

IP-043 adds `development_runtime` and a separate opt-in fixture container.
The launcher requires `--development`, fixed UID10003, owned pinned files,
the fixture-only database and bound credential LOGIN. Startup verifies actual
role/context and008/009 capabilities before opening the mTLS listener.
Ambient `PG*` options are rejected. Exact synthetic credential canaries are
required before verification or durable consumption; no real broker transport
exists. Administrative fixture credentials and the BFF client private key
are absent from this container. This remains a development server/provider.
[Service boundary and validation](../../docs/credential-development-service.md).

IP-044 changes only this synthetic launcher's HTTP engine to `private_asgi`,
using the existing Uvicorn0.54.0/h11 pins. Controlled accepted sockets bound
TLS before parsing, with mandatory peer pin and a raw-header guard before h11
normalization. Executor work remains independently bounded until its actual
future finishes, including after socket disconnect. No blind retry, real
credential intake, provider or production activation is added.
[ASGI contract and upgrade coupling](../../docs/credential-asgi-transport.md).

IP-045 adds a separate three-phase browser controller and bounded BFF
continuations without stored credential bodies. Its synthetic internal HTTPS
fixture exercises registration, replacement and revocation through this
restricted service. Next routes remain unavailable without provisioned BFF
providers; actual Next sessions, physical authenticators and operational
identities remain separate acceptance gates.
[Browser contract and fixture limits](../../docs/credential-browser-flow.md).

`keyfiles.DevelopmentKeyFileProvider` requires explicit `development_mode=True`.
Trusted server configuration fixes directory, `KeyFile(version_id, basename,
sha256_fingerprint)` entries and active version. The directory must be owned by
the configured UID with mode 0700; each file must be a regular single-link file,
owned by that UID, mode 0400 and exactly 32 bytes. Descriptor-relative reads use
NOFOLLOW/CLOEXEC/NONBLOCK, bounded reads and checked fingerprints before creating
the existing keyring. Fingerprint configuration must remain independently
trusted across restarts. No key generator, automatic rotation, usage ledger or
external provider is implemented. Parent path resolution and configuration are
trusted deployment inputs. VM-root control defeats this local boundary.

## Checks

Offline tests (host must provide its pinned environment):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/credentials/src:packages/credentials/src packages/credentials/.venv/bin/python -m unittest discover -s tests/credential_store -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/credentials/src:packages/credentials/src:integrations/bitget/src packages/credentials/.venv/bin/python -m unittest discover -s tests/credential_onboarding -v
```

The fake connection verifies fixed SQL/parameter contracts, rollback behavior,
ownership and concurrency/error paths. Actual PostgreSQL/RLS tests are separate;
passing offline tests is not proof of database policy or real account connectivity.
The hardened Compose check runs the client and onboarding units alongside actual
PostgreSQL authorization and AEAD onboarding flows: 120 tests passed (19 client,
41 onboarding units, 60 actual PostgreSQL cases). Only synthetic signing keys,
development KEK files and mocked broker responses are used. Fixture setup:
[infra/README.md](../../infra/README.md). Its administrative test credentials
are distinct from a future runtime credential service. No real broker test.

IP-038: 77 offline onboarding tests passed (41 existing plus 36 new).
109 actual offline TS/Jose→Python checks cover all three actions, Unicode,
whitespace, short expiry, safe-integer boundaries and rejection across the
legacy/new audiences. These do not exercise a durable DB consumer or broker.
All77 offline tests also passed in the pinned Python3.14.10 checkcontainer,
with no network, secrets, mounts, ports or DB dependencies.
During IP-038, the historical 120 credential and 461 API/worker cases were
not rerun.

IP-039: 271 credential tests passed: 19 client, 95 offline onboarding (18 new client
cases) and 157 actual PostgreSQL cases (97 new008 cases). These include all three
actions through actual receipt→HMAC→verifier→private client consume/lock and 92
SQL lifecycle cases. Pinned migrate/storage/API-check builds passed; 461 actual
API/worker checks were rerun and passed. The historical 333 Cockpit and 109
TS/Jose→Python checks from IP-038 were not rerun; the TS signer is unchanged.
No final credential writer or actual broker was exercised in IP-039.

IP-040: 356 tests passed in the pinned checkcontainer: 19 client, 116 offline
onboarding (21 new executor cases) and 221 actual PostgreSQL (64 new cases:
48 completion and 16 executor). All009 cases passed; the complete run took 153.42s.
009 preflight, fixture-only application and pinned migrate/storage/API-check
builds passed. Only synthetic assertions, keys and injected broker responses
were used; no actual broker or real-key acceptance.
The 461 API/worker checks also passed against fixture009, giving 817 current
checks in total. API code was unchanged. Historical 333 Cockpit/109 interop
results remain IP-038 and were not rerun; the TS signer is unchanged.
