"""Offline client transaction tests; database policy is proved separately in PG."""
import dataclasses
import json
import pickle
import unittest
from uuid import UUID

from investalo_credential_store.client import CONTEXT_SQL, ROLE_SQL
from investalo_credential_store.models import StoreContext
from investalo_credential_store.passkey_authorization import (
    CONSUME_SQL, LOCK_SQL, ConsumedPasskeyAuthorization, PasskeyAuthorizationClient,
)
from investalo_credential_store.passkey_request_assertion import PasskeyRequestVerifier
from investalo_credential_store.request_assertion import OnboardingRejected, RequestVerifier
from test_passkey_assertions import (
    ISSUER, KEY, NOW, ORIGIN, SUBJECT, TENANT, TRIPLE, USER,
    fixture_body, fixture_claims, fixture_context, sign_assertion,
)


ROLE = "credential_fixture"


class DriverFailure(Exception):
    def __init__(self, state=None):
        self.sqlstate = state
        super().__init__("postgres://synthetic-private-password@fixture synthetic-private-secret")


class TransactionFixture:
    def __init__(self):
        self.role = (ROLE, ROLE, False, False, False, False, False, True)
        self.actor = (TENANT, USER)
        self.autocommit = False
        self.responses = {}
        self.fail = {}
        self.calls = []
        self.opened = []
        self.committed = []
        self.rolled_back = []
        self.consumed_claims = []
        self.unknown_commit = False
        self.enter_failure = False

    def connect(self):
        connection = TransactionConnection(self, len(self.opened) + 1)
        self.opened.append(connection)
        return connection

    def client(self, *, store_context=None, request_context=None, verifier=None):
        return PasskeyAuthorizationClient(
            store_context or StoreContext(tenant_id=TENANT, user_id=USER, expected_login_role=ROLE),
            request_context or fixture_context(), verifier=verifier or PasskeyRequestVerifier(
                key=KEY, oidc_issuer=ISSUER, origin=ORIGIN, clock=lambda: NOW,
            ), connect=self.connect,
        )


class TransactionConnection:
    def __init__(self, database, number):
        self.database = database
        self.number = number
        self.autocommit = database.autocommit
        self.pending_consumes = []

    def __enter__(self):
        if self.database.enter_failure:
            raise DriverFailure()
        return self

    def __exit__(self, kind, value, traceback):
        if kind is not None:
            self.database.rolled_back.append(self.number)
            return False
        self.database.committed.append(self.number)
        self.database.consumed_claims.extend(self.pending_consumes)
        if self.database.unknown_commit:
            raise DriverFailure("08006")
        return False

    def cursor(self):
        return TransactionCursor(self)


class TransactionCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def execute(self, query, params=()):
        db = self.connection.database
        db.calls.append((self.connection.number, query, params))
        if query in db.fail:
            raise db.fail[query]
        if query == ROLE_SQL:
            rows = [db.role]
        elif query == CONTEXT_SQL:
            rows = [db.actor]
        elif query == CONSUME_SQL:
            claims = json.loads(params[0])
            self.connection.pending_consumes.append(claims)
            rows = [(UUID(claims["authorization_id"]),)]
        elif query == LOCK_SQL:
            rows = [(True,)]
        else:
            raise AssertionError("Unexpected SQL in offline fixture")
        self.rows = list(db.responses.get(query, rows))


