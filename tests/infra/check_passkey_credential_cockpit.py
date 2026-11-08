"""Isolated real TS/WebAuthn/API/PG/Jose -> private Python/AEAD/009 fixture.

--orchestrate uses only the host stdlib and privately relays bounded JSON lines
between pinned check containers. --child alone mounts fixture DB credentials.
--service places execution in a separate restricted development container; the
administrative child prepares protected, create-only synthetic runtime files
and reads resulting audits. Client identities/bodies/tokens use private pipes,
never user-facing output. No physical device, email or real broker proof.
"""
from contextlib import contextmanager
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import selectors
import socket
import ssl
import stat
import struct
import subprocess
import sys
import tempfile
import threading
from time import monotonic, sleep, time
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
OVERLAY = "infra/compose.passkey-credential-checks.yaml"
MAX_WIRE = 32768
ORIGIN, ISSUER, RP = (
    "https://cockpit.local.test:8443", "https://auth.cockpit.local.test:8443", "cockpit.local.test",
)
CHECKS = 0
FAILED_STAGE = "unavailable"
FAILED_POSITION = ""
CHILD_STAGE = "python.imports"
DIAGNOSTIC_FUNCTIONS = {"child", "connect", "actor", "broker", "check", "read_input", "wire", "emit", "cbor", "header"}
RUNTIME_STATE = Path("/fixture-runtime-state")
RUNTIME_MARKER = ".investalo-credential-runtime-checks"
RUNTIME_MARKER_CONTENT = b"synthetic-credential-runtime-state-v1\n"


class Failure(Exception):
    """No raw driver, library, broker or SQL error is ever published."""


def check(value):
    global CHECKS
    if not value:
        raise Failure("isolated credential check rejected")
    CHECKS += 1


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def wire(value):
    raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
    check(len(raw) <= MAX_WIRE)
    return raw + b"\n"


def emit(value):
    sys.stdout.buffer.write(wire(value))
    sys.stdout.buffer.flush()


def read_input():
    raw = sys.stdin.buffer.readline(MAX_WIRE + 2)
    check(raw.endswith(b"\n") and len(raw) <= MAX_WIRE + 1)
    value = json.loads(raw)
    check(type(value) is dict)
    return value


def cbor(value):
    def header(major, length):
        if length < 24:
            return bytes([major * 32 + length])
        if length <= 255:
            return bytes([major * 32 + 24, length])
        if length <= 65535:
            return bytes([major * 32 + 25]) + struct.pack(">H", length)
        raise Failure()
    if isinstance(value, int):
        return header(0 if value >= 0 else 1, value if value >= 0 else -1 - value)
    if isinstance(value, bytes):
        return header(2, len(value)) + value
    if isinstance(value, dict):
        return header(5, len(value)) + b"".join(cbor(k) + cbor(v) for k, v in value.items())
    raise Failure()


def prepare_runtime_files(files):
    """One fresh UUID run; held FDs and O_EXCL never replace earlier material."""
    check(os.geteuid() == 10003)
    check(set(files) == {"config", "signing-key", "client-ca", "tls-cert", "tls-key", "active.key"})
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW

    def binding(parent, name, held):
        linked, info = os.stat(name, dir_fd=parent, follow_symlinks=False), os.fstat(held)
        check((linked.st_dev, linked.st_ino) == (info.st_dev, info.st_ino))

    def directory(fd):
        info = os.fstat(fd)
        check(stat.S_ISDIR(info.st_mode) and info.st_uid == info.st_gid == 10003
              and stat.S_IMODE(info.st_mode) == 0o700)

    parent = os.open(RUNTIME_STATE.parent, flags)
    state = os.open(RUNTIME_STATE.name, flags, dir_fd=parent)
    try:
        directory(state)
        marker = os.open(RUNTIME_MARKER, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=state)
        try:
            info = os.fstat(marker)
            check(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 10003
                  and stat.S_IMODE(info.st_mode) == 0o400 and info.st_nlink == 1
                  and info.st_size == len(RUNTIME_MARKER_CONTENT))
            check(os.read(marker, len(RUNTIME_MARKER_CONTENT) + 1) == RUNTIME_MARKER_CONTENT)
            binding(state, RUNTIME_MARKER, marker)
        finally:
            os.close(marker)
        run = str(uuid4())
        os.mkdir(run, 0o700, dir_fd=state)
        run_fd = os.open(run, flags, dir_fd=state)
        try:
            directory(run_fd)
            os.mkdir("keks", 0o700, dir_fd=run_fd)
            kek_fd = os.open("keks", flags, dir_fd=run_fd)
            try:
                directory(kek_fd)
                for name, data in files.items():
                    check(type(data) is bytes and 1 <= len(data) <= 8192)
                    target = kek_fd if name == "active.key" else run_fd
                    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o400, dir_fd=target)
                    try:
                        info = os.fstat(fd)
                        check(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 10003
                              and stat.S_IMODE(info.st_mode) == 0o400 and info.st_nlink == 1)
                        check(os.write(fd, data) == len(data))
                        os.fsync(fd)
                        binding(target, name, fd)
                    finally:
                        os.close(fd)
                binding(run_fd, "keks", kek_fd)
                binding(state, run, run_fd)
                binding(parent, RUNTIME_STATE.name, state)
            finally:
                os.close(kek_fd)
        finally:
            os.close(run_fd)
        return run
    finally:
        os.close(state)
        os.close(parent)


