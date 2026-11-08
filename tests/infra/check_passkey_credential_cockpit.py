"""Isolated real TS/WebAuthn/API/PG/Jose -> private Python/AEAD/009 fixture.

--orchestrate uses only the host stdlib and privately relays bounded JSON lines
between pinned check containers. --child alone mounts fixture DB credentials.
Synthetic bodies/keys/tokens remain in process memory and pipes, never files or
user-facing output. No physical device, email attestation or real broker proof.
"""
from contextlib import contextmanager
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import selectors
import struct
import subprocess
import sys
from time import monotonic, time
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


def child():
    global CHILD_STAGE
    # Container-only imports: host orchestration needs no dependencies.
    from datetime import datetime, timedelta, timezone
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, NoEncryption,
    )
    import psycopg
    from psycopg.rows import dict_row
    from investalo_bitget.signing import INFO_PATH
    from investalo_bitget.transport import ReadResponse
    from investalo_credentials import KEKRing
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
        check(db.execute("SELECT 1 FROM platform.schema_migrations WHERE version="
                         "'009_passkey_credential_completions'").fetchone() is not None)
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
    ring = KEKRing((("synthetic-purpose-cockpit", secrets.token_bytes(32)),),
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
    service = PasskeyBitgetOnboarding(context, ring, connect=factory, verifier=verifier,
                                     request_context=request_context, transport=broker,
                                     expected_egress_ip="203.0.113.19")
    store = CredentialStore(context, ring, connect=factory)
    emit({"kind": "configuration", "config": {
        "bound": bound, "account": str(account), "rp": RP,
        "api": "https://credential-flow-api:8000", "disabledApi": "https://credential-flow-disabled-api:8000",
        "credentialId": b64(credential_id), "userHandle": b64(user_handle),
        "privateKey": private.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode(),
        "internalKey": Path(os.environ["CREDENTIAL_FLOW_API_SECRET_FILE"]).read_text().strip(),
        "signingKey": b64(signing_key),
    }})
    executions = 0
    while True:
        command = read_input()
        if command.get("kind") == "complete":
            CHILD_STAGE = "python.audit"
            check(set(command) == {"kind"} and executions == 3 and len(broker_calls) == 2)
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
        CHILD_STAGE = "python.execute"
        check(type(command["body"]) is str and type(command["token"]) is str)
        body = command["body"].encode("utf-8")
        payload = json.loads(body)
        action = ("register", "replace", "revoke")[executions]
        assertion = verifier.verify(command["token"], action=action, body=body, context=request_context)
        check(assertion.oidc_auth_time == session["oidcAuthTime"] and assertion.passkey_checked_at > session["oidcAuthTime"])
        check(body.startswith(b" \n") and body.endswith(b"\t"))
        check(assertion.body_sha256 == hashlib.sha256(body).hexdigest())
        calls = len(broker_calls)
        try:
            service.apply(action, token=command["token"], body=body + b" ")
        except OnboardingRejected as error:
            check(error.code == "authentication_required")
        else:
            raise Failure()
        check(len(broker_calls) == calls)
        result = service.apply(action, token=command["token"], body=body).public()
        check(set(result) == {"connection_id", "credential_revision", "storage_version", "status"})
        calls = len(broker_calls)
        try:
            service.apply(action, token=command["token"], body=body)
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
        emit({"kind": "executed", "result": result, "body_sha256": hashlib.sha256(body).hexdigest()})


def orchestrate():
    """Bounded private subprocess relay; never dump stdout/stderr on failure."""
    prefix = ["bash", "infra/scripts/compose.sh", "--file", OVERLAY, "--profile", "passkey-credential-checks"]
    children = []
    names = []
    selector = selectors.DefaultSelector()
    buffers = {}
    deadline = monotonic() + 180

    def start(service):
        name = "investalo-purpose-check-" + uuid4().hex
        names.append(name)
        process = subprocess.Popen(prefix + ["run", "--rm", "--no-deps", "-T", "--name", name, service],
                                   cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, bufsize=0)
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
        python = start("credential-flow-checks")
        configuration = read(python)
        check(configuration.get("kind") == "configuration")
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
                print(f"PASS: {node_count + final['checks']} isolated TS/WebAuthn/API/PG/Python checks; synthetic keys and broker only.")
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
        for process, name in zip(children, names):
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
        if sys.argv[1:] == ["--orchestrate"]:
            orchestrate()
        elif sys.argv[1:] == ["--child"]:
            child()
        else:
            raise Failure()
    except Exception as error:
        if sys.argv[1:] == ["--child"]:
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
