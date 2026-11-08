"""Offline orchestration/crypto tests; PostgreSQL policy is proved separately."""
import copy
import dataclasses
import json
import pickle
import unittest
from uuid import UUID
from unittest.mock import patch

from investalo_bitget.signing import INFO_PATH
from investalo_bitget.transport import ReadResponse
from investalo_credentials import KEKRing
from investalo_credential_store.bitget_payload import decode_credentials
from investalo_credential_store.client import (
    CONTEXT_SQL, CREATE_SQL, READ_SQL, REPLACE_SQL, REVOKE_SQL, ROLE_SQL,
)
from investalo_credential_store.models import StoreContext
from investalo_credential_store.passkey_authorization import CONSUME_SQL, LOCK_SQL
from investalo_credential_store.passkey_onboarding import FINISH_SQL, PasskeyBitgetOnboarding
from investalo_credential_store.passkey_request_assertion import PasskeyRequestVerifier
from investalo_credential_store.request_assertion import OnboardingRejected, RequestVerifier
from test_passkey_assertions import (
    ACCOUNT, CONNECTION, ISSUER, KEY, NOW, ORIGIN, SUBJECT, TENANT, TRIPLE, USER,
    fixture_body, fixture_claims, fixture_context, fixture_target, sign_assertion,
)

ROLE, IP = "credential_fixture", "203.0.113.19"
SECOND = {"api_key": "synthetic-replacement-key", "secret": "synthetic-replacement-secret",
          "passphrase": "synthetic-replacement-passphrase"}


class DriverFailure(Exception):
    def __init__(self, state="08006"):
        self.sqlstate = state
        super().__init__("postgres://synthetic-password@fixture synthetic-private-secret")


class Database:
    """Transaction fake does not establish RLS, authority or SQL correctness."""
    def __init__(self):
        self.role = (ROLE, ROLE, False, False, False, False, False, True)
        self.actor = (TENANT, USER)
        self.autocommit = False
        self.rows, self.authorizations, self.finished = {}, {}, {}
        self.calls, self.committed, self.rolled_back = [], [], []
        self.opens = 0
        self.fail, self.responses = {}, {}
        self.unknown_commit = set()
        self.before_finish = None
        self.paused = False

    def connect(self):
        self.opens += 1
        return Connection(self, self.opens)


class Connection:
    def __init__(self, database, number):
        self.database, self.number = database, number
        self.autocommit = database.autocommit

    def __enter__(self):
        self.original = copy.deepcopy((
            self.database.rows, self.database.authorizations, self.database.finished,
        ))
        return self

    def __exit__(self, kind, value, traceback):
        db = self.database
        if kind is not None:
            db.rows, db.authorizations, db.finished = self.original
            db.rolled_back.append(self.number)
        else:
            db.committed.append(self.number)
            if self.number in db.unknown_commit:
                # Deliberately ambiguous: fake commit did persist, then lost its
                # acknowledgement. The executor must never infer rollback.
                raise DriverFailure()
        return False

    def cursor(self):
        return Cursor(self)


