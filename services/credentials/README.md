# Credential store client

Isolated Python client for migration 003's fixed PostgreSQL functions, using the
AEAD core in `packages/credentials`. No HTTP/API/CLI, key provider, broker
serializer, file/network launcher or real credentials are added.

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
wiping, real credentials, authenticated broker-UID verification, SDK triple
validation, onboarding, MFA step-up and HTTP authorization
are separate pending work; this client does not claim them.

Offline tests (host must provide its pinned environment):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/credentials/src:packages/credentials/src packages/credentials/.venv/bin/python -m unittest discover -s tests/credential_store -v
```

The fake connection verifies fixed SQL/parameter contracts, rollback behavior,
ownership and concurrency/error paths. Actual PostgreSQL/RLS tests are separate;
passing offline tests is not proof of database policy or real account connectivity.
The hardened Compose check additionally passed 18 real PostgreSQL cases,
including two actual client/crypto/DB flows. Fixture setup and commands:
[infra/README.md](../../infra/README.md). Its administrative test credentials
are distinct from a future runtime credential service. No real broker test.
