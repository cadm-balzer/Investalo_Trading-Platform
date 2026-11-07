# Credential AEAD envelopes

Isolated Python core using the project's pinned `cryptography` AES-GCM library.
No database, API, CLI, file I/O, network, broker serializer or real key test.

`AADBinding` holds trusted UUIDs for tenant, user, platform account and connection,
broker UID, nullable parent UID and positive credential revision. Parent `None`
and string `"0"` are distinct; no broker parent-status inference is made.
Broker/family/mode are exactly `bitget` / `classic_v2` / `real_read_only`.
`SecretPayload` accepts opaque 1–4,096-byte payloads. Triple validation and
serialization live in the separate
[credential service](../../services/credentials/README.md), outside this core.

`KEKRing(entries=((version_id, key_bytes), ...), active_version=...)` accepts
1–32 unique bounded ASCII version IDs and exactly 32 bytes per KEK. Duplicate key
material under different version IDs is rejected within the ring. A version ID
must always identify the same key material across provider restarts and rotation.
The development file provider uses fixed trusted fingerprints for this mapping;
an isolated ring cannot verify its historical continuity. An operational provider
remains unfinished. The active version seals new envelopes; old envelopes
decrypt only while the matching old KEK remains available.

API:

- `seal(payload, binding, keyring) -> Envelope`
- `open_envelope(envelope, expected_binding, keyring) -> SecretPayload`
- `rewrap(envelope, expected_binding, keyring) -> Envelope`
- `dump_envelope(envelope) -> str`
- `load_envelope(str_or_bytes) -> Envelope`

Each seal creates a random 256-bit DEK and independent random 96-bit payload and
wrapping nonces. AES-256-GCM encrypts the payload under the DEK; another
AES-256-GCM wraps that DEK under the versioned KEK. Canonical JSON AAD includes
the envelope format version, every binding field and distinct payload/wrapping
domain markers. Wrapping AAD additionally includes the KEK ID. Payload AAD
excludes the KEK ID so rewrap can preserve its ciphertext and nonce.

Rewrap first authenticates both the old wrapped DEK and the entire old payload,
then uses the active KEK and a fresh wrapping nonce. It returns a new envelope;
the original object and old root keys are not altered or deleted. Storage updates
and concurrency are responsibilities of the separate
[credential store](../../services/credentials/README.md).

Only the explicit dump/load API serializes envelopes; its JSON contains format,
KEK ID, nonces, wrapped DEK and ciphertext, never plaintext or KEKs. Load rejects
unknown/missing/duplicate fields, malformed or noncanonical Base64, invalid
nonces, and oversized documents/fields. Private objects have redacted repr/str
and reject pickle/dataclass serialization. `SecretPayload.reveal()` is an
explicit trusted-service boundary. Static exceptions suppress backend error
chains; no logger is implemented here.

These protections do not provide authorization, tenant database isolation, a
credential vault/service isolation, or resistance to an attacker controlling
the process/root account. Python does not guarantee memory wiping. A future
key provider must supply and protect random KEKs, enforce immutable version
mapping, and support backups/restoration. Loss of all applicable KEKs means loss
of recoverability. Removing old KEKs too early breaks old-envelope recovery.

Revision is authenticated but prevents rollback only when the trusted caller
obtains the expected current revision from authoritative database state, as the
separate credential store does.
The envelope cannot determine freshness by itself. Random nonce collisions have
nonzero probability; future operational key-usage/collision budgets, rotation
limits and monitoring are not implemented here. There is no global nonce
registry, automatic rotation policy or claim of real credential readiness.

Offline tests:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/credentials/src packages/credentials/.venv/bin/python -m unittest discover -s tests/credentials -v
```

The published AES-256-GCM vector and all test keys/payloads are synthetic.
The package uses the pinned
[cryptography 50.0.2 AESGCM API](https://cryptography.io/en/50.0.2/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM).
