"""Offline fake connection; real envelope crypto, no SQL policy proof or I/O."""
import copy
import dataclasses
import json
import pickle
import unittest
from uuid import UUID
from unittest.mock import patch

from investalo_credentials import AADBinding, KEKRing, SecretPayload, seal, dump_envelope
from investalo_credential_store import (
    CredentialStore, ErrorCode, StoreContext, StoreRejected,
)
from investalo_credential_store.client import (
    ROLE_SQL, CONTEXT_SQL, CREATE_SQL, READ_SQL, REPLACE_SQL, REWRAP_SQL, REVOKE_SQL,
)

TENANT, USER, ACCOUNT, CONNECTION = (UUID(int=i) for i in (1, 2, 3, 4))
KEY_1, KEY_2 = bytes(range(32)), bytes(range(32, 64))
PAYLOAD = b"synthetic-private-triple"
SECOND = b"synthetic-replacement-triple"


def binding(**overrides):
    return AADBinding(**{
        "tenant_id": TENANT, "user_id": USER, "platform_account_id": ACCOUNT,
        "connection_id": CONNECTION, "broker_uid": "123456", "parent_uid": "0",
        "credential_revision": 1, **overrides,
    })


def keyring(active="kek-1"):
    return KEKRing((("kek-1", KEY_1), ("kek-2", KEY_2)), active_version=active)


class PGFailure(Exception):
    def __init__(self, state):
        self.sqlstate = state
        super().__init__("synthetic postgres://private:password@host secret-driver-body")


class FakeDB:
    def __init__(self):
        self.role = ("credential_a", "credential_a", False, False, False, False, False, True)
        self.context = (TENANT, USER)
        self.autocommit = False
        self.rows = {}
        self.peer_committed = {}
        self.log = []
        self.commits = self.rollbacks = self.opens = self.closes = 0
        self.fail = {}
        self.return_change = None
        self.race = False
        self.paused = False
        self.commit_failure = False

    def connect(self):
        self.opens += 1
        return FakeConnection(self)

    def store(self, ring=None, **context):
        return CredentialStore(
            StoreContext(tenant_id=context.get("tenant_id", TENANT),
                         user_id=context.get("user_id", USER),
                         expected_login_role=context.get("expected_login_role", "credential_a")),
            ring or keyring(), connect=self.connect)


