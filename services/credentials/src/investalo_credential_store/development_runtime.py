"""Explicit synthetic-only development launcher; no production or broker intake.

All identity, connection and file locations are trusted fixed server inputs.
The ASGI HTTPS boundary remains an isolated development fixture. It accepts
only the existing synthetic credential canaries, before durable consumption.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import hmac
import json
import os
import re
import ssl
import stat
import sys
import time
from uuid import UUID

import psycopg

from investalo_bitget.signing import INFO_PATH, SignedReadRequest
from investalo_bitget.transport import ReadResponse

from .client import CONTEXT_SQL, ROLE_SQL, _row
from .keyfiles import DevelopmentKeyFileProvider, KeyFile
from .models import StoreContext, _PrivateImmutable
from .onboarding import _request
from .passkey_onboarding import PasskeyBitgetOnboarding
from .passkey_request_assertion import MAX_BODY_BYTES, PasskeyRequestVerifier
from .private_asgi import create_private_asgi_server
from .private_http import CredentialHTTPApplication
from .request_assertion import OnboardingRejected

OWNER_UID = 10003
CONFIG_PATH = "/run/secrets/credential_service_config"
SIGNING_PATH = "/run/secrets/credential_service_signing_key"
CLIENT_CA_PATH = "/run/secrets/credential_service_client_ca"
TLS_CERT_PATH = "/run/secrets/credential_service_tls_cert"
TLS_KEY_PATH = "/run/secrets/credential_service_tls_key"
KEK_DIRECTORY = "/run/credential-keks"
KEK_VERSION = "synthetic-purpose-cockpit"
PASSWORD_PATH = "/run/secrets/credentials_test_password_a"
PG_CA_PATH = "/run/secrets/local_ca_cert"
DATABASE = "investalo_credentials_checks"
LOGIN_ROLE = "investalo_credentials_tests_a"
OIDC_ISSUER = "https://auth.cockpit.local.test:8443"
ORIGIN = "https://cockpit.local.test:8443"
ADDRESS = ("0.0.0.0", 9443)
EGRESS_IP = "203.0.113.19"
SCHEMA = "investalo-credential-development-service/1"
CONFIG_FIELDS = frozenset((
    "schema", "tenant_id", "user_id", "broker_uid", "signing_sha256",
    "kek_sha256", "client_certificate_sha256",
))
CAPABILITY_SQL = """SELECT current_database(),
pg_catalog.has_function_privilege(session_user,
pg_catalog.to_regprocedure('platform.credential_consume_passkey_authorization(jsonb)'), 'EXECUTE'),
pg_catalog.has_function_privilege(session_user,
pg_catalog.to_regprocedure('platform.credential_lock_passkey_authorization(jsonb)'), 'EXECUTE'),
pg_catalog.has_function_privilege(session_user,
pg_catalog.to_regprocedure('platform.credential_finish_passkey_authorization(jsonb,text)'), 'EXECUTE')"""
TIMEOUT_SQL = ("SET LOCAL statement_timeout = '10s'", "SET LOCAL lock_timeout = '5s'")
STARTUP_ERROR = "Credential development service startup rejected."
_API_KEYS = {"register": "synthetic-purpose-api", "replace": "synthetic-purpose-replacement"}
_SECRET = "synthetic-purpose-secret-päß-1e0".encode("utf-8")
_PASSPHRASE = "synthetic-purpose-passphrase"


class DevelopmentRuntimeRejected(ValueError):
    def __init__(self):
        super().__init__("development_runtime_rejected")


class DevelopmentConfig(_PrivateImmutable):
    __slots__ = ("tenant_id", "user_id", "broker_uid", "signing_sha256",
                 "kek_sha256", "client_certificate_sha256")

    def __init__(self, fields):
        try:
            if type(fields) is not dict or set(fields) != CONFIG_FIELDS or fields["schema"] != SCHEMA:
                raise ValueError()
            values = {}
            for name in ("tenant_id", "user_id"):
                value = fields[name]
                if type(value) is not str or str(UUID(value)) != value:
                    raise ValueError()
                values[name] = UUID(value)
            uid = fields["broker_uid"]
            if type(uid) is not str or re.fullmatch(r"[1-9][0-9]{0,19}", uid) is None:
                raise ValueError()
            values["broker_uid"] = uid
            for name in ("signing_sha256", "kek_sha256", "client_certificate_sha256"):
                value = fields[name]
                if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                    raise ValueError()
                values[name] = value
            if hmac.compare_digest(values["signing_sha256"], values["kek_sha256"]):
                raise ValueError()
            for name, value in values.items():
                object.__setattr__(self, name, value)
        except Exception:
            raise DevelopmentRuntimeRejected() from None


def _development(value):
    if value is not True:
        raise DevelopmentRuntimeRejected() from None


def _metadata(value, *, owner, mode, limit, exact):
    if (not stat.S_ISREG(value.st_mode) or stat.S_IMODE(value.st_mode) != mode
            or owner is not None and value.st_uid != owner or value.st_nlink != 1
            or not 1 <= value.st_size <= limit
            or exact is not None and value.st_size != exact):
        raise DevelopmentRuntimeRejected() from None


def _unchanged(before, after):
    if (before.st_dev, before.st_ino, before.st_mode, before.st_uid, before.st_gid,
            before.st_nlink, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_mode, after.st_uid, after.st_gid,
            after.st_nlink, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise DevelopmentRuntimeRejected() from None


@contextmanager
def _checked_file(path, *, limit, exact=None, owner=OWNER_UID, mode=0o400):
    """Pin every path component and bounded regular file, including TLS loads."""
    directory = descriptor = None
    try:
        if (type(path) is not str or not path.startswith("/")
                or any(part in ("", ".", "..") for part in path.split("/")[1:])):
            raise ValueError()
        parts = path.split("/")[1:]
        directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        for component in parts[:-1]:
            next_directory = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                                     | os.O_CLOEXEC, dir_fd=directory)
            os.close(directory)
            directory = next_directory
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                             | os.O_CLOEXEC, dir_fd=directory)
        before = os.fstat(descriptor)
        _metadata(before, owner=owner, mode=mode, limit=limit, exact=exact)
        chunks, size = [], 0
        while size <= limit:
            chunk = os.read(descriptor, limit + 1 - size)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        raw = b"".join(chunks)
        if len(raw) != before.st_size:
            raise ValueError()
        _unchanged(before, os.fstat(descriptor))
        yield descriptor, raw
        _unchanged(before, os.fstat(descriptor))
    except Exception:
        raise DevelopmentRuntimeRejected() from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory is not None:
            os.close(directory)


def _read(path, **requirements):
    with _checked_file(path, **requirements) as (_, raw):
        return raw


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError()
        value[key] = item
    return value


def _invalid_constant(_):
    raise ValueError()


def load_config(*, development_mode: bool) -> DevelopmentConfig:
    _development(development_mode)
    try:
        raw = _read(CONFIG_PATH, limit=2048)
        fields = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_object,
                            parse_constant=_invalid_constant)
        return DevelopmentConfig(fields)
    except Exception:
        raise DevelopmentRuntimeRejected() from None


def _environment():
    # libpq has many ambient connection/TLS/GUC options. None belong to this
    # fixed fixture identity, including service files and inherited PGOPTIONS.
    if any(name.startswith("PG") for name in os.environ):
        raise DevelopmentRuntimeRejected() from None


def _connect_factory(password):
    _environment()

    @contextmanager
    def connect():
        _environment()
        # Never pool, retry, change role or pass request-derived connection GUCs.
        connection = psycopg.connect(
            host="postgres", port=5432, dbname=DATABASE, user=LOGIN_ROLE,
            password=password, sslmode="verify-full", sslrootcert=PG_CA_PATH,
            connect_timeout=5, autocommit=False, gssencmode="disable",
            options="-c statement_timeout=10000 -c lock_timeout=5000",
        )
        with connection:
            if connection.autocommit is not False:
                raise DevelopmentRuntimeRejected() from None
            with connection.cursor() as cursor:
                for query in TIMEOUT_SQL:
                    cursor.execute(query)
            yield connection

    return connect


def _startup_check(context, connect):
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(ROLE_SQL)
            role = _row(cursor, 8)
            if (role[:2] != (LOGIN_ROLE, LOGIN_ROLE)
                    or any(type(value) is not bool for value in role[2:])
                    or any(role[2:7]) or role[7] is not True):
                raise DevelopmentRuntimeRejected() from None
            cursor.execute(CONTEXT_SQL)
            if _row(cursor, 2) != (context.tenant_id, context.user_id):
                raise DevelopmentRuntimeRejected() from None
            cursor.execute(CAPABILITY_SQL)
            capabilities = _row(cursor, 4)
            if (capabilities[0] != DATABASE
                    or any(value is not True for value in capabilities[1:])):
                raise DevelopmentRuntimeRejected() from None


def _synthetic_request(action, body):
    """Reject actual key intake before executor verification/008 consumption."""
    if (action not in ("register", "replace", "revoke") or type(body) is not bytes
            or not 1 <= len(body) <= MAX_BODY_BYTES):
        raise OnboardingRejected("invalid_request") from None
    _, _, _, _, credentials, _ = _request(action, body)
    if action != "revoke" and (
            credentials._api_key != _API_KEYS[action]
            or not hmac.compare_digest(credentials._secret_key, _SECRET)
            or credentials._passphrase != _PASSPHRASE):
        raise OnboardingRejected("invalid_request") from None


class _SyntheticInfoTransport(_PrivateImmutable):
    __slots__ = ("_uid",)

    def __init__(self, config):
        object.__setattr__(self, "_uid", config.broker_uid)

    def __call__(self, signed):
        if (type(signed) is not SignedReadRequest or signed.method != "GET"
                or signed.path != INFO_PATH or signed.parameters != () or signed.body != b""):
            raise OnboardingRejected("invalid_request") from None
        signed.validate()
        return ReadResponse(200, json.dumps({
            "code": "00000", "requestTime": time.time_ns() // 1_000_000,
            "data": {"userId": self._uid, "parentId": None, "authorities": ["stor"],
                     "ips": EGRESS_IP},
        }, separators=(",", ":")).encode("ascii"))


def create_application(config: DevelopmentConfig, *, development_mode: bool) -> CredentialHTTPApplication:
    _development(development_mode)
    try:
        if type(config) is not DevelopmentConfig:
            raise ValueError()
        _environment()
        signing = _read(SIGNING_PATH, limit=32, exact=32)
        if not hmac.compare_digest(hashlib.sha256(signing).hexdigest(), config.signing_sha256):
            raise ValueError()
        ring = DevelopmentKeyFileProvider(
            KEK_DIRECTORY, (KeyFile(KEK_VERSION, "active.key", config.kek_sha256),),
            active_version=KEK_VERSION, development_mode=True, owner_uid=OWNER_UID,
        ).load()
        raw_password = _read(PASSWORD_PATH, limit=128)
        password = raw_password.decode("ascii", errors="strict")
        if re.fullmatch(r"[A-Za-z0-9_-]{32,128}", password) is None:
            raise ValueError()
        # CA is existing public bootstrap material; still pin a regular bounded
        # immutable0444 file, rejecting symlinks and multiple hard links.
        _read(PG_CA_PATH, limit=32768, owner=None, mode=0o444)
        connect = _connect_factory(password)
        context = StoreContext(tenant_id=config.tenant_id, user_id=config.user_id,
                               expected_login_role=LOGIN_ROLE)
        verifier = PasskeyRequestVerifier(key=signing, oidc_issuer=OIDC_ISSUER, origin=ORIGIN,
                                         clock=lambda: int(time.time()))
        transport = _SyntheticInfoTransport(config)
        _startup_check(context, connect)

        def execute(request_context, action, token, body):
            _synthetic_request(action, body)
            executor = PasskeyBitgetOnboarding(
                context, ring, connect=connect, verifier=verifier,
                request_context=request_context, transport=transport,
                expected_egress_ip=EGRESS_IP,
            )
            return executor.apply(action, token=token, body=body)

        return CredentialHTTPApplication(context, execute, enabled=True)
    except Exception:
        raise DevelopmentRuntimeRejected() from None


def _tls_context():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    ca = _read(CLIENT_CA_PATH, limit=32768).decode("ascii", errors="strict")
    context.load_verify_locations(cadata=ca)
    # OpenSSL reopens the pinned Linux descriptors. No path replacement or
    # runtime secret copy can substitute a different server certificate/key.
    with _checked_file(TLS_CERT_PATH, limit=32768) as (certificate, _):
        with _checked_file(TLS_KEY_PATH, limit=32768) as (key, _):
            context.load_cert_chain(f"/proc/self/fd/{certificate}", f"/proc/self/fd/{key}")
    return context


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["--development"]:
        print(STARTUP_ERROR, file=sys.stderr)
        return 1
    server = None
    result = 1
    try:
        if os.geteuid() != OWNER_UID:
            raise DevelopmentRuntimeRejected()
        config = load_config(development_mode=True)
        application = create_application(config, development_mode=True)
        tls = _tls_context()
        server = create_private_asgi_server(
            ADDRESS, tls_context=tls,
            client_certificate_sha256=frozenset((config.client_certificate_sha256,)),
            application=application, timeout_seconds=20, max_workers=4,
        )
        server.serve_forever()
        result = 0
    except KeyboardInterrupt:
        result = 0
    except Exception:
        print(STARTUP_ERROR, file=sys.stderr)
    finally:
        if server is not None:
            try:
                server.server_close()
            except Exception:
                print(STARTUP_ERROR, file=sys.stderr)
                result = 1
    return result


if __name__ == "__main__":
    raise SystemExit(main())