def child(*, https=False, service=False):
    global CHILD_STAGE
    # Container-only imports: host orchestration needs no dependencies.
    from datetime import datetime, timedelta, timezone
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, NoEncryption,
    )
    import psycopg
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    from psycopg.rows import dict_row
    from investalo_bitget.signing import INFO_PATH
    from investalo_bitget.transport import ReadResponse
    from investalo_credentials import AADBinding, KEKRing, load_envelope, open_envelope
    from investalo_credential_store import CredentialStore, StoreContext
    from investalo_credential_store.bitget_payload import decode_credentials
    from investalo_credential_store.passkey_onboarding import PasskeyBitgetOnboarding
    from investalo_credential_store.passkey_request_assertion import (
        PasskeyRequestContext, PasskeyRequestVerifier,
    )
    from investalo_credential_store.request_assertion import OnboardingRejected

    CHILD_STAGE = "python.role"
    check(os.geteuid() == 10003 and os.environ.get("PGDATABASE") == "investalo_credentials_checks")
    identities = {
        "admin": ("API_TEST_ADMIN_USER", "API_TEST_ADMIN_PASSWORD_FILE"),
        "runtime": ("PGUSER", "PGPASSWORD_FILE"),
        "credential": ("CREDENTIAL_TEST_USER_A", "CREDENTIAL_TEST_PASSWORD_A_FILE"),
    }

    @contextmanager
    def connect(identity, *, tuples=False):
        check(not service or identity != "credential")
        name, password_file = identities[identity]
        params = dict(host=os.environ["PGHOST"], port=int(os.environ["PGPORT"]),
                      dbname=os.environ["PGDATABASE"], user=os.environ[name],
                      password=Path(os.environ[password_file]).read_text().strip(),
                      sslmode="verify-full", sslrootcert=os.environ["PGSSLROOTCERT"],
                      connect_timeout=5)
        if not tuples:
            params["row_factory"] = dict_row
        with psycopg.connect(**params) as db:
            db.execute("SET LOCAL statement_timeout='10s'")
            db.execute("SET LOCAL lock_timeout='5s'")
            yield db

    CHILD_STAGE = "python.setup"
    tenant, user, account = uuid4(), uuid4(), uuid4()
    subject = "synthetic-credential-cockpit-" + uuid4().hex
    credential_id, user_handle = secrets.token_bytes(32), secrets.token_bytes(32)
    private = ec.generate_private_key(ec.SECP256R1())
    numbers = private.public_key().public_numbers()
    public = cbor({1: 2, 3: -7, -1: 1,
                   -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")})
    ticket_hash, enrollment_binding = secrets.token_bytes(32), secrets.token_bytes(32)
    with connect("admin") as db:
        check(db.execute("SELECT current_database() AS database,session_user AS login").fetchone()
              == {"database": "investalo_credentials_checks", "login": "investalo_migration"})
        for version, checksum in (
            ("008_passkey_credential_authorizations",
             "9328008652ad697a306093301d9488fe3e0b184a3ffd8333f7beda5924712c57"),
            ("009_passkey_credential_completions",
             "435d658458c6be7359ab19ad575421fb843c8756975710cc651eff41c4d62b75"),
        ):
            check(db.execute("SELECT checksum FROM platform.schema_migrations WHERE version=%s",
                             (version,)).fetchone() == {"checksum": checksum})
        check(os.environ["CREDENTIAL_TEST_USER_A"] == "investalo_credentials_tests_a")
        db.execute("INSERT INTO platform.tenants(id,name) VALUES(%s,'Synthetic purpose cockpit')", (tenant,))
        db.execute("INSERT INTO platform.users(id,oidc_issuer,oidc_subject) VALUES(%s,%s,%s)",
                   (user, ISSUER, subject))
        db.execute("INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES(%s,%s,'owner')",
                   (tenant, user))
        db.execute("INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency) VALUES"
                   "(%s,%s,'Synthetic purpose account','bitget','read_only','USDT')", (tenant, account))
        db.execute("INSERT INTO platform.credential_role_bindings(database_role,tenant_id,user_id) VALUES(%s,%s,%s)"
                   " ON CONFLICT(database_role) DO UPDATE SET tenant_id=excluded.tenant_id,user_id=excluded.user_id",
                   (os.environ["CREDENTIAL_TEST_USER_A"], tenant, user))
        # Explicit synthetic administrative approval only. Real assertion crypto
        # is performed by SimpleWebAuthn in the TS driver for every action.
        db.execute("SELECT platform.passkey_issue_enrollment(%s,%s,%s,%s,%s,%s,%s,%s)",
                   (tenant, user, RP, ticket_hash, user_handle, 0,
                    datetime.now(timezone.utc) + timedelta(seconds=300), uuid4()))

    def actor(db):
        for name, value in {"app.tenant_id": str(tenant), "app.user_id": str(user),
                            "app.oidc_issuer": ISSUER, "app.oidc_subject": subject}.items():
            db.execute("SELECT set_config(%s,%s,true)", (name, value))

    CHILD_STAGE = "python.enroll"
    with connect("runtime") as db:
        actor(db)
        claim = db.execute("SELECT * FROM platform.passkey_claim_enrollment(%s,%s,%s,%s,%s)",
                           (ticket_hash, RP, enrollment_binding, 0, int(time()))).fetchone()
    with connect("runtime") as db:
        actor(db)
        factor = db.execute("SELECT * FROM platform.passkey_finish_enrollment(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (claim["claim_id"], enrollment_binding, credential_id, public,
                             0, False, False, 0, int(time()))).fetchone()
    check(factor["storage_version"] == 1 and factor["status"] == "active")

    CHILD_STAGE = "python.keys"
    session = dict(issuer=ISSUER, subject=subject, oidcAuthTime=int(time()) - 600,
                   tenantId=str(tenant), authEpoch=0, expiresAt=int(time()) + 600,
                   displayName="Synthetic purpose", tenantName="Synthetic purpose cockpit",
                   csrf=b64(secrets.token_bytes(32)))
    bound = dict(handle=b64(secrets.token_bytes(32)), session=session, origin=ORIGIN)
    binding = hashlib.sha256(json.dumps([
        "passkey-action-proof-v1", bound["handle"], session["csrf"], session["issuer"],
        subject, str(tenant), 0, session["oidcAuthTime"], ORIGIN, session["expiresAt"],
    ], separators=(",", ":")).encode()).hexdigest()
    signing_key = secrets.token_bytes(32)
    kek = secrets.token_bytes(32)
    ring = KEKRing((("synthetic-purpose-cockpit", kek),),
                   active_version="synthetic-purpose-cockpit")
    broker_uid = str(10**19 + uuid4().int % 10**19)
    broker_calls = []

    def broker(signed):
        check(signed.path == INFO_PATH and signed.method == "GET")
        broker_calls.append(signed.path)
        return ReadResponse(200, json.dumps({
            "code": "00000", "requestTime": int(time() * 1000),
            "data": {"userId": broker_uid, "parentId": None, "authorities": ["stor"],
                     "ips": "203.0.113.19"},
        }, separators=(",", ":")).encode())

    context = StoreContext(tenant_id=tenant, user_id=user,
                           expected_login_role=os.environ["CREDENTIAL_TEST_USER_A"])
    request_context = PasskeyRequestContext(
        tenant_id=tenant, user_id=user, subject=subject, auth_epoch=0,
        oidc_auth_time=session["oidcAuthTime"], session_binding=binding,
        session_expires_at=session["expiresAt"],
    )
    verifier = PasskeyRequestVerifier(key=signing_key, oidc_issuer=ISSUER, origin=ORIGIN,
                                     clock=lambda: int(time()))
    factory = lambda: connect("credential", tuples=True)
    store = None if service else CredentialStore(context, ring, connect=factory)
    config = {
        "bound": bound, "account": str(account), "rp": RP,
        "userId": str(user),
        "api": "https://credential-flow-api:8000", "disabledApi": "https://credential-flow-disabled-api:8000",
        "credentialId": b64(credential_id), "userHandle": b64(user_handle),
        "privateKey": private.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode(),
        "internalKey": Path(os.environ["CREDENTIAL_FLOW_API_SECRET_FILE"]).read_text().strip(),
        "signingKey": b64(signing_key),
    }
    executions = 0
    executed = []

    def audit(action, token, body):
        """Administrative reads and pure AEAD only; never consume/lock/apply."""
        nonlocal executions
        global CHILD_STAGE
        CHILD_STAGE = "python.audit"
        check(service and action == ("register", "replace", "revoke")[executions])
        assertion = verifier.verify(token, action=action, body=body, context=request_context)
        check(assertion.oidc_auth_time == session["oidcAuthTime"]
              and assertion.passkey_checked_at > session["oidcAuthTime"])
        check(body.startswith(b" \n") and body.endswith(b"\t"))
        check(assertion.body_sha256 == hashlib.sha256(body).hexdigest())
        payload = json.loads(body)
        with connect("admin") as db:
            record = db.execute("SELECT outcome,transaction_id FROM platform.passkey_credential_completion_audit "
                                "WHERE authorization_id=%s", (assertion.authorization_id,)).fetchone()
            authorization = db.execute("SELECT state,receipt,lock_transaction FROM platform.passkey_credential_authorizations "
                                       "WHERE authorization_id=%s", (assertion.authorization_id,)).fetchone()
            check(record["outcome"] == "completed" and authorization["state"] == "locked"
                  and record["transaction_id"] == authorization["lock_transaction"])
            check(authorization["receipt"]["body_sha256"] == hashlib.sha256(body).hexdigest())
            protected = db.execute("SELECT * FROM platform.credential_connections "
                                   "WHERE tenant_id=%s AND user_id=%s AND platform_account_id=%s",
                                   (tenant, user, account)).fetchone()
            expected = ((1, 1, "active"), (2, 2, "active"), (2, 3, "revoked"))[executions]
            check((protected["credential_revision"], protected["storage_version"], protected["status"]) == expected)
            result = dict(connection_id=str(protected["connection_id"]), credential_revision=expected[0],
                          storage_version=expected[1], status=expected[2])
            check(protected["broker_uid"] == broker_uid and protected["parent_uid"] is None)
            check(protected["tenant_id"] == tenant and protected["user_id"] == user)
            stored_json = json.dumps(protected["envelope"])
            check("synthetic-purpose-secret" not in stored_json and "synthetic-purpose-passphrase" not in stored_json)
            # No credential LOGIN session, store client or executor is used by
            # this audit. The runtime is the sole writer of this authorization.
            binding = AADBinding(**{name: protected[name] for name in (
                "tenant_id", "user_id", "platform_account_id", "connection_id", "broker_uid", "parent_uid",
                "credential_revision", "broker", "account_family", "connection_mode",
            )})
            opened = open_envelope(load_envelope(stored_json), binding, ring)
            decoded = decode_credentials(opened)
            check(decoded._secret_key.decode() == "synthetic-purpose-secret-päß-1e0")
            check(decoded._api_key == ("synthetic-purpose-api" if executions == 0 else "synthetic-purpose-replacement"))
            if action != "revoke":
                check(decoded._api_key == payload["credentials"]["api_key"])
            count = db.execute("SELECT count(*) AS n FROM platform.passkey_credential_completion_audit "
                               "WHERE tenant_id=%s AND user_id=%s", (tenant, user)).fetchone()
            check(count["n"] == executions + 1)
        executions += 1
        return result

    def execute(trusted, action, token, body):
        nonlocal executions
        global CHILD_STAGE
        check(not service)
        CHILD_STAGE = "python.execute"
        check(all(getattr(trusted, field) == getattr(request_context, field)
                  for field in request_context.__slots__))
        executor = PasskeyBitgetOnboarding(context, ring, connect=factory, verifier=verifier,
                                          request_context=trusted, transport=broker,
                                          expected_egress_ip="203.0.113.19")
        payload = json.loads(body)
        assertion = verifier.verify(token, action=action, body=body, context=trusted)
        check(assertion.oidc_auth_time == session["oidcAuthTime"] and assertion.passkey_checked_at > session["oidcAuthTime"])
        check(body.startswith(b" \n") and body.endswith(b"\t"))
        check(assertion.body_sha256 == hashlib.sha256(body).hexdigest())
        calls = len(broker_calls)
        try:
            executor.apply(action, token=token, body=body + b" ")
        except OnboardingRejected as error:
            check(error.code == "authentication_required")
        else:
            raise Failure()
        check(len(broker_calls) == calls)
        value = executor.apply(action, token=token, body=body)
        check(action == ("register", "replace", "revoke")[executions])
        result = value.public()
        check(set(result) == {"connection_id", "credential_revision", "storage_version", "status"})
        calls = len(broker_calls)
        try:
            executor.apply(action, token=token, body=body)
        except OnboardingRejected as error:
            check(error.code in {"access_denied", "concurrent_change"})
        else:
            raise Failure()
        check(len(broker_calls) == calls)
        with connect("admin") as db:
            record = db.execute("SELECT outcome,transaction_id FROM platform.passkey_credential_completion_audit "
                                "WHERE authorization_id=%s", (assertion.authorization_id,)).fetchone()
            authorization = db.execute("SELECT receipt,lock_transaction FROM platform.passkey_credential_authorizations "
                                       "WHERE authorization_id=%s", (assertion.authorization_id,)).fetchone()
            check(record["outcome"] == "completed" and record["transaction_id"] == authorization["lock_transaction"])
            check(authorization["receipt"]["body_sha256"] == hashlib.sha256(body).hexdigest())
            protected = db.execute("SELECT envelope FROM platform.credential_connections "
                                   "WHERE tenant_id=%s AND connection_id=%s", (tenant, UUID(result["connection_id"]))).fetchone()
            stored_json = json.dumps(protected["envelope"])
            check("synthetic-purpose-secret" not in stored_json and "synthetic-purpose-passphrase" not in stored_json)
        if action != "revoke":
            opened = store.read(UUID(result["connection_id"]))
            decoded = decode_credentials(opened.payload)
            check(decoded._api_key == payload["credentials"]["api_key"])
            check(decoded._secret_key.decode() == payload["credentials"]["secret"])
            check(opened.snapshot.binding.broker_uid == broker_uid)
        executions += 1
        executed.append((token, body, result))
        return value

    servers, threads = [], []
    with tempfile.TemporaryDirectory(prefix="synthetic-credential-tls-") as tls_dir:
        if https or service:
            from investalo_credential_store.private_http import (
                CredentialHTTPApplication, create_private_https_server,
            )
            hostname = "credential-restricted.cockpit.local.test" if service else "credential-flow-executor.cockpit.local.test"
            ca_key = ec.generate_private_key(ec.SECP256R1())
            ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic credential CA")])
            stamp = datetime.now(timezone.utc)
            ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
                  .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
                  .not_valid_before(stamp - timedelta(minutes=1)).not_valid_after(stamp + timedelta(hours=1))
                  .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                  .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
                  .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                                 critical=False)
                  .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False,
                                               key_encipherment=False, data_encipherment=False,
                                               key_agreement=False, key_cert_sign=True, crl_sign=True,
                                               encipher_only=False, decipher_only=False), critical=True)
                  .sign(ca_key, hashes.SHA256()))

            def leaf(name, usage, *, server=False):
                key = ec.generate_private_key(ec.SECP256R1())
                builder = (x509.CertificateBuilder()
                           .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
                           .issuer_name(ca_name).public_key(key.public_key())
                           .serial_number(x509.random_serial_number())
                           .not_valid_before(stamp - timedelta(minutes=1))
                           .not_valid_after(stamp + timedelta(hours=1))
                           .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                           .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                                          critical=False)
                           .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                                          critical=False)
                           .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                                        key_encipherment=False, data_encipherment=False,
                                                        key_agreement=False, key_cert_sign=False, crl_sign=False,
                                                        encipher_only=False, decipher_only=False), critical=True)
                           .add_extension(x509.ExtendedKeyUsage([usage]), critical=False))
                if server:
                    builder = builder.add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]),
                                                    critical=False)
                certificate = builder.sign(ca_key, hashes.SHA256())
                return key, certificate

            server_key, server_cert = leaf(hostname, ExtendedKeyUsageOID.SERVER_AUTH, server=True)
            client_key, client_cert = leaf("Synthetic credential BFF", ExtendedKeyUsageOID.CLIENT_AUTH)
            other_key, other_cert = leaf("Unpinned synthetic BFF", ExtendedKeyUsageOID.CLIENT_AUTH)
            pins = frozenset({client_cert.fingerprint(hashes.SHA256()).hex()})
            if service:
                runtime_config = dict(schema="investalo-credential-development-service/1",
                                      tenant_id=str(tenant), user_id=str(user), broker_uid=broker_uid,
                                      signing_sha256=hashlib.sha256(signing_key).hexdigest(),
                                      kek_sha256=hashlib.sha256(kek).hexdigest(),
                                      client_certificate_sha256=next(iter(pins)))
                config["runtimeRun"] = prepare_runtime_files({
                    "config": json.dumps(runtime_config, separators=(",", ":")).encode("ascii"),
                    "signing-key": signing_key, "active.key": kek,
                    "client-ca": ca.public_bytes(Encoding.PEM),
                    "tls-cert": server_cert.public_bytes(Encoding.PEM),
                    "tls-key": server_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()),
                })
            else:
                server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                server_context.minimum_version = ssl.TLSVersion.TLSv1_2
                server_context.verify_mode = ssl.CERT_REQUIRED
                server_context.load_verify_locations(cadata=ca.public_bytes(Encoding.PEM).decode())
                cert_file, key_file = Path(tls_dir) / "server.pem", Path(tls_dir) / "server.key"
                cert_file.write_bytes(server_cert.public_bytes(Encoding.PEM))
                key_file.write_bytes(server_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
                key_file.chmod(0o600)
                server_context.load_cert_chain(str(cert_file), str(key_file))
                for port, enabled in ((9443, True), (9444, False)):
                    application = CredentialHTTPApplication(context, execute, enabled=enabled)
                    server = create_private_https_server(("0.0.0.0", port), tls_context=server_context,
                                                         client_certificate_sha256=pins, application=application)
                    servers.append(server)
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    threads.append(thread)
            config["executor"] = {
                "origin": f"https://{hostname}:9443", "disabledOrigin": f"https://{hostname}:9444",
                "ca": ca.public_bytes(Encoding.PEM).decode(),
                "certificate": client_cert.public_bytes(Encoding.PEM).decode(),
                "privateKey": client_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode(),
                "otherCertificate": other_cert.public_bytes(Encoding.PEM).decode(),
                "otherPrivateKey": other_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode(),
                "service": service,
            }
        emit({"kind": "configuration", "config": config})
        if service:
            CHILD_STAGE = "python.readiness"
            check(read_input() == {"kind": "ready"})
            client_context = ssl.create_default_context(cadata=config["executor"]["ca"])
            cert_file, key_file = Path(tls_dir) / "client.pem", Path(tls_dir) / "client.key"
            cert_file.write_text(config["executor"]["certificate"])
            key_file.write_text(config["executor"]["privateKey"])
            key_file.chmod(0o600)
            client_context.load_cert_chain(str(cert_file), str(key_file))
            ready_deadline = monotonic() + 25
            # Only idempotent unsupported GET requests may retry during startup.
            for path, expected in (("/not-a-route", b" 404 "), ("/v1/credentials/bitget/register", b" 405 ")):
                while True:
                    check(monotonic() < ready_deadline)
                    try:
                        with client_context.wrap_socket(socket.create_connection((hostname, 9443), timeout=2),
                                                        server_hostname=hostname) as peer:
                            peer.sendall(f"GET {path} HTTP/1.1\r\nHost: {hostname}\r\nConnection: close\r\n\r\n".encode())
                            status = peer.recv(512).split(b"\r\n", 1)[0]
                        check(expected in status)
                        break
                    except (OSError, ssl.SSLError):
                        sleep(0.1)
            emit({"kind": "ready"})
        audits = 0
        try:
            while True:
                command = read_input()
                if command.get("kind") == "complete":
                    CHILD_STAGE = "python.audit"
                    check(set(command) == {"kind"} and executions == 3
                          and len(broker_calls) == (0 if service else 2))
                    check(not https and not service or audits == 3)
                    with connect("admin") as db:
                        rows = db.execute("SELECT action,outcome FROM platform.passkey_credential_completion_audit "
                                          "WHERE tenant_id=%s AND user_id=%s ORDER BY occurred_at", (tenant, user)).fetchall()
                        check(rows == [{"action": action, "outcome": "completed"}
                                       for action in ("register", "replace", "revoke")])
                        key = db.execute("SELECT sign_count,storage_version FROM platform.passkey_credentials "
                                         "WHERE passkey_id=%s", (factor["passkey_id"],)).fetchone()
                        check(key == {"sign_count": 3, "storage_version": 4})
                        count = db.execute("SELECT count(*) AS n FROM platform.passkey_credential_authorizations a "
                                           "JOIN platform.passkey_action_proofs p ON p.proof_id=a.proof_id "
                                           "WHERE p.tenant_id=%s AND p.user_id=%s AND a.state='locked'", (tenant, user)).fetchone()
                        check(count["n"] == 3)
                    emit({"kind": "complete", "checks": CHECKS})
                    return
                check(set(command) == {"kind", "token", "body"} and command["kind"] == "execute")
                check(type(command["body"]) is str and type(command["token"]) is str)
                body = command["body"].encode("utf-8")
                if service:
                    result = audit(("register", "replace", "revoke")[executions], command["token"], body)
                    audits += 1
                elif https:
                    check(audits < len(executed))
                    token, actual_body, result = executed[audits]
                    check(command["token"] == token and body == actual_body)
                    audits += 1
                else:
                    result = execute(request_context, ("register", "replace", "revoke")[executions],
                                     command["token"], body).public()
                emit({"kind": "executed", "result": result, "body_sha256": hashlib.sha256(body).hexdigest()})
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(timeout=3)


def inspect_runtime(name, run):
    """Only allowlisted metadata; never request logs, environment or full JSON."""
    projection = (
        '{"user":{{json .Config.User}},"readonly":{{json .HostConfig.ReadonlyRootfs}},'
        '"privileged":{{json .HostConfig.Privileged}},"caps":{{json .HostConfig.CapDrop}},'
        '"security":{{json .HostConfig.SecurityOpt}},"ports":{{json .HostConfig.PortBindings}},'
        '"logging":{{json .HostConfig.LogConfig.Type}},"groups":{{json .HostConfig.GroupAdd}},"networks":['
        '{{range $name,$network := .NetworkSettings.Networks}}{{json $name}},{{end}}null],'
        '"mounts":[{{range .Mounts}}{"type":{{json .Type}},"source":{{json .Source}},'
        '"target":{{json .Destination}},"rw":{{json .RW}}},{{end}}null]}'
    )
    result = subprocess.run(["docker", "inspect", "--format", projection, name], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=8, check=False)
    check(result.returncode == 0 and len(result.stdout) <= MAX_WIRE)
    value = json.loads(result.stdout)
    check(value["user"] == "10003:10003" and value["readonly"] is True and value["privileged"] is False)
    check(value["caps"] == ["ALL"] and value["security"] == ["no-new-privileges:true"])
    check(value["logging"] == "none" and value["ports"] in ({}, None))
    check(value["groups"] in ([], None))
    check(set(value["networks"][:-1]) == {"investalo-local_database", "investalo-local_passkey_credential"})
    base = Path("/tmp/investalo-credential-runtime-state") / run
    expected = {
        "/run/secrets/credentials_test_password_a": ROOT / "infra/local/credentials_test_password_a",
        "/run/secrets/local_ca_cert": ROOT / "infra/local/local_ca_cert",
        "/run/credential-keks": base / "keks",
        **{"/run/secrets/credential_service_" + target: base / source for target, source in (
            ("config", "config"), ("signing_key", "signing-key"), ("client_ca", "client-ca"),
            ("tls_cert", "tls-cert"), ("tls_key", "tls-key"),
        )},
    }
    mounts = value["mounts"][:-1]
    # Docker reports tmpfs separately on some supported engine versions.
    mounts = [mount for mount in mounts if mount["type"] != "tmpfs"]
    check(len(mounts) == len(expected) and {mount["target"] for mount in mounts} == set(expected))
    for mount in mounts:
        check(mount["type"] == "bind" and mount["rw"] is False
              and mount["source"] == str(expected[mount["target"]]))


def inspect_administration(name):
    """Confirm the setup/audit child has no bound credential LOGIN secret."""
    projection = ('[{{range .Mounts}}{"type":{{json .Type}},'
                  '"target":{{json .Destination}},"rw":{{json .RW}}},{{end}}null]')
    result = subprocess.run(["docker", "inspect", "--format", projection, name], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=8, check=False)
    check(result.returncode == 0 and len(result.stdout) <= MAX_WIRE)
    mounts = [mount for mount in json.loads(result.stdout)[:-1] if mount["type"] != "tmpfs"]
    expected = {
        "/run/secrets/platform_runtime_password": False,
        "/run/secrets/platform_migration_password": False,
        "/run/secrets/credential_flow_api_secret": False,
        "/run/secrets/local_ca_cert": False,
        "/app/tests/infra/check_passkey_credential_cockpit.py": False,
        "/fixture-runtime-state": True,
    }
    check(len(mounts) == len(expected) and {mount["target"] for mount in mounts} == set(expected))
    check(all(mount["type"] == "bind" and mount["rw"] is expected[mount["target"]] for mount in mounts))


def orchestrate(*, https=False, service=False):
    """Bounded private subprocess relay; never dump stdout/stderr on failure."""
    prefix = ["bash", "infra/scripts/compose.sh", "--file", OVERLAY, "--profile", "passkey-credential-checks"]
    children = []
    owned = []
    selector = selectors.DefaultSelector()
    buffers = {}
    deadline = monotonic() + 180

    def start(service_name, *, runtime_run=None):
        name = "investalo-purpose-check-" + uuid4().hex
        args = prefix + ["run", "--rm", "--no-deps", "-T", "--use-aliases", "--name", name, service_name]
        if service_name == "credential-flow-checks" and https:
            args += ["python", "/app/tests/infra/check_passkey_credential_cockpit.py", "--child", "--https"]
        environment = os.environ.copy()
        # An inherited selector cannot redirect the fixed fixture mount.
        environment.pop("CREDENTIAL_RUNTIME_CHECK_RUN", None)
        if runtime_run is not None:
            check(str(UUID(runtime_run)) == runtime_run)
            environment["CREDENTIAL_RUNTIME_CHECK_RUN"] = runtime_run
        process = subprocess.Popen(args,
                                   cwd=ROOT, env=environment,
                                   stdin=subprocess.DEVNULL if runtime_run else subprocess.PIPE,
                                   stdout=subprocess.DEVNULL if runtime_run else subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, bufsize=0)
        owned.append((process, name))
        if runtime_run:
            return process, name
        children.append(process)
        buffers[process] = bytearray()
        selector.register(process.stdout, selectors.EVENT_READ, process)
        return process

    def read(process):
        global FAILED_STAGE, FAILED_POSITION
        buffer = buffers[process]
        while b"\n" not in buffer:
            check(monotonic() < deadline)
            ready = selector.select(min(20, max(0, deadline - monotonic())))
            check(bool(ready))
            for key, _ in ready:
                chunk = os.read(key.fileobj.fileno(), 4096)
                if not chunk and key.data is not process:
                    selector.unregister(key.fileobj)
                    continue
                check(bool(chunk))
                buffers[key.data].extend(chunk)
                check(len(buffers[key.data]) <= MAX_WIRE + 1)
        raw, _, remaining = buffer.partition(b"\n")
        buffers[process] = bytearray(remaining)
        value = json.loads(raw)
        check(type(value) is dict)
        if value.get("kind") == "failed":
            allowed = {"configuration", "disabled"} | {
                action + "." + phase for action in ("register", "replace", "revoke")
                for phase in ("prepare", "finish", "execute")
            } | {"python." + phase for phase in (
                "imports", "role", "setup", "enroll", "keys", "execute", "audit",
                "readiness",
            )}
            stage = value.get("stage")
            if type(stage) is str and stage in allowed:
                FAILED_STAGE = stage
                function, line = value.get("function"), value.get("line")
                if (type(function) is str and function in DIAGNOSTIC_FUNCTIONS
                        and type(line) is int and 1 <= line <= 1000):
                    FAILED_POSITION = f"; {function}:{line}"
            raise Failure()
        return value

    def send(process, value):
        process.stdin.write(wire(value))
        process.stdin.flush()

    try:
        python = start("credential-service-checks" if service else "credential-flow-checks")
        configuration = read(python)
        check(configuration.get("kind") == "configuration")
        if service:
            inspect_administration(owned[0][1])
            run = configuration["config"].pop("runtimeRun")
            check(type(run) is str and str(UUID(run)) == run)
            runtime, runtime_name = start("credential-restricted", runtime_run=run)
            # The read-only TLS handshake/GET probe waits boundedly for startup.
            # No credential request is retried by this orchestrator.
            send(python, {"kind": "ready"})
            check(read(python) == {"kind": "ready"} and runtime.poll() is None)
            inspect_runtime(runtime_name, run)
        node = start("credential-flow-node")
        send(node, configuration)
        while True:
            message = read(node)
            if message.get("kind") == "complete":
                check(set(message) == {"kind", "checks"} and type(message["checks"]) is int)
                node_count = message["checks"]
                send(python, {"kind": "complete"})
                final = read(python)
                check(final.get("kind") == "complete" and type(final["checks"]) is int)
                for process in children:
                    process.stdin.close()
                    check(process.wait(timeout=10) == 0)
                transport = "/restricted-service/mTLS" if service else "/mTLS" if https else ""
                print(f"PASS: {node_count + final['checks']} isolated TS/WebAuthn/API/PG/Python{transport} checks; synthetic keys and broker only.")
                return
            check(set(message) == {"kind", "token", "body"} and message["kind"] == "execute")
            send(python, message)
            result = read(python)
            check(set(result) == {"kind", "result", "body_sha256"} and result["kind"] == "executed")
            send(node, result)
    finally:
        selector.close()
        # Only unique names created by this invocation are stopped. --rm removes
        # these one-off fixtures; existing public or development services stay.
        for process, name in owned:
            if process.poll() is None:
                try:
                    subprocess.run(["docker", "stop", "--time", "3", name], cwd=ROOT,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8, check=False)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    try:
        if sys.argv[1:] in (["--orchestrate"], ["--orchestrate", "--https"], ["--orchestrate", "--service"]):
            orchestrate(https="--https" in sys.argv[1:], service="--service" in sys.argv[1:])
        elif sys.argv[1:] in (["--child"], ["--child", "--https"], ["--child", "--service"]):
            child(https="--https" in sys.argv[1:], service="--service" in sys.argv[1:])
        else:
            raise Failure()
    except Exception as error:
        if sys.argv[1:] in (["--child"], ["--child", "--https"], ["--child", "--service"]):
            diagnostic = {"kind": "failed", "stage": CHILD_STAGE}
            trace = error.__traceback__
            while trace is not None:
                code = trace.tb_frame.f_code
                if (code.co_filename == __file__ and code.co_name in DIAGNOSTIC_FUNCTIONS):
                    diagnostic.update(function=code.co_name, line=trace.tb_lineno)
                trace = trace.tb_next
            emit(diagnostic)
        else:
            print(f"FAIL: isolated passkey credential cockpit fixture ({FAILED_STAGE}{FAILED_POSITION}).", file=sys.stderr)
        raise SystemExit(1) from None
