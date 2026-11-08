"""Synthetic launcher checks; no actual database, broker or listening socket."""
from contextlib import ExitStack
import hashlib
import io
import json
import os
from pathlib import Path
import pickle
import ssl
import tempfile
import unittest
from unittest.mock import Mock, patch
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtendedKeyUsageOID
from investalo_bitget import Credentials
from investalo_bitget.signing import INFO_PATH, SPOT_PATH, SignedReadRequest
from investalo_credential_store import development_runtime as runtime
from investalo_credential_store.onboarding import OnboardingResult
from investalo_credential_store.request_assertion import OnboardingRejected
from test_passkey_assertions import CONNECTION, TENANT, USER, fixture_body, fixture_context
from test_private_http import authority, leaf

SIGNING = b"synthetic-signing-material-32byte"[:32]
KEK = b"synthetic-kek-material-32byte!!!!"[:32]
PASSWORD = "synthetic-password-material-1234567890"
TRIPLE = {"api_key": "synthetic-purpose-api", "secret": "synthetic-purpose-secret-päß-1e0",
          "passphrase": "synthetic-purpose-passphrase"}


def fields(**changes):
    return {
        "schema": runtime.SCHEMA, "tenant_id": str(TENANT), "user_id": str(USER),
        "broker_uid": "123456", "signing_sha256": hashlib.sha256(SIGNING).hexdigest(),
        "kek_sha256": hashlib.sha256(KEK).hexdigest(), "client_certificate_sha256": "ab" * 32,
        **changes,
    }