class Cursor:
    def __init__(self, connection):
        self.connection, self.result = connection, []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def fetchone(self):
        return self.result.pop(0) if self.result else None

    def execute(self, query, params=()):
        db, number = self.connection.database, self.connection.number
        db.calls.append((number, query, params))
        failure = db.fail.get((query, params[-1])) if query == FINISH_SQL else None
        if failure is None:
            failure = db.fail.get(query)
        if failure is not None:
            raise failure
        if query == ROLE_SQL:
            rows = [db.role]
        elif query == CONTEXT_SQL:
            rows = [db.actor]
        elif query == CONSUME_SQL:
            claims = json.loads(params[0])
            identity = claims["authorization_id"]
            if identity in db.authorizations:
                raise DriverFailure("42501")
            db.authorizations[identity] = (claims, "consumed", number)
            rows = [(UUID(identity),)]
        elif query == LOCK_SQL:
            claims = json.loads(params[0])
            old = db.authorizations.get(claims["authorization_id"])
            if (old is None or old[0] != claims or old[1] != "consumed"
                    or old[2] not in db.committed or db.paused and claims["target"]["action"] != "revoke"):
                raise DriverFailure("42501")
            db.authorizations[claims["authorization_id"]] = (claims, "locked", number)
            rows = [(True,)]
        elif query == FINISH_SQL:
            claims, outcome = json.loads(params[0]), params[1]
            identity = claims["authorization_id"]
            old = db.authorizations.get(identity)
            if (old is None or old[0] != claims or identity in db.finished
                    or outcome == "completed" and old[1:] != ("locked", number)
                    or outcome == "failed" and old[1] != "consumed"):
                raise DriverFailure("42501")
            if db.before_finish:
                db.before_finish(outcome)
            db.finished[identity] = outcome
            rows = [(True,)]
        elif query == CREATE_SQL:
            account, connection, uid, parent, envelope = params
            if connection in db.rows:
                raise DriverFailure("23505")
            row = (*db.actor, account, connection, uid, parent, "bitget",
                   "classic_v2", "real_read_only", 1, 1, "active", json.loads(envelope))
            db.rows[connection] = row
            rows = [row]
        elif query in (READ_SQL, REPLACE_SQL, REVOKE_SQL):
            connection = params[0]
            row = db.rows.get(connection)
            if row is None or row[:2] != db.actor or row[11] != "active":
                raise DriverFailure("42501")
            if query != REVOKE_SQL and db.paused:
                raise DriverFailure("42501")
            if query == READ_SQL:
                rows = [row]
            else:
                revision, storage = params[1:3]
                if row[9:11] != (revision, storage):
                    raise DriverFailure("40001")
                if query == REVOKE_SQL:
                    db.rows[connection] = (*row[:10], storage + 1, "revoked", row[12])
                    rows = [(storage + 1,)]
                else:
                    row = (*row[:9], revision + 1, storage + 1, "active", json.loads(params[3]))
                    db.rows[connection] = row
                    rows = [row]
        else:
            raise AssertionError("Unexpected fixed SQL in offline fixture")
        self.result = list(db.responses.get(query, rows))


class Broker:
    def __init__(self, database):
        self.database, self.calls, self.patch = database, [], {}
        self.before_response = None
        self.uid, self.parent = "123456", None

    def __call__(self, signed):
        if signed.method != "GET" or signed.path != INFO_PATH:
            raise AssertionError("Unexpected broker dispatch")
        # Ordering, not SQL-policy proof: this assertion catches dispatch before
        # an acknowledged consume and before any private write.
        if not self.database.committed:
            raise AssertionError("Probe before consume commit")
        self.calls.append(signed.path)
        if self.before_response:
            self.before_response()
        data = {"userId": self.uid, "parentId": self.parent,
                "authorities": ["stor"], "ips": IP, **self.patch}
        return ReadResponse(200, json.dumps({
            "code": "00000", "requestTime": NOW * 1000, "data": data,
        }).encode())


class PasskeyOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.broker = Broker(self.db)
        self.ring = KEKRing((("synthetic-passkey-kek", bytes(range(32))),),
                            active_version="synthetic-passkey-kek")
        self.service = self.make_service()
        self.sequence = 0

    def make_service(self, **overrides):
        options = {
            "connect": self.db.connect, "verifier": PasskeyRequestVerifier(
                key=KEY, oidc_issuer=ISSUER, origin=ORIGIN, clock=lambda: NOW,
            ), "request_context": fixture_context(), "transport": self.broker,
            "expected_egress_ip": IP,
        }
        options.update(overrides)
        return PasskeyBitgetOnboarding(
            StoreContext(tenant_id=TENANT, user_id=USER, expected_login_role=ROLE),
            self.ring, **options,
        )

    def request(self, action="register", *, revision=1, storage=1, triple=None, **overrides):
        self.sequence += 1
        target = fixture_target(action)
        if action != "register":
            target.update(expected_revision=revision, expected_storage=storage)
        body = fixture_body(action, target=target, triple=triple)
        claims = fixture_claims(
            action, body=body, target=target, authorization_id=str(UUID(int=2000 + self.sequence)),
            proof_id=str(UUID(int=3000 + self.sequence)), grant_id=str(UUID(int=4000 + self.sequence)),
            jti=str(UUID(int=5000 + self.sequence)), **overrides,
        )
        return sign_assertion(claims), body, claims

    def apply(self, action="register", *, service=None, **options):
        token, body, claims = self.request(action, **options)
        result = (service or self.service).apply(action, token=token, body=body)
        return result, claims

    def rejected(self, code, operation):
        with self.assertRaises(OnboardingRejected) as failure:
            operation()
        error = failure.exception
        self.assertEqual(error.code, code)
        self.assertEqual(str(error), code)
        self.assertIsNone(error.__cause__)
        self.assertTrue(error.__suppress_context__)
        for private in (KEY.decode(), SUBJECT, ORIGIN, TRIPLE["secret"],
                        SECOND["secret"], "synthetic-password"):
            self.assertNotIn(private, repr(error) + str(error))

    def test_register_has_committed_consume_then_probe_then_atomic_write_completion(self):
        result, claims = self.apply()
        self.assertEqual(result.public(), {
            "connection_id": CONNECTION, "credential_revision": 1,
            "storage_version": 1, "status": "active",
        })
        self.assertEqual(self.broker.calls, [INFO_PATH])
        self.assertEqual(self.db.committed, [1, 2])
        queries = [query for _, query, _ in self.db.calls]
        self.assertLess(queries.index(CONSUME_SQL), queries.index(LOCK_SQL))
        self.assertLess(queries.index(LOCK_SQL), queries.index(CREATE_SQL))
        self.assertLess(queries.index(CREATE_SQL), queries.index(FINISH_SQL))
        final_numbers = {number for number, query, _ in self.db.calls
                         if query in (LOCK_SQL, CREATE_SQL, FINISH_SQL)}
        self.assertEqual(final_numbers, {2})
        consume = next(params[0] for _, query, params in self.db.calls if query == CONSUME_SQL)
        completed = next(params for _, query, params in self.db.calls if query == FINISH_SQL)
        self.assertEqual(completed, (consume, "completed"))
        self.assertEqual(json.loads(consume), claims)
        self.assertNotIn(TRIPLE["secret"], json.dumps(self.db.rows[UUID(CONNECTION)][12]))

    def test_replace_preserves_bound_identity_and_authenticates_old_ciphertext(self):
        self.apply()
        result, claims = self.apply("replace", triple=SECOND)
        opened = self.service._store.read(UUID(CONNECTION))
        self.assertEqual(decode_credentials(opened.payload)._api_key, SECOND["api_key"])
        self.assertEqual(opened.snapshot.binding.broker_uid, self.broker.uid)
        self.assertEqual((result.credential_revision, result.storage_version), (2, 2))
        self.assertEqual(self.db.finished[claims["authorization_id"]], "completed")
        calls = [q for _, q, _ in self.db.calls]
        second_consume = calls.index(CONSUME_SQL, calls.index(CONSUME_SQL) + 1)
        self.assertLess(second_consume, calls.index(READ_SQL))
        self.assertEqual(len(self.broker.calls), 2)

    def test_paused_revoke_requires_neither_old_key_decryption_nor_probe(self):
        self.apply()
        self.db.paused = True
        original_reads = sum(q == READ_SQL for _, q, _ in self.db.calls)
        original_probes = len(self.broker.calls)
        self.ring = KEKRing((("synthetic-unrelated-kek", b"x" * 32),),
                            active_version="synthetic-unrelated-kek")
        service = self.make_service()
        with patch("investalo_credential_store.client.open_envelope",
                   side_effect=AssertionError("Revocation decrypted old credentials")):
            result, _ = self.apply("revoke", service=service)
        self.assertEqual((result.status, result.credential_revision, result.storage_version),
                         ("revoked", 1, 2))
        self.assertEqual(len(self.broker.calls), original_probes)
        self.assertEqual(sum(q == READ_SQL for _, q, _ in self.db.calls), original_reads)

    def test_invalid_signature_body_and_context_fail_before_db_or_dispatch(self):
        token, body, _ = self.request()
        for invalid_token, invalid_body in (("invalid", body), (token, body + b" "), (token, b"")):
            self.rejected("authentication_required",
                          lambda: self.service.apply("register", token=invalid_token, body=invalid_body))
        self.assertEqual(self.db.opens, 0)
        self.assertEqual(self.broker.calls, [])

    def test_signed_body_with_unsafe_or_client_selected_fields_fails_before_db(self):
        for patch_body in ({"broker_uid": "123"}, {"expected_egress_ip": IP}):
            body = json.loads(fixture_body())
            body.update(patch_body)
            raw = json.dumps(body).encode()
            token = sign_assertion(fixture_claims(body=raw))
            self.rejected("authentication_required",
                          lambda: self.service.apply("register", token=token, body=raw))
        self.assertEqual(self.db.opens, 0)
        self.assertEqual(self.broker.calls, [])

    def test_constructor_rejects_legacy_verifier_untrusted_context_transport_or_ip(self):
        for options in (
            {"verifier": RequestVerifier(key=KEY, oidc_issuer=ISSUER, clock=lambda: NOW)},
            {"request_context": fixture_context(user_id=UUID(int=8000))},
            {"request_context": object()}, {"transport": None},
            {"expected_egress_ip": "https://client-selected.invalid"},
        ):
            self.rejected("invalid_context", lambda: self.make_service(**options))
        self.assertEqual(self.db.opens, 0)

    def test_role_and_context_denial_occurs_before_probe_and_mutation(self):
        self.db.actor = (TENANT, UUID(int=9999))
        token, body, _ = self.request()
        self.rejected("access_denied",
                      lambda: self.service.apply("register", token=token, body=body))
        self.assertEqual(self.broker.calls, [])
        self.assertEqual(self.db.rows, {})
        self.assertEqual(self.db.finished, {})

    def test_unknown_consume_commit_has_no_probe_no_finalization_no_retry(self):
        token, body, _ = self.request()
        self.db.unknown_commit.add(1)
        self.rejected("unavailable",
                      lambda: self.service.apply("register", token=token, body=body))
        self.assertEqual(self.broker.calls, [])
        self.assertEqual(self.db.rows, {})
        self.assertEqual(self.db.opens, 1)
        self.assertEqual(sum(q == CONSUME_SQL for _, q, _ in self.db.calls), 1)
        self.assertFalse(any(q in (LOCK_SQL, FINISH_SQL) for _, q, _ in self.db.calls))

    def test_replay_is_denied_before_any_second_probe_or_write(self):
        token, body, claims = self.request()
        self.service.apply("register", token=token, body=body)
        original_calls = len(self.broker.calls)
        self.rejected("access_denied",
                      lambda: self.service.apply("register", token=token, body=body))
        self.assertEqual(len(self.broker.calls), original_calls)
        self.assertEqual(self.db.finished[claims["authorization_id"]], "completed")

    def test_bad_permissions_or_extra_whitelist_ips_audit_failure_without_write(self):
        for broker_patch in ({"authorities": ["stow"]}, {"ips": IP + ",203.0.113.20"}):
            self.setUp()
            self.broker.patch = broker_patch
            token, body, claims = self.request()
            self.rejected("broker_rejected",
                          lambda: self.service.apply("register", token=token, body=body))
            self.assertEqual(self.db.rows, {})
            self.assertEqual(self.db.finished[claims["authorization_id"]], "failed")
            self.assertFalse(any(q in (LOCK_SQL, CREATE_SQL) for _, q, _ in self.db.calls))

    def test_replacement_probe_cannot_change_current_uid_or_parent(self):
        for broker_patch in ({"userId": "987654"}, {"parentId": "987654"}):
            self.setUp()
            self.apply()
            self.broker.patch = broker_patch
            token, body, claims = self.request("replace", triple=SECOND)
            self.rejected("broker_rejected",
                          lambda: self.service.apply("replace", token=token, body=body))
            self.assertEqual(self.db.rows[UUID(CONNECTION)][9:11], (1, 1))
            self.assertEqual(self.db.finished[claims["authorization_id"]], "failed")

    def test_final_role_or_actor_change_keeps_static_denial_and_rolls_back(self):
        token, body, claims = self.request()
        self.broker.before_response = lambda: setattr(self.db, "actor", (TENANT, UUID(int=7000)))
        self.rejected("access_denied",
                      lambda: self.service.apply("register", token=token, body=body))
        self.assertEqual(self.db.rows, {})
        self.assertEqual(self.db.committed, [1])
        self.assertEqual(self.db.authorizations[claims["authorization_id"]][1], "consumed")

    def test_final_lock_denial_preserves_original_static_code_and_failure_audit(self):
        token, body, claims = self.request()
        self.db.fail[LOCK_SQL] = DriverFailure("42501")
        self.rejected("access_denied",
                      lambda: self.service.apply("register", token=token, body=body))
        self.assertEqual(self.db.rows, {})
        self.assertEqual(self.db.finished[claims["authorization_id"]], "failed")
        self.assertEqual(sum(q == LOCK_SQL for _, q, _ in self.db.calls), 1)

    def test_final_mutation_conflict_rolls_back_lock_and_audits_failure(self):
        token, body, claims = self.request()
        self.db.fail[CREATE_SQL] = DriverFailure("40001")
        self.rejected("concurrent_change",
                      lambda: self.service.apply("register", token=token, body=body))
        self.assertEqual(self.db.rows, {})
        self.assertEqual(self.db.authorizations[claims["authorization_id"]][1], "consumed")
        self.assertEqual(self.db.finished[claims["authorization_id"]], "failed")
        self.assertEqual(self.db.rolled_back, [2])

    def test_completion_denial_rolls_back_credential_and_retains_failure_code(self):
        token, body, claims = self.request()
        self.db.fail[(FINISH_SQL, "completed")] = DriverFailure("42501")
        self.db.fail[(FINISH_SQL, "failed")] = DriverFailure()
        self.rejected("access_denied",
                      lambda: self.service.apply("register", token=token, body=body))
        self.assertEqual(self.db.rows, {})
        self.assertEqual(self.db.authorizations[claims["authorization_id"]][1], "consumed")
        self.assertEqual(self.db.finished, {})
        self.assertEqual(self.db.committed, [1])
        self.assertEqual(self.db.rolled_back, [2, 3])

    def test_completion_nonboolean_success_also_rolls_back_write(self):
        for rows in ([], [(False,)], [(1,)], [(True,), (True,)]):
            self.setUp()
            token, body, claims = self.request()
            self.db.responses[FINISH_SQL] = rows
            self.rejected("invalid_record",
                          lambda: self.service.apply("register", token=token, body=body))
            self.assertEqual(self.db.rows, {})
            self.assertEqual(self.db.finished, {})
            self.assertEqual(self.db.authorizations[claims["authorization_id"]][1], "consumed")

    def test_unknown_final_commit_returns_no_success_and_never_overwrites_completion(self):
        token, body, claims = self.request()
        self.db.unknown_commit.add(2)
        self.rejected("unavailable",
                      lambda: self.service.apply("register", token=token, body=body))
        # The fake deliberately persists this ambiguous commit. Retrying would
        # double dispatch or overwrite the actual successful terminal audit.
        self.assertEqual(self.db.rows[UUID(CONNECTION)][9:12], (1, 1, "active"))
        self.assertEqual(self.db.finished[claims["authorization_id"]], "completed")
        self.assertEqual(self.broker.calls, [INFO_PATH])
        self.assertEqual(sum(q == CREATE_SQL for _, q, _ in self.db.calls), 1)
        self.assertEqual(sum(q == LOCK_SQL for _, q, _ in self.db.calls), 1)
        self.assertEqual(sum(q == CONSUME_SQL for _, q, _ in self.db.calls), 1)

    def test_replace_stale_versions_are_denied_after_consume_before_probe(self):
        self.apply()
        token, body, claims = self.request("replace", revision=2, storage=2)
        before = len(self.broker.calls)
        self.rejected("concurrent_change",
                      lambda: self.service.apply("replace", token=token, body=body))
        self.assertEqual(len(self.broker.calls), before)
        self.assertEqual(self.db.finished[claims["authorization_id"]], "failed")

    def test_tampered_old_ciphertext_cannot_reach_probe_or_new_sealing(self):
        self.apply()
        row = self.db.rows[UUID(CONNECTION)]
        envelope = copy.deepcopy(row[12])
        envelope["ciphertext"] = ("A" if envelope["ciphertext"][0] != "A" else "B") + envelope["ciphertext"][1:]
        self.db.rows[UUID(CONNECTION)] = (*row[:12], envelope)
        token, body, claims = self.request("replace")
        with patch("investalo_credential_store.client.seal") as seal:
            self.rejected("authentication_failed",
                          lambda: self.service.apply("replace", token=token, body=body))
            seal.assert_not_called()
        self.assertEqual(len(self.broker.calls), 1)
        self.assertEqual(self.db.finished[claims["authorization_id"]], "failed")

    def test_driver_and_untrusted_transport_errors_are_static_without_secret_messages(self):
        self.broker.before_response = lambda: (_ for _ in ()).throw(
            ValueError("synthetic-private-secret synthetic-password"))
        token, body, claims = self.request()
        self.rejected("broker_rejected",
                      lambda: self.service.apply("register", token=token, body=body))
        self.assertEqual(self.db.finished[claims["authorization_id"]], "failed")
        self.assertEqual(self.db.rows, {})

    def test_service_and_result_are_immutable_redacted_with_explicit_safe_projection(self):
        result, _ = self.apply()
        for private in (self.service, result):
            self.assertFalse(hasattr(private, "__dict__"))
            for serialize in (pickle.dumps, dataclasses.asdict, json.dumps):
                with self.assertRaises(TypeError):
                    serialize(private)
            with self.assertRaises(AttributeError):
                private.untrusted = TRIPLE
            for secret in (TRIPLE["secret"], KEY.decode(), SUBJECT, self.broker.uid):
                self.assertNotIn(secret, repr(private) + str(private))
        public = json.dumps(result.public())
        for secret in (TRIPLE["secret"], self.broker.uid, "ciphertext", "kek"):
            self.assertNotIn(secret, public)


if __name__ == "__main__":
    unittest.main()