class PasskeyAuthorizationClientTests(unittest.TestCase):
    def setUp(self):
        self.database = TransactionFixture()
        self.client = self.database.client()

    def consume(self, *, action="register", token=None, body=None, client=None):
        body = fixture_body(action) if body is None else body
        token = sign_assertion(fixture_claims(action, body=body)) if token is None else token
        return (client or self.client).consume(action, token=token, body=body)

    def rejected(self, code, operation):
        with self.assertRaises(OnboardingRejected) as caught:
            operation()
        error = caught.exception
        self.assertEqual(error.code, code)
        self.assertEqual(str(error), code)
        self.assertIsNone(error.__cause__)
        self.assertTrue(error.__suppress_context__)
        for private in (KEY.decode(), SUBJECT, ISSUER, ORIGIN, str(TENANT),
                        TRIPLE["secret"], "synthetic-private-password"):
            self.assertNotIn(private, repr(error) + str(error))

    def test_all_actions_return_handle_only_after_committed_consume(self):
        for action in ("register", "replace", "revoke"):
            handle = self.consume(action=action)
            self.assertIsInstance(handle, ConsumedPasskeyAuthorization)
            self.assertEqual(self.database.committed[-1], len(self.database.opened))
            self.assertEqual(self.database.consumed_claims[-1], fixture_claims(action))
        self.assertEqual(len([row for row in self.database.calls if row[1] == CONSUME_SQL]), 3)
        self.assertEqual(self.database.rolled_back, [])

    def test_invalid_token_body_or_actor_is_rejected_before_connecting(self):
        for token, body in (
            ("not-a-token", fixture_body()),
            (sign_assertion(fixture_claims()), fixture_body() + b" "),
            (sign_assertion(fixture_claims()), b""),
            (sign_assertion(fixture_claims(user_id=str(UUID(int=9000)))), fixture_body()),
        ):
            self.rejected("authentication_required", lambda: self.consume(token=token, body=body))
        self.assertEqual(self.database.opened, [])
        self.assertEqual(self.database.calls, [])

    def test_constructor_requires_exact_tenant_and_user_context_match(self):
        for request in (fixture_context(tenant_id=UUID(int=7000)),
                        fixture_context(user_id=UUID(int=7001)), object()):
            self.rejected("invalid_context", lambda: self.database.client(request_context=request))
        self.rejected("invalid_context", lambda: self.database.client(store_context=object()))
        old = RequestVerifier(key=KEY, oidc_issuer=ISSUER, clock=lambda: NOW)
        self.rejected("invalid_context", lambda: self.database.client(verifier=old))
        self.assertEqual(self.database.opened, [])

    def test_claim_boundary_has_exact_signed_fields_and_no_raw_body_or_token(self):
        body = fixture_body()
        token = sign_assertion(fixture_claims(body=body))
        handle = self.consume(token=token, body=body)
        claim_json, = next(params for _, query, params in self.database.calls if query == CONSUME_SQL)
        self.assertEqual(json.loads(claim_json), fixture_claims(body=body))
        self.assertEqual(len(json.loads(claim_json)), 30)
        self.assertNotIn(TRIPLE["secret"], claim_json)
        self.assertNotIn(token, claim_json)
        self.assertFalse(hasattr(handle, "body"))
        self.assertFalse(hasattr(handle, "token"))
        self.assertFalse(hasattr(handle, "public"))
        self.assertEqual(handle._assertion.body_sha256, fixture_claims()["body_sha256"])

    def test_role_must_be_exact_login_and_current_role_without_privileged_flags(self):
        invalid = [
            ("other", ROLE, False, False, False, False, False, True),
            (ROLE, "other", False, False, False, False, False, True),
            (ROLE, ROLE, False, False, False, False, False, False),
        ]
        for offset in range(2, 7):
            role = list(self.database.role)
            role[offset] = True
            invalid.append(tuple(role))
        role = list(self.database.role)
        role[2] = 0
        invalid.append(tuple(role))
        for role in invalid:
            self.database.role = role
            self.rejected("access_denied", self.consume)
        self.assertFalse(any(query in (CONTEXT_SQL, CONSUME_SQL) for _, query, _ in self.database.calls))
        self.assertEqual(self.database.committed, [])

    def test_database_actor_must_equal_bound_store_and_request_context(self):
        for actor in ((UUID(int=9000), USER), (TENANT, UUID(int=9001)),
                      (str(TENANT), USER), (TENANT, str(USER))):
            self.database.actor = actor
            self.rejected("access_denied", self.consume)
        self.assertFalse(any(query == CONSUME_SQL for _, query, _ in self.database.calls))
        self.assertEqual(self.database.committed, [])

    def test_autocommit_is_explicit_false_in_consume_and_lock_transactions(self):
        for invalid in (True, None, 0, "false"):
            self.database.autocommit = invalid
            self.rejected("invalid_context", self.consume)
        self.assertEqual(self.database.calls, [])
        self.database.autocommit = False
        handle = self.consume()
        self.database.autocommit = True
        self.rejected("invalid_context", lambda: self.lock_once(handle))
        self.assertFalse(any(query == LOCK_SQL for _, query, _ in self.database.calls))

    def test_database_denial_and_known_failure_codes_are_static_and_never_retried(self):
        for state, code in (("42501", "access_denied"), ("40001", "concurrent_change"),
                            ("23505", "identity_conflict"), ("22023", "invalid_record"),
                            ("08006", "unavailable"), (None, "unavailable")):
            self.database.fail[CONSUME_SQL] = DriverFailure(state)
            before = len(self.database.calls)
            self.rejected(code, self.consume)
            calls = self.database.calls[before:]
            self.assertEqual(sum(query == CONSUME_SQL for _, query, _ in calls), 1)
        self.assertEqual(self.database.committed, [])
        self.assertEqual(self.database.consumed_claims, [])

    def test_consume_requires_one_exact_authorization_uuid_row(self):
        for rows in ([], [(UUID(int=999),)], [(str(UUID(int=1010)),)],
                     [(None,)], [(UUID(int=1010),), (UUID(int=1010),)],
                     [(UUID(int=1010), True)], [[UUID(int=1010)]]):
            self.database.responses[CONSUME_SQL] = rows
            self.rejected("invalid_record", self.consume)
        self.assertEqual(self.database.committed, [])
        self.assertEqual(self.database.consumed_claims, [])

    def test_unknown_consume_commit_returns_no_handle_and_does_not_retry(self):
        self.database.unknown_commit = True
        sentinel = object()
        handle = sentinel
        try:
            handle = self.consume()
        except OnboardingRejected as error:
            self.assertEqual(error.code, "unavailable")
        else:
            self.fail("Unknown consume commit returned an authority handle")
        self.assertIs(handle, sentinel)
        self.assertEqual(self.database.committed, [1])
        self.assertEqual(len(self.database.consumed_claims), 1)
        self.assertEqual(sum(query == CONSUME_SQL for _, query, _ in self.database.calls), 1)
        self.assertFalse(any(query == LOCK_SQL for _, query, _ in self.database.calls))

    def test_connection_entry_error_is_static_and_never_returns_authority(self):
        self.database.enter_failure = True
        self.rejected("unavailable", self.consume)
        self.assertEqual(len(self.database.opened), 1)
        self.assertEqual(self.database.calls, [])

    def lock_once(self, handle, *, client=None):
        with (client or self.client).lock(handle) as connection:
            return connection

    def test_lock_uses_same_claims_and_new_checked_transaction_connection(self):
        handle = self.consume()
        consumed_at = self.database.committed.copy()
        with self.client.lock(handle) as connection:
            self.assertEqual(consumed_at, [1])
            self.assertEqual(self.database.committed, [1])
            self.assertIs(connection, self.database.opened[1])
            self.assertIs(connection.autocommit, False)
        self.assertEqual(self.database.committed, [1, 2])
        consume_args = next(params for _, query, params in self.database.calls if query == CONSUME_SQL)
        lock_args = next(params for _, query, params in self.database.calls if query == LOCK_SQL)
        self.assertEqual(consume_args, lock_args)
        self.assertEqual([query for number, query, _ in self.database.calls if number == 2],
                         [ROLE_SQL, CONTEXT_SQL, LOCK_SQL])

    def test_lock_rejects_foreign_client_handle_without_database_access(self):
        handle = self.consume()
        other_client = self.database.client()
        for value in (None, UUID(int=1010), object(), handle,
                      object.__new__(ConsumedPasskeyAuthorization)):
            before = len(self.database.opened)
            self.rejected("invalid_context", lambda: self.lock_once(value, client=other_client))
            self.assertEqual(len(self.database.opened), before)

    def test_current_role_and_actor_are_checked_again_before_lock(self):
        handle = self.consume()
        self.database.actor = (TENANT, UUID(int=8888))
        self.rejected("access_denied", lambda: self.lock_once(handle))
        self.assertFalse(any(query == LOCK_SQL for _, query, _ in self.database.calls))
        self.assertEqual(self.database.committed, [1])
        self.assertEqual(len(self.database.consumed_claims), 1)

    def test_lock_denial_or_nonboolean_success_does_not_enter_caller_write_block(self):
        handle = self.consume()
        for rows in ([], [(False,)], [(1,)], [(None,)], [(True,), (True,)]):
            self.database.responses[LOCK_SQL] = rows
            self.rejected("invalid_record", lambda: self.lock_once(handle))
        self.database.responses.pop(LOCK_SQL)
        self.database.fail[LOCK_SQL] = DriverFailure("42501")
        self.rejected("access_denied", lambda: self.lock_once(handle))
        self.assertEqual(self.database.committed, [1])
        self.assertEqual(len(self.database.consumed_claims), 1)

    def test_failed_final_transaction_rolls_back_while_consume_remains_committed(self):
        handle = self.consume()
        def failed_write():
            with self.client.lock(handle):
                try:
                    raise DriverFailure("40001")
                except DriverFailure as error:
                    raise OnboardingRejected("concurrent_change") from error
        self.rejected("concurrent_change", failed_write)
        self.assertEqual(self.database.committed, [1])
        self.assertEqual(self.database.rolled_back, [2])
        self.assertEqual(len(self.database.consumed_claims), 1)
        self.assertEqual(sum(query == CONSUME_SQL for _, query, _ in self.database.calls), 1)
        self.assertEqual(sum(query == LOCK_SQL for _, query, _ in self.database.calls), 1)

    def test_unknown_lock_commit_is_static_and_not_retried(self):
        handle = self.consume()
        self.database.unknown_commit = True
        self.rejected("unavailable", lambda: self.lock_once(handle))
        self.assertEqual(self.database.committed, [1, 2])
        self.assertEqual(sum(query == LOCK_SQL for _, query, _ in self.database.calls), 1)
        self.assertEqual(sum(query == CONSUME_SQL for _, query, _ in self.database.calls), 1)

    def test_client_and_handle_are_private_immutable_and_nonserializing(self):
        handle = self.consume()
        for private in (self.client, handle):
            for secret in (TRIPLE["secret"], KEY.decode(), SUBJECT, ISSUER, ORIGIN, str(TENANT)):
                self.assertNotIn(secret, repr(private) + str(private))
            self.assertFalse(hasattr(private, "__dict__"))
            self.assertFalse(hasattr(private, "public"))
            for serialize in (pickle.dumps, dataclasses.asdict, json.dumps):
                with self.assertRaises(TypeError):
                    serialize(private)
            with self.assertRaises(AttributeError):
                private.other = "changed"
        with self.assertRaises(AttributeError):
            handle._owner = object()
        self.assertFalse(hasattr(self.client, "apply"))
        self.assertFalse(hasattr(self.client, "probe"))
        self.assertFalse(hasattr(self.client, "finish"))


if __name__ == "__main__":
    unittest.main()
