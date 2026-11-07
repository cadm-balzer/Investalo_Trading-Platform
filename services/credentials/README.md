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
wiping, real credentials, actual broker verification, browser MFA step-up
and HTTP authorization are separate pending work. The onboarding layer below
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

## Development file provider

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