class FakeConnection:
    def __init__(self, db):
        self.db = db
        self.autocommit = db.autocommit

    def __enter__(self):
        self.original = copy.deepcopy(self.db.rows)
        self.db.peer_committed = {}
        return self

    def __exit__(self, exc_type, exc, tb):
        self.db.closes += 1
        if exc_type or self.db.commit_failure:
            self.db.rows = self.original
            # A separate actor's committed change survives our rollback.
            self.db.rows.update(self.db.peer_committed)
            self.db.rollbacks += 1
            if not exc_type:
                raise PGFailure("08006")
        else:
            self.db.commits += 1

    def cursor(self):
        return FakeCursor(self.db)


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.result = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def fetchone(self):
        return self.result.pop(0) if self.result else None

    def execute(self, sql, params=()):
        self.db.log.append((sql, params))
        if sql in self.db.fail:
            raise self.db.fail[sql]
        if sql == ROLE_SQL:
            self.result = [self.db.role]
            return
        if sql == CONTEXT_SQL:
            self.result = [self.db.context]
            return
        if sql == CREATE_SQL:
            account, connection, uid, parent, encrypted = params
            if self.db.paused:
                raise PGFailure("42501")
            if connection in self.db.rows:
                raise PGFailure("23505")
            row = (*self.db.context, account, connection, uid, parent, "bitget",
                   "classic_v2", "real_read_only", 1, 1, "active", json.loads(encrypted))
        else:
            connection = params[0]
            row = self.db.rows.get(connection)
            if row is None or row[:2] != self.db.context or row[11] != "active":
                raise PGFailure("42501")
            if sql != REVOKE_SQL and self.db.paused:
                raise PGFailure("42501")
            if sql == READ_SQL:
                self.result = [row]
                return
            if sql not in (REPLACE_SQL, REWRAP_SQL, REVOKE_SQL):
                raise AssertionError("Unapproved SQL")
            _, revision, storage, *encrypted = params
            if self.db.race:
                row = (*row[:10], row[10] + 1, *row[11:])
                self.db.rows[connection] = row
                self.db.peer_committed[connection] = row
            if (revision, storage) != (row[9], row[10]):
                raise PGFailure("40001")
            if sql == REVOKE_SQL:
                self.db.rows[connection] = (*row[:10], storage + 1, "revoked", row[12])
                self.result = [(storage + 1,)]
                return
            row = (*row[:9], revision + (sql == REPLACE_SQL), storage + 1,
                   "active", json.loads(encrypted[0]))
        self.db.rows[connection] = row
        result = self.db.return_change(row) if self.db.return_change else row
        self.result = [result]


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.store = self.db.store()

    def rejected(self, code, action):
        with self.assertRaises(StoreRejected) as caught:
            action()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), code.value)
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn("password", repr(caught.exception))
        self.assertNotIn(PAYLOAD.decode(), str(caught.exception))
        return caught.exception

    def registered(self):
        return self.store.register(binding(), SecretPayload(PAYLOAD))

    def test_register_and_read_fixed_sql_ciphertext_only(self):
        registered = self.registered()
        opened = self.store.read(CONNECTION)
        self.assertEqual(opened.payload.reveal(), PAYLOAD)
        self.assertEqual(registered.binding.credential_revision, 1)
        self.assertEqual(registered.storage_version, 1)
        self.assertEqual([entry[0] for entry in self.db.log],
                         [ROLE_SQL, CONTEXT_SQL, CREATE_SQL, ROLE_SQL, CONTEXT_SQL, READ_SQL])
        create_params = self.db.log[2][1]
        self.assertEqual(create_params[:4], (ACCOUNT, CONNECTION, "123456", "0"))
        self.assertNotIn(PAYLOAD.decode(), create_params[4])
        self.assertEqual(self.db.commits, 2)
        self.assertEqual(self.db.opens, self.db.closes)

    def test_login_role_dangerous_flags_current_role_and_login_capability(self):
        for index in range(2, 7):
            db = FakeDB()
            role = list(db.role)
            role[index] = True
            db.role = tuple(role)
            self.rejected(ErrorCode.ACCESS_DENIED, lambda: db.store().read(CONNECTION))
            self.assertEqual([q for q, _ in db.log], [ROLE_SQL])
        for role in (("foreign_login", "foreign_login", False, False, False, False, False, True),
                     ("credential_a", "assumed_role", False, False, False, False, False, True),
                     ("credential_a", "credential_a", False, False, False, False, False, False),
                     ("credential_a", "credential_a", 0, False, False, False, False, True)):
            db = FakeDB()
            db.role = role
            self.rejected(ErrorCode.ACCESS_DENIED, lambda: db.store().read(CONNECTION))

    def test_db_context_not_caller_owner_establishes_authorization(self):
        for identity in ((TENANT, UUID(int=999)), (UUID(int=999), USER), ("1", "2")):
            db = FakeDB()
            db.context = identity
            with patch("investalo_credential_store.client.seal") as encrypt:
                self.rejected(ErrorCode.ACCESS_DENIED, lambda: db.store().register(
                    binding(), SecretPayload(PAYLOAD)))
                encrypt.assert_not_called()
            self.assertEqual([q for q, _ in db.log], [ROLE_SQL, CONTEXT_SQL])
        self.db.fail[CONTEXT_SQL] = PGFailure("42501")
        self.rejected(ErrorCode.ACCESS_DENIED, lambda: self.registered())
        self.assertEqual(self.db.rows, {})

    def test_register_caller_owner_and_initial_revision_rejected_before_connect(self):
        for changed in (binding(user_id=UUID(int=99)), binding(tenant_id=UUID(int=99))):
            self.rejected(ErrorCode.ACCESS_DENIED,
                          lambda: self.store.register(changed, SecretPayload(PAYLOAD)))
        self.rejected(ErrorCode.INVALID_RECORD,
                      lambda: self.store.register(binding(credential_revision=2), SecretPayload(PAYLOAD)))
        self.assertEqual(self.db.opens, 0)

    def test_autocommit_rejected_before_sql(self):
        self.db.autocommit = True
        self.rejected(ErrorCode.INVALID_CONTEXT, lambda: self.registered())
        self.assertEqual(self.db.log, [])
        self.assertEqual(self.db.rollbacks, 1)

    def test_read_metadata_is_authoritative_for_every_binding_field(self):
        self.registered()
        original = self.db.rows[CONNECTION]
        changed_fields = {
            2: UUID(int=999), 4: "777", 5: None, 9: 2,
        }
        for index, value in changed_fields.items():
            row = list(original)
            row[index] = value
            self.db.rows[CONNECTION] = tuple(row)
            self.rejected(ErrorCode.AUTHENTICATION_FAILED, lambda: self.store.read(CONNECTION))
        for index, value in ((0, UUID(int=999)), (1, UUID(int=999)), (3, UUID(int=999)),
                             (11, "revoked")):
            row = list(original)
            row[index] = value
            self.db.rows[CONNECTION] = tuple(row)
            self.rejected(ErrorCode.ACCESS_DENIED, lambda: self.store.read(CONNECTION))

    def test_replace_authenticates_old_and_increments_both_versions(self):
        self.registered()
        updated = self.store.replace(CONNECTION, expected_revision=1, expected_storage=1,
                                     payload=SecretPayload(SECOND))
        self.assertEqual(updated.binding.credential_revision, 2)
        self.assertEqual(updated.storage_version, 2)
        self.assertEqual(self.store.read(CONNECTION).payload.reveal(), SECOND)
        self.assertEqual(updated.binding.broker_uid, "123456")
        self.assertEqual(updated.binding.parent_uid, "0")
        self.rejected(ErrorCode.CONCURRENT_CHANGE, lambda: self.store.replace(
            CONNECTION, expected_revision=1, expected_storage=1, payload=SecretPayload(PAYLOAD)))
        self.assertEqual(self.db.rows[CONNECTION][9:11], (2, 2))

    def test_tampered_current_envelope_blocks_replace_and_rewrap_before_new_seal(self):
        self.registered()
        original = self.db.rows[CONNECTION]
        raw = copy.deepcopy(original[12])
        raw["ciphertext"] = ("A" if raw["ciphertext"][0] != "A" else "B") + raw["ciphertext"][1:]
        self.db.rows[CONNECTION] = (*original[:12], raw)
        with patch("investalo_credential_store.client.seal") as encrypt:
            self.rejected(ErrorCode.AUTHENTICATION_FAILED, lambda: self.store.replace(
                CONNECTION, expected_revision=1, expected_storage=1, payload=SecretPayload(SECOND)))
            encrypt.assert_not_called()
        self.rejected(ErrorCode.AUTHENTICATION_FAILED, lambda: self.store.rewrap(
            CONNECTION, expected_revision=1, expected_storage=1))
        self.assertFalse(any(sql in (REPLACE_SQL, REWRAP_SQL) for sql, _ in self.db.log))

    def test_rewrap_preserves_revision_payload_and_nonce_but_cas_storage_increments(self):
        original = self.registered()
        rotating_store = self.db.store(keyring(active="kek-2"))
        revised = rotating_store.rewrap(CONNECTION, expected_revision=1, expected_storage=1)
        self.assertEqual(revised.binding.credential_revision, 1)
        self.assertEqual(revised.storage_version, 2)
        self.assertEqual(revised.envelope.ciphertext, original.envelope.ciphertext)
        self.assertEqual(revised.envelope.payload_nonce, original.envelope.payload_nonce)
        self.assertEqual(revised.envelope.kek_id, "kek-2")
        self.assertEqual(rotating_store.read(CONNECTION).payload.reveal(), PAYLOAD)
        self.rejected(ErrorCode.CONCURRENT_CHANGE, lambda: rotating_store.rewrap(
            CONNECTION, expected_revision=1, expected_storage=1))

    def test_competing_cas_change_rolls_back_and_never_retries(self):
        self.registered()
        self.db.race = True
        self.rejected(ErrorCode.CONCURRENT_CHANGE, lambda: self.store.replace(
            CONNECTION, expected_revision=1, expected_storage=1, payload=SecretPayload(SECOND)))
        self.assertEqual(sum(sql == REPLACE_SQL for sql, _ in self.db.log), 1)
        self.assertEqual(self.db.rows[CONNECTION][9:11], (1, 2))
        self.assertEqual(self.db.rollbacks, 1)

    def test_mismatched_written_metadata_or_blob_rolls_back_register(self):
        changes = {
            2: UUID(int=99), 4: "999", 5: None, 9: 2, 10: 2,
        }
        other_ciphertext = json.loads(dump_envelope(seal(SecretPayload(SECOND), binding(), keyring())))
        changes[12] = other_ciphertext
        for index, value in changes.items():
            db = FakeDB()
            def changed(row):
                modified = list(row)
                modified[index] = value
                return tuple(modified)
            db.return_change = changed
            self.rejected(ErrorCode.INVALID_RECORD, lambda: db.store().register(
                binding(), SecretPayload(PAYLOAD)))
            self.assertEqual(db.rows, {})
            self.assertEqual(db.rollbacks, 1)

    def test_foreign_written_owner_rolls_back(self):
        self.db.return_change = lambda row: (UUID(int=99), *row[1:])
        self.rejected(ErrorCode.ACCESS_DENIED, lambda: self.registered())
        self.assertEqual(self.db.rows, {})
        self.assertEqual(self.db.commits, 0)

    def test_mismatched_cas_return_storage_rolls_back_replace(self):
        self.registered()
        self.db.return_change = lambda row: (*row[:10], row[10] + 1, *row[11:])
        self.rejected(ErrorCode.INVALID_RECORD, lambda: self.store.replace(
            CONNECTION, expected_revision=1, expected_storage=1, payload=SecretPayload(SECOND)))
        self.assertEqual(self.db.rows[CONNECTION][9:11], (1, 1))
        self.db.return_change = None
        self.assertEqual(self.store.read(CONNECTION).payload.reveal(), PAYLOAD)

    def test_paused_account_blocks_reads_but_revoke_needs_no_read_or_decrypt(self):
        self.registered()
        self.db.paused = True
        self.rejected(ErrorCode.ACCESS_DENIED, lambda: self.store.read(CONNECTION))
        # No old KEK: protective revoke must still work.
        missing_key_store = self.db.store(KEKRing((("kek-2", KEY_2),), active_version="kek-2"))
        offset = len(self.db.log)
        with patch("investalo_credential_store.client.open_envelope") as decrypt:
            self.assertEqual(missing_key_store.revoke(
                CONNECTION, expected_revision=1, expected_storage=1), 2)
            decrypt.assert_not_called()
        self.assertEqual([q for q, _ in self.db.log[offset:]], [ROLE_SQL, CONTEXT_SQL, REVOKE_SQL])
        self.assertEqual(self.db.rows[CONNECTION][11], "revoked")
        self.rejected(ErrorCode.ACCESS_DENIED, lambda: self.store.revoke(
            CONNECTION, expected_revision=1, expected_storage=2))
        self.rejected(ErrorCode.ACCESS_DENIED, lambda: self.store.read(CONNECTION))

    def test_sqlstate_mapping_and_connect_commit_error_chain_static(self):
        for state, code in (
            ("42501", ErrorCode.ACCESS_DENIED), ("40001", ErrorCode.CONCURRENT_CHANGE),
            ("23505", ErrorCode.IDENTITY_CONFLICT), ("22023", ErrorCode.INVALID_RECORD),
            ("08006", ErrorCode.UNAVAILABLE), (None, ErrorCode.UNAVAILABLE)):
            db = FakeDB()
            db.fail[ROLE_SQL] = PGFailure(state)
            error = self.rejected(code, lambda: db.store().read(CONNECTION))
            self.assertTrue(error.__suppress_context__)
        def fail_connect():
            raise PGFailure("08006")
        client = CredentialStore(self.store._context, keyring(), connect=fail_connect)
        error = self.rejected(ErrorCode.UNAVAILABLE, lambda: client.read(CONNECTION))
        self.assertTrue(error.__suppress_context__)
        self.db.commit_failure = True
        self.rejected(ErrorCode.UNAVAILABLE, lambda: self.registered())
        self.assertEqual(sum(sql == CREATE_SQL for sql, _ in self.db.log), 1)

    def test_unknown_or_missing_kek_maps_safe_without_payload(self):
        self.registered()
        missing = self.db.store(KEKRing((("kek-2", KEY_2),), active_version="kek-2"))
        self.rejected(ErrorCode.KEY_UNAVAILABLE, lambda: missing.read(CONNECTION))
        wrong = self.db.store(KEKRing((("kek-1", KEY_2),), active_version="kek-1"))
        self.rejected(ErrorCode.AUTHENTICATION_FAILED, lambda: wrong.read(CONNECTION))

    def test_snapshot_secret_client_representations_and_serialization_redacted(self):
        registered = self.registered()
        opened = self.store.read(CONNECTION)
        for value in (self.store, self.store._context, registered, opened, opened.payload):
            printed = repr(value) + str(value)
            for secret in (PAYLOAD.decode(), "123456", KEY_1.hex(), "password"):
                self.assertNotIn(secret, printed)
            for operation in (pickle.dumps, dataclasses.asdict):
                with self.assertRaises(TypeError):
                    operation(value)
            self.assertFalse(hasattr(value, "__dict__"))
        with self.assertRaises(AttributeError):
            registered.storage_version = 999

    def test_invalid_identifiers_context_and_versions_cannot_dispatch_sql(self):
        for uuid in (str(CONNECTION), None, 4, "SQL injection"):
            self.rejected(ErrorCode.INVALID_RECORD, lambda: self.store.read(uuid))
        for revision, storage in ((0, 1), (1, 0), (True, 1), (1, True), ("1", 1), (1, 2**63 - 1)):
            self.rejected(ErrorCode.INVALID_RECORD, lambda: self.store.replace(
                CONNECTION, expected_revision=revision, expected_storage=storage,
                payload=SecretPayload(SECOND)))
        for role in ("", "bad role", "a;drop", "A", "x" * 64):
            self.rejected(ErrorCode.INVALID_CONTEXT, lambda: StoreContext(
                tenant_id=TENANT, user_id=USER, expected_login_role=role))
        self.assertEqual(self.db.opens, 0)

    def test_oversized_or_unknown_jsonb_envelope_rejected_without_decrypt(self):
        self.registered()
        original = self.db.rows[CONNECTION]
        for envelope in ({**original[12], "unknown": "field"},
                         {**original[12], "ciphertext": "A" * 10000},
                         {"ciphertext": ["not-a-string"]}, "not-jsonb-object"):
            self.db.rows[CONNECTION] = (*original[:12], envelope)
            with patch("investalo_credential_store.client.open_envelope") as decrypt:
                self.rejected(ErrorCode.INVALID_RECORD, lambda: self.store.read(CONNECTION))
                decrypt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