class Cursor:
    def __init__(self, connection):
        self.connection, self.rows = connection, []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        self.rows = list({
            runtime.ROLE_SQL: [self.connection.role],
            runtime.CONTEXT_SQL: [self.connection.actor],
            runtime.CAPABILITY_SQL: [self.connection.capabilities],
        }.get(query, []))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class Connection:
    def __init__(self, *, role=None, actor=None, capabilities=None, autocommit=False, failure=None):
        self.role = role or (runtime.LOGIN_ROLE, runtime.LOGIN_ROLE, False, False,
                             False, False, False, True)
        self.actor = actor or (TENANT, USER)
        self.capabilities = capabilities or (runtime.DATABASE, True, True, True)
        self.autocommit, self.failure = autocommit, failure
        self.queries, self.commits, self.rollbacks, self.closed = [], 0, 0, False

    def __enter__(self):
        return self

    def __exit__(self, kind, *_):
        self.closed = True
        if kind is None:
            self.commits += 1
            if self.failure:
                raise self.failure
        else:
            self.rollbacks += 1
        return False

    def cursor(self):
        return Cursor(self)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {}, clear=True))
        names = {
            "CONFIG_PATH": "config", "SIGNING_PATH": "signing", "PASSWORD_PATH": "password",
            "PG_CA_PATH": "pgca", "CLIENT_CA_PATH": "clientca", "TLS_CERT_PATH": "cert",
            "TLS_KEY_PATH": "key", "KEK_DIRECTORY": "keks",
        }
        for name, basename in names.items():
            self.stack.enter_context(patch.object(runtime, name, str(self.base / basename)))
        self.write(runtime.CONFIG_PATH, json.dumps(fields()).encode())
        self.write(runtime.SIGNING_PATH, SIGNING)
        self.write(runtime.PASSWORD_PATH, PASSWORD.encode())
        self.write(runtime.PG_CA_PATH, b"synthetic existing public PG CA", mode=0o444)
        directory = Path(runtime.KEK_DIRECTORY)
        directory.mkdir(mode=0o700)
        self.own(directory)
        self.write(directory / "active.key", KEK)

    def own(self, path):
        if os.geteuid() == 0:
            os.chown(path, runtime.OWNER_UID, runtime.OWNER_UID)
        elif os.geteuid() != runtime.OWNER_UID:
            self.skipTest("Private fixture files require runtime UID or local root.")

    def write(self, path, raw, *, mode=0o400):
        path = Path(path)
        # Test repair only; the actual runtime never creates or writes a file.
        if path.exists():
            path.chmod(0o600)
        path.write_bytes(raw)
        self.own(path)
        path.chmod(mode)

    def rejected(self, call):
        with self.assertRaises(runtime.DevelopmentRuntimeRejected) as error:
            call()
        self.assertEqual(str(error.exception), "development_runtime_rejected")
        self.assertTrue(error.exception.__suppress_context__)

    def config(self):
        return runtime.load_config(development_mode=True)

    def application(self, connection=None):
        connection = connection or Connection()
        mocked = self.stack.enter_context(patch.object(runtime.psycopg, "connect",
                                                       return_value=connection))
        app = runtime.create_application(self.config(), development_mode=True)
        return app, connection, mocked

    def test_explicit_development_flag_required_before_private_reads_or_listen(self):
        with patch.object(runtime, "_read") as read, \
             patch.object(runtime, "create_private_asgi_server") as server, \
             patch.object(runtime.psycopg, "connect") as connect, \
             patch("sys.stderr", new_callable=io.StringIO) as stderr:
            for value in (False, None, 1, "true"):
                self.rejected(lambda: runtime.load_config(development_mode=value))
                self.rejected(lambda: runtime.create_application(runtime.DevelopmentConfig(fields()),
                                                                development_mode=value))
            for args in ([], ["--production"], ["--development", "--config", "/other"],
                         ["--development", "--development"]):
                self.assertEqual(runtime.main(args), 1)
            read.assert_not_called()
            connect.assert_not_called()
            server.assert_not_called()
            self.assertEqual(stderr.getvalue(), (runtime.STARTUP_ERROR + "\n") * 4)

    def test_valid_config_is_fixed_schema_private_and_immutable(self):
        config = self.config()
        self.assertEqual((config.tenant_id, config.user_id, config.broker_uid), (TENANT, USER, "123456"))
        self.assertEqual(str(config), "DevelopmentConfig(<redacted>)")
        with self.assertRaises(AttributeError):
            config.broker_uid = "654321"
        with self.assertRaises(TypeError):
            pickle.dumps(config)
        self.assertEqual(set(config.__slots__), runtime.CONFIG_FIELDS - {"schema"})

    def test_config_rejects_request_selection_and_noncanonical_scalars(self):
        invalid = (
            {"schema": "other"}, {"tenant_id": str(TENANT).upper().replace("a", "A") + " "},
            {"user_id": USER}, {"tenant_id": 1001}, {"broker_uid": "0123456"},
            {"broker_uid": "0"}, {"broker_uid": "1" * 21}, {"broker_uid": "123\x00"},
            {"broker_uid": 123456}, {"signing_sha256": "AB" * 32},
            {"kek_sha256": fields()["signing_sha256"]},
            {"role": "investalo_admin"}, {"dsn": "private database"},
            {"origin": "https://other.fixture.invalid"}, {"provider": "other"},
        )
        for changes in invalid:
            with self.subTest(field=next(iter(changes))):
                self.rejected(lambda: runtime.DevelopmentConfig(fields(**changes)))
        for key in runtime.CONFIG_FIELDS:
            reduced = fields()
            reduced.pop(key)
            self.rejected(lambda: runtime.DevelopmentConfig(reduced))

    def test_config_duplicate_invalid_encoding_nonobject_and_oversize_rejected(self):
        raw = json.dumps(fields()).encode()
        cases = (
            raw[:-1] + b',"broker_uid":"654321"}', b"\xff", b"[]", b"null",
            raw.replace(b'"123456"', b"NaN"), b" " * 2049,
        )
        for value in cases:
            self.write(runtime.CONFIG_PATH, value)
            self.rejected(self.config)

    def test_config_mode_owner_size_and_hardlinks_rejected_before_read(self):
        path = Path(runtime.CONFIG_PATH)
        for mode in (0o600, 0o440, 0o444, 0o000):
            path.chmod(mode)
            with patch.object(runtime.os, "read") as read:
                self.rejected(self.config)
                read.assert_not_called()
        path.chmod(0o400)
        if os.geteuid() == 0:
            os.chown(path, 0, 0)
            self.rejected(self.config)
            self.own(path)
        os.link(path, self.base / "linked")
        self.rejected(self.config)

    def test_config_final_and_parent_symlinks_rejected(self):
        alias = self.base / "alias"
        alias.symlink_to(runtime.CONFIG_PATH)
        with patch.object(runtime, "CONFIG_PATH", str(alias)):
            self.rejected(self.config)
        directory_alias = self.base / "directory-alias"
        directory_alias.symlink_to(self.base, target_is_directory=True)
        with patch.object(runtime, "CONFIG_PATH", str(directory_alias / "config")):
            self.rejected(self.config)

    def test_changed_or_growing_file_rejected_and_descriptors_closed(self):
        actual = runtime.os.fstat
        seen = []

        def changed(descriptor):
            value = actual(descriptor)
            seen.append(descriptor)
            if len(seen) == 2:
                parts = list(value)
                parts[6] += 1
                return os.stat_result(parts)
            return value

        with patch.object(runtime.os, "fstat", side_effect=changed):
            self.rejected(self.config)
        for descriptor in set(seen):
            with self.assertRaises(OSError):
                os.fstat(descriptor)
        with patch.object(runtime.os, "read", return_value=b"x" * 2049):
            self.rejected(self.config)

    def test_signing_fingerprint_exact_size_and_distinct_kek_checked_before_db(self):
        for value in (b"x" * 31, b"x" * 33, b"x" * 32):
            self.write(runtime.SIGNING_PATH, value)
            with patch.object(runtime.psycopg, "connect") as connect:
                self.rejected(lambda: runtime.create_application(self.config(), development_mode=True))
                connect.assert_not_called()

    def test_kek_fingerprint_mode_and_symlink_checked_before_db(self):
        key = Path(runtime.KEK_DIRECTORY) / "active.key"
        self.write(key, b"x" * 32)
        with patch.object(runtime.psycopg, "connect") as connect:
            self.rejected(lambda: runtime.create_application(self.config(), development_mode=True))
            connect.assert_not_called()
        self.write(key, KEK, mode=0o600)
        self.rejected(lambda: runtime.create_application(self.config(), development_mode=True))
        key.rename(key.with_name("original.key"))
        key.symlink_to("original.key")
        self.rejected(lambda: runtime.create_application(self.config(), development_mode=True))

    def test_password_file_validation_happens_before_database(self):
        for raw in (b"", b"short", b"x" * 129, b"x" * 32 + b"\n", b"\xff" * 32):
            self.write(runtime.PASSWORD_PATH, raw)
            with patch.object(runtime.psycopg, "connect") as connect:
                self.rejected(lambda: runtime.create_application(self.config(), development_mode=True))
                connect.assert_not_called()

    def test_startup_checks_role_actor_database_and_function_privileges(self):
        app, connection, _ = self.application()
        self.assertTrue(app.enabled)
        self.assertEqual(app.context.expected_login_role, runtime.LOGIN_ROLE)
        self.assertEqual([query for query, _ in connection.queries],
                         [*runtime.TIMEOUT_SQL, runtime.ROLE_SQL, runtime.CONTEXT_SQL, runtime.CAPABILITY_SQL])
        self.assertEqual((connection.commits, connection.rollbacks, connection.closed), (1, 0, True))
        self.assertNotIn("schema_migrations", runtime.CAPABILITY_SQL)

    def test_startup_rejects_admin_role_flags_role_switch_and_foreign_actor(self):
        normal = Connection().role
        roles = [("investalo_admin", *normal[1:]), (normal[0], "other", *normal[2:])]
        for position in range(2, 8):
            changed = list(normal)
            changed[position] = not normal[position]
            roles.append(tuple(changed))
        roles.append((*normal[:2], 0, *normal[3:]))
        for role in roles:
            connection = Connection(role=role)
            with patch.object(runtime.psycopg, "connect", return_value=connection):
                self.rejected(lambda: runtime.create_application(self.config(), development_mode=True))
            self.assertEqual((connection.commits, connection.rollbacks), (0, 1))
            self.assertNotIn(runtime.CONTEXT_SQL, [query for query, _ in connection.queries])
        for actor in ((UUID(int=99), USER), (TENANT, UUID(int=99))):
            with patch.object(runtime.psycopg, "connect", return_value=Connection(actor=actor)):
                self.rejected(lambda: runtime.create_application(self.config(), development_mode=True))

    def test_startup_rejects_wrong_database_missing_function_or_execute(self):
        for capabilities in (("investalo", True, True, True),
                             (runtime.DATABASE, None, True, True),
                             (runtime.DATABASE, True, False, True),
                             (runtime.DATABASE, True, True, 1)):
            with patch.object(runtime.psycopg, "connect",
                              return_value=Connection(capabilities=capabilities)):
                self.rejected(lambda: runtime.create_application(self.config(), development_mode=True))

    def test_fixed_ssl_fresh_connections_timeouts_and_no_ambient_role_options(self):
        connections = [Connection(), Connection()]
        with patch.object(runtime.psycopg, "connect", side_effect=connections) as connect:
            factory = runtime._connect_factory(PASSWORD)
            for expected in connections:
                with factory() as actual:
                    self.assertIs(actual, expected)
            self.assertEqual(connect.call_count, 2)
            for call in connect.call_args_list:
                self.assertEqual(call.kwargs, {
                    "host": "postgres", "port": 5432, "dbname": "investalo_credentials_checks",
                    "user": "investalo_credentials_tests_a", "password": PASSWORD,
                    "sslmode": "verify-full", "sslrootcert": runtime.PG_CA_PATH,
                    "connect_timeout": 5, "autocommit": False, "gssencmode": "disable",
                    "options": "-c statement_timeout=10000 -c lock_timeout=5000",
                })
            for connection in connections:
                self.assertEqual(connection.queries, [(query, None) for query in runtime.TIMEOUT_SQL])
                self.assertTrue(connection.closed)

    def test_ambient_libpq_settings_rejected_before_secrets_and_connection(self):
        for name in ("PGOPTIONS", "PGSERVICE", "PGSERVICEFILE", "PGPASSWORD", "PGHOST",
                     "PGHOSTADDR", "PGDATABASE", "PGSSLMODE", "PGSSLKEY", "PGPASSFILE"):
            with patch.dict(os.environ, {name: "sensitive test canary"}), \
                 patch.object(runtime, "_read") as read, \
                 patch.object(runtime.psycopg, "connect") as connect:
                self.rejected(lambda: runtime.create_application(runtime.DevelopmentConfig(fields()),
                                                                development_mode=True))
                self.rejected(lambda: runtime._connect_factory(PASSWORD))
                read.assert_not_called()
                connect.assert_not_called()

    def test_failed_connect_and_unknown_commit_never_retried(self):
        with patch.object(runtime.psycopg, "connect", side_effect=RuntimeError("private canary")) as connect:
            with self.assertRaises(RuntimeError):
                with runtime._connect_factory(PASSWORD)():
                    self.fail("Unexpected connected transaction")
            self.assertEqual(connect.call_count, 1)
        connection = Connection(failure=RuntimeError("lost commit reply"))
        with patch.object(runtime.psycopg, "connect", return_value=connection) as connect:
            self.rejected(lambda: runtime.create_application(self.config(), development_mode=True))
            self.assertEqual(connect.call_count, 1)
            self.assertEqual(connection.commits, 1)
            self.assertTrue(connection.closed)

    def test_autocommit_connection_rejected_and_rolled_back(self):
        connection = Connection(autocommit=True)
        with patch.object(runtime.psycopg, "connect", return_value=connection):
            self.rejected(lambda: runtime.create_application(self.config(), development_mode=True))
        self.assertEqual(connection.queries, [])
        self.assertEqual(connection.rollbacks, 1)

    def test_actual_or_near_fixture_credentials_rejected_before_executor_or_database(self):
        app, _, connect = self.application()
        connect.reset_mock()
        triples = (
            {**TRIPLE, "api_key": "actual-user-key"}, {**TRIPLE, "secret": "actual-user-secret"},
            {**TRIPLE, "passphrase": "actual-user-passphrase"},
            {**TRIPLE, "secret": TRIPLE["secret"] + " "},
            {**TRIPLE, "api_key": "synthetic-purpose-replacement"},
        )
        with patch.object(runtime, "PasskeyBitgetOnboarding") as executor:
            for triple in triples:
                with self.assertRaises(OnboardingRejected) as error:
                    app.execute(fixture_context(), "register", "opaque", fixture_body(triple=triple))
                self.assertEqual(error.exception.code, "invalid_request")
            executor.assert_not_called()
            connect.assert_not_called()

    def test_exact_synthetic_rawbody_and_independent_original_session_reach_executor(self):
        app, _, _ = self.application()
        context = fixture_context()
        result = OnboardingResult(UUID(CONNECTION), 1, 1, "active")
        with patch.object(runtime, "PasskeyBitgetOnboarding") as executor:
            executor.return_value.apply.return_value = result
            for action in ("register", "replace", "revoke"):
                triple = {**TRIPLE, "api_key": runtime._API_KEYS.get(action, TRIPLE["api_key"])}
                raw = fixture_body(action, triple=triple)
                self.assertIs(app.execute(context, action, "opaque-original-token", raw), result)
                self.assertIs(executor.call_args.kwargs["request_context"], context)
                self.assertEqual(context.oidc_auth_time, fixture_context().oidc_auth_time)
                executor.return_value.apply.assert_called_with(action, token="opaque-original-token", body=raw)

    def test_revoke_rejects_credentials_and_invalid_actions_before_executor(self):
        body = json.loads(fixture_body("revoke"))
        body["credentials"] = TRIPLE
        for action, raw in (("revoke", json.dumps(body).encode()), ("other", fixture_body()),
                            ("register", b"x" * 4097), ("register", "not bytes")):
            with self.assertRaises(OnboardingRejected):
                runtime._synthetic_request(action, raw)

    def test_transport_returns_only_fixed_synthetic_getinfo_without_network(self):
        transport = runtime._SyntheticInfoTransport(self.config())
        credentials = Credentials(TRIPLE["api_key"], TRIPLE["secret"], TRIPLE["passphrase"])
        with patch("urllib.request.build_opener") as network:
            response = transport(SignedReadRequest(credentials, INFO_PATH, (), 1))
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.body)["data"], {
                "userId": "123456", "parentId": None, "authorities": ["stor"], "ips": "203.0.113.19",
            })
            with self.assertRaises(OnboardingRejected):
                transport(SignedReadRequest(credentials, SPOT_PATH, (("assetType", "all"),), 1))
            with self.assertRaises(OnboardingRejected):
                transport(Mock(method="GET", path=INFO_PATH))
            network.assert_not_called()

    def tls_files(self):
        ca_key, ca = authority()
        key, cert = leaf(ca_key, ca, "credential-restricted.cockpit.local.test",
                         ExtendedKeyUsageOID.SERVER_AUTH)
        self.write(runtime.CLIENT_CA_PATH, ca.public_bytes(serialization.Encoding.PEM))
        self.write(runtime.TLS_CERT_PATH, cert.public_bytes(serialization.Encoding.PEM))
        self.write(runtime.TLS_KEY_PATH, key.private_bytes(serialization.Encoding.PEM,
                   serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))

    def test_tls_requires_client_certificate_and_loads_real_pinned_fd_files(self):
        self.tls_files()
        context = runtime._tls_context()
        self.assertEqual(context.protocol, ssl.PROTOCOL_TLS_SERVER)
        self.assertEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertGreaterEqual(context.cert_store_stats()["x509_ca"], 1)
        Path(runtime.TLS_KEY_PATH).chmod(0o600)
        self.rejected(runtime._tls_context)

    def test_launcher_startup_failure_static_and_never_listens(self):
        canary = "private password/config canary"
        with patch.object(runtime.os, "geteuid", return_value=runtime.OWNER_UID), \
             patch.object(runtime, "create_application", side_effect=ValueError(canary)), \
             patch.object(runtime, "create_private_asgi_server") as server, \
             patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(runtime.main(["--development"]), 1)
            server.assert_not_called()
            self.assertEqual(stderr.getvalue(), runtime.STARTUP_ERROR + "\n")
            self.assertNotIn(canary, stderr.getvalue())

    def test_launcher_only_binds_after_config_keys_db_and_tls_verified(self):
        config = self.config()
        app, _, _ = self.application()
        server, tls, ordering = Mock(), Mock(), []
        with patch.object(runtime.os, "geteuid", return_value=runtime.OWNER_UID), \
             patch.object(runtime, "load_config", side_effect=lambda **_: ordering.append("config") or config), \
             patch.object(runtime, "create_application",
                          side_effect=lambda *_args, **_: ordering.append("application") or app), \
             patch.object(runtime, "_tls_context", side_effect=lambda: ordering.append("tls") or tls), \
             patch.object(runtime, "create_private_asgi_server",
                          side_effect=lambda *_args, **_: ordering.append("bind") or server) as bind:
            self.assertEqual(runtime.main(["--development"]), 0)
            self.assertEqual(ordering, ["config", "application", "tls", "bind"])
            bind.assert_called_once_with(("0.0.0.0", 9443), tls_context=tls,
                client_certificate_sha256=frozenset((config.client_certificate_sha256,)),
                application=app, timeout_seconds=20, max_workers=4)
            server.serve_forever.assert_called_once()
            server.server_close.assert_called_once()

    def test_launcher_wrong_os_user_rejected_before_read_and_close_errors_are_static(self):
        with patch.object(runtime.os, "geteuid", return_value=0), \
             patch.object(runtime, "load_config") as load, \
             patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(runtime.main(["--development"]), 1)
            load.assert_not_called()
        server = Mock()
        server.server_close.side_effect = ValueError("sensitive close canary")
        with patch.object(runtime.os, "geteuid", return_value=runtime.OWNER_UID), \
             patch.object(runtime, "create_application"), patch.object(runtime, "_tls_context"), \
             patch.object(runtime, "create_private_asgi_server", return_value=server), \
             patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(runtime.main(["--development"]), 1)
            self.assertEqual(stderr.getvalue(), runtime.STARTUP_ERROR + "\n")


if __name__ == "__main__":
    unittest.main()
