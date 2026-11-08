"""Isolated real HTTPS -> Next BFF -> signed API -> fixture PostgreSQL check.

Only unique synthetic users/tickets/keys are created. The test operator approval
is a synthetic fixture, never a real email attestation. Encrypted fixture sessions
are seeded in a dedicated check mount; no application authentication bypass is
introduced. This does not prove physical browser, biometrics or hardware use.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import ssl
import stat
import struct
import sys
from time import monotonic, sleep, time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


ORIGIN = "https://cockpit.local.test:8443"
DISABLED_ORIGIN = "https://cockpit.local.test:9443"
ISSUER = "https://auth.cockpit.local.test:8443"
RP = "cockpit.local.test"
PREFIX = "/api/passkeys/actions"
CHECKS = 0
STAGE = "configuration"


class CheckFailure(Exception):
    """Static step name only: never publish tickets, sessions or key material."""


def check(condition, name):
    global CHECKS
    if not condition:
        raise CheckFailure(name)
    CHECKS += 1


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def unb64(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def wire(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()


def cbor(value):
    """Minimal deterministic CBOR for the exact synthetic none/EC2-P256 record."""
    def header(major, length):
        if length < 24:
            return bytes([major * 32 + length])
        if length <= 255:
            return bytes([major * 32 + 24, length])
        if length <= 65535:
            return bytes([major * 32 + 25]) + struct.pack(">H", length)
        raise ValueError("Synthetic CBOR size unavailable")
    if isinstance(value, int):
        return header(0 if value >= 0 else 1, value if value >= 0 else -1 - value)
    if isinstance(value, bytes):
        return header(2, len(value)) + value
    if isinstance(value, str):
        encoded = value.encode()
        return header(3, len(encoded)) + encoded
    if isinstance(value, dict):
        return header(5, len(value)) + b"".join(cbor(k) + cbor(v) for k, v in value.items())
    raise ValueError("Synthetic CBOR value unavailable")


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, _request, _fp, _code, _msg, _headers, _url):
        return None


def opener():
    return build_opener(
        HTTPSHandler(context=ssl.create_default_context(cafile=os.environ["PGSSLROOTCERT"])),
        NoRedirects(),
    )


def request(path, session=None, payload=None, *, raw=None, headers=None, origin=ORIGIN):
    values = {"Origin": origin, "Sec-Fetch-Site": "same-origin"}
    if session:
        values.update({
            "Cookie": "__Host-investalo-session=" + session["handle"],
            "X-CSRF-Token": session["value"]["csrf"],
        })
    body = raw if raw is not None else wire(payload) if payload is not None else None
    if body is not None:
        values["Content-Type"] = "application/json"
    values.update(headers or {})
    req = Request(origin + path, data=body, headers=values, method="POST" if body is not None else "GET")
    try:
        response = opener().open(req, timeout=15)
    except HTTPError as failure:
        response = failure
    with response:
        data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise CheckFailure("bounded HTTPS response")
        content_type = response.headers.get_content_type()
        result = json.loads(data) if content_type == "application/json" else data.decode("utf-8")
        return response.status, result, dict(response.headers)


def json_post(path, session, payload, **options):
    status, value, headers = request(path, session, payload, **options)
    if "no-store" not in next((v for k, v in headers.items() if k.lower() == "cache-control"), ""):
        raise CheckFailure("proof/enrollment response is not cached")
    return status, value


def admin():
    return psycopg.connect(
        host=os.environ["PGHOST"], port=os.environ["PGPORT"], dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=Path(os.environ["PGPASSWORD_FILE"]).read_text().rstrip("\r\n"),
        sslmode=os.environ["PGSSLMODE"], sslrootcert=os.environ["PGSSLROOTCERT"],
        connect_timeout=3, row_factory=dict_row,
    )


@contextmanager
def fixture_state():
    """Only the pre-provisioned dedicated check mount may contain seeded sessions.

    Directory descriptors and O_NOFOLLOW prevent an accepted path being replaced
    with a symlink between checking ownership and writing the fixture file.
    No directory is created, re-owned or chmodded by this harness.
    """
    if os.environ.get("PASSKEY_CHECK_STATE_DIR") != "/app/check-state" or os.geteuid() != 10003:
        raise CheckFailure("dedicated nonroot fixture-state configuration")
    directory = marker = sessions = None
    try:
        directory = os.open("/app/check-state", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(directory)
        if info.st_uid != 10002 or info.st_gid != 10010 or stat.S_IMODE(info.st_mode) != 0o2770:
            raise CheckFailure("dedicated fixture-state owner and permissions")
        marker = os.open(".investalo-passkey-browser-checks", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
        info = os.fstat(marker)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 10003 or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o400 or info.st_size > 64
                or os.read(marker, 65) != b"synthetic-fixture-state-v1\n"):
            raise CheckFailure("explicit protected synthetic fixture-state marker")
        sessions = os.open("sessions", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
        info = os.fstat(sessions)
        if info.st_uid != 10003 or info.st_gid != 10010 or stat.S_IMODE(info.st_mode) != 0o2770:
            raise CheckFailure("dedicated nonsymlink fixture-session directory")
        yield sessions
    except OSError:
        raise CheckFailure("protected fixture-state mount unavailable") from None
    finally:
        for fd in [sessions, marker, directory]:
            if fd is not None:
                os.close(fd)


def fixture():
    # Also defend callers other than run(): no DB fixture write before validation.
    with fixture_state():
        pass
    with admin() as db:
        identity = db.execute(
            "SELECT current_database() AS database,session_user AS login"
        ).fetchone()
        check(identity == {"database": "investalo_credentials_checks", "login": "investalo_migration"},
              "explicit fixture database and migration operator")
        check(bool(db.execute(
            "SELECT 1 FROM platform.schema_migrations WHERE version='007_passkey_action_proofs'"
        ).fetchone()), "reviewed immutable007 exists")
        tenant, user, account, connected, connection = (uuid4() for _ in range(5))
        subject = "synthetic-bff-browser-" + uuid4().hex
        db.execute("INSERT INTO platform.users(id,oidc_issuer,oidc_subject) VALUES(%s,%s,%s)",
                   (user, ISSUER, subject))
        db.execute("INSERT INTO platform.tenants(id,name) VALUES(%s,'Synthetic BFF browser check')", (tenant,))
        db.execute("INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES(%s,%s,'owner')",
                   (tenant, user))
        db.execute(
            "INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency) VALUES"
            "(%s,%s,'Synthetic unconnected browser account','bitget','read_only','USDT'),"
            "(%s,%s,'Synthetic connected browser account','bitget','read_only','USDT')",
            (tenant, account, tenant, connected),
        )
        encode = lambda length: base64.b64encode(b"\x01" * length).decode()
        # Structural fixture bytes only. No actual AEAD material or broker key.
        envelope = {
            "schema_version": "credential-envelope/1", "kek_id": "synthetic-browser-check",
            "payload_nonce": encode(12), "wrap_nonce": encode(12),
            "wrapped_dek": encode(48), "ciphertext": encode(32),
        }
        db.execute(
            "INSERT INTO platform.credential_connections(tenant_id,user_id,platform_account_id,"
            "connection_id,broker_uid,credential_revision,storage_version,status,envelope) "
            "VALUES(%s,%s,%s,%s,%s,1,1,'active',%s)",
            (tenant, user, connected, connection, str(10**19 + uuid4().int % (10**19)), Jsonb(envelope)),
        )
        token, user_handle = secrets.token_bytes(32), secrets.token_bytes(32)
        # Explicitly synthetic test approval, analogous to isolated registry tests.
        # This does not attest that a human email was received or confirmed.
        ticket = db.execute(
            "SELECT platform.passkey_issue_enrollment(%s,%s,%s,%s,%s,%s,%s,%s) AS id",
            (tenant, user, RP, hashlib.sha256(token).digest(), user_handle, 0,
             datetime.now(timezone.utc) + timedelta(seconds=600), uuid4()),
        ).fetchone()["id"]
    return {
        "tenant": tenant, "user": user, "account": account, "connected": connected,
        "connection": connection, "subject": subject, "ticket": ticket,
        "token": b64(token), "user_handle": b64(user_handle), "auth_time": int(time()) - 600,
    }


def session(f):
    handle, csrf = b64(secrets.token_bytes(32)), b64(secrets.token_bytes(32))
    value = {
        "issuer": ISSUER, "subject": f["subject"], "oidcAuthTime": f["auth_time"],
        "tenantId": str(f["tenant"]), "authEpoch": 0, "expiresAt": int(time()) + 1800,
        "displayName": "Synthetic BFF browser", "tenantName": "Synthetic BFF browser check", "csrf": csrf,
    }
    secret = Path(os.environ["PASSKEY_CHECK_SESSION_SECRET_FILE"]).read_text().strip()
    key = hashlib.sha256(("investalo-session-v1:" + secret).encode()).digest()
    iv = secrets.token_bytes(12)
    encrypted = AESGCM(key).encrypt(iv, wire(value), None)
    target = hashlib.sha256(handle.encode()).hexdigest() + ".json.enc"
    with fixture_state() as directory:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640, dir_fd=directory)
        with os.fdopen(fd, "w") as output:
            # Only this newly reserved file is affected, never an existing path.
            os.fchmod(output.fileno(), 0o640)
            info = os.fstat(output.fileno())
            if info.st_uid != 10003 or info.st_gid != 10010 or info.st_nlink != 1:
                raise CheckFailure("new protected fixture-session file")
            output.write(base64.b64encode(iv + encrypted[-16:] + encrypted[:-16]).decode())
    return {"handle": handle, "value": value}


def key():
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_numbers()
    cose = cbor({1: 2, 3: -7, -1: 1, -2: public.x.to_bytes(32, "big"), -3: public.y.to_bytes(32, "big")})
    return {"private": private, "cose": cose, "credential": secrets.token_bytes(32)}


def registration(k, options):
    client = wire({"type": "webauthn.create", "challenge": options["challenge"],
                   "origin": ORIGIN, "crossOrigin": False})
    authenticator = (
        hashlib.sha256(RP.encode()).digest() + b"\x45" + b"\x00" * 4 + b"\x00" * 16
        + struct.pack(">H", len(k["credential"])) + k["credential"] + k["cose"]
    )
    attestation = cbor({"fmt": "none", "authData": authenticator, "attStmt": {}})
    return {
        "id": b64(k["credential"]), "rawId": b64(k["credential"]), "type": "public-key",
        "clientExtensionResults": {"credProps": {"rk": True}},
        "response": {"clientDataJSON": b64(client), "attestationObject": b64(attestation)},
    }


def assertion(k, f, options, counter, *, wrong_key=False):
    client = wire({"type": "webauthn.get", "challenge": options["challenge"],
                   "origin": ORIGIN, "crossOrigin": False})
    data = hashlib.sha256(RP.encode()).digest() + b"\x05" + struct.pack(">I", counter)
    signer = ec.generate_private_key(ec.SECP256R1()) if wrong_key else k["private"]
    signature = signer.sign(data + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
    return {
        "id": b64(k["credential"]), "rawId": b64(k["credential"]), "type": "public-key",
        "clientExtensionResults": {}, "response": {
            "clientDataJSON": b64(client), "authenticatorData": b64(data),
            "signature": b64(signature), "userHandle": f["user_handle"],
        },
    }


def ticket_state(f):
    with admin() as db:
        return db.execute(
            "SELECT state,claim_id FROM platform.passkey_enrollment_tickets WHERE ticket_id=%s",
            (f["ticket"],),
        ).fetchone()


def proof_state(attempt):
    with admin() as db:
        return db.execute(
            "SELECT state,oidc_auth_time,checked_at FROM platform.passkey_action_proofs WHERE proof_id=%s",
            (attempt["attempt_id"],),
        ).fetchone()


def credential_state(f):
    with admin() as db:
        return db.execute(
            "SELECT storage_version,sign_count,credential_id,public_key,status "
            "FROM platform.passkey_credentials WHERE tenant_id=%s AND user_id=%s AND rp_id=%s",
            (f["tenant"], f["user"], RP),
        ).fetchone()


def start_proof(s, account, action):
    status, value = json_post(PREFIX + "/start", s,
                              {"platform_account_id": str(account), "action": action})
    check(status == 200, "proof start")
    check(set(value) == {"attempt_id", "options", "confirmation_token", "preview"},
          "start public projection")
    check(set(value["preview"]) == {"target", "accountName", "expiresAt", "execution_enabled"}
          and value["preview"]["execution_enabled"] is False and value["preview"]["target"]["action"] == action
          and value["preview"]["target"]["platform_account_id"] == str(account), "selected immutable preview")
    check(value["options"]["rpId"] == RP and value["options"]["userVerification"] == "required",
          "exact RP and required user verification")
    check(len(unb64(value["confirmation_token"])) == 32 and len(unb64(value["options"]["challenge"])) == 32,
          "bounded random preview and challenge")
    return value


def finish_payload(start, credential):
    return {"attempt_id": start["attempt_id"], "credential": credential,
            "confirmation_token": start["confirmation_token"]}


def finish_proof(s, f, k, start, counter):
    status, value = json_post(PREFIX + "/finish", s, finish_payload(start, assertion(k, f, start["options"], counter)))
    check(status == 200, "signed fresh proof finish")
    check(set(value) == {"grant_id", "grant"} and set(value["grant"]) == {
        "target", "accountName", "checkedAt", "expiresAt", "confirmationToken", "execution_enabled"
    }, "finish safe public grant")
    check(value["grant"]["target"] == start["preview"]["target"] and
          value["grant"]["confirmationToken"] == start["confirmation_token"] and
          value["grant"]["execution_enabled"] is False, "grant matches own preview without execution")
    return value


def confirm_payload(start, finished, *, token=None):
    return {"grant_id": finished["grant_id"],
            "confirmation_token": token if token is not None else start["confirmation_token"]}


def check_actions(f, s, other_session, k):
    first = start_proof(s, f["account"], "register")
    status, _ = json_post(PREFIX + "/finish", other_session,
                          finish_payload(first, assertion(k, f, first["options"], 1)))
    check(status == 400 and proof_state(first)["state"] == "prepared",
          "another session cannot burn a prepared action proof")
    wrong_csrf = {"X-CSRF-Token": b64(secrets.token_bytes(32))}
    status, _ = json_post(PREFIX + "/finish", s,
                          finish_payload(first, assertion(k, f, first["options"], 1)), headers=wrong_csrf)
    check(status == 403 and proof_state(first)["state"] == "prepared",
          "wrong CSRF cannot consume proof claim")
    payload = finish_payload(first, assertion(k, f, first["options"], 1))
    with ThreadPoolExecutor(max_workers=2) as threads:
        results = list(threads.map(lambda _: json_post(PREFIX + "/finish", s, payload), range(2)))
    check(sorted(status for status, _ in results) == [200, 400], "concurrent finish succeeds exactly once")
    finished = next(value for status, value in results if status == 200)
    check(set(finished) == {"grant_id", "grant"} and finished["grant"]["execution_enabled"] is False,
          "concurrent finish has verification-only receipt")
    state = proof_state(first)
    check(state["state"] == "granted" and state["oidc_auth_time"] == f["auth_time"]
          and state["checked_at"] > f["auth_time"], "durable grant retains original OIDC time")
    saved = credential_state(f)
    check((saved["storage_version"], saved["sign_count"]) == (2, 1),
          "verified counter CAS occurs once")
    status, _ = json_post(PREFIX + "/confirm", s,
                          confirm_payload(first, finished, token=b64(secrets.token_bytes(32))))
    check(status == 400 and proof_state(first)["state"] == "granted",
          "wrong preview cannot consume own grant")
    status, projection = json_post(PREFIX + "/grant", s, confirm_payload(first, finished))
    check(status == 200 and projection == finished["grant"], "current own grant can be read")
    with ThreadPoolExecutor(max_workers=2) as threads:
        results = list(threads.map(
            lambda _: json_post(PREFIX + "/confirm", s, confirm_payload(first, finished)), range(2)
        ))
    check(sorted(status for status, _ in results) == [200, 400], "concurrent confirmation succeeds once")
    receipt = next(value for status, value in results if status == 200)
    check(receipt == {"status": "verified", "execution_enabled": False, "action": "register",
                      "platform_account_id": str(f["account"])}, "exact non-execution confirmation")
    check(proof_state(first)["state"] == "confirmed", "confirmed state is committed")
    check(json_post(PREFIX + "/grant", s, confirm_payload(first, finished))[0] == 400,
          "confirmed grant cannot be read or republished")
    check(json_post(PREFIX + "/finish", s, payload)[0] == 400, "signed assertion replay is rejected")
    with admin() as db:
        events = db.execute(
            "SELECT event FROM platform.passkey_action_audit WHERE proof_id=%s ORDER BY occurred_at",
            (first["attempt_id"],),
        ).fetchall()
    check([row["event"] for row in events] == ["prepared", "claimed", "granted", "confirmed"],
          "single durable lifecycle audit")

    failed = start_proof(s, f["account"], "register")
    status, _ = json_post(PREFIX + "/finish", s,
                          finish_payload(failed, assertion(k, f, failed["options"], 2, wrong_key=True)))
    check(status == 400 and proof_state(failed)["state"] == "claimed",
          "crypto failure leaves committed claim consumed")
    check((credential_state(f)["storage_version"], credential_state(f)["sign_count"]) == (2, 1),
          "crypto failure never advances counter")
    status, _ = json_post(PREFIX + "/finish", s,
                          finish_payload(failed, assertion(k, f, failed["options"], 2)))
    check(status == 400, "failed crypto claim cannot be retried with a good signature")

    stale = start_proof(s, f["account"], "register")
    latest = start_proof(s, f["account"], "register")
    granted = finish_proof(s, f, k, latest, 2)
    status, _ = json_post(PREFIX + "/confirm", s,
                          confirm_payload(latest, granted, token=stale["confirmation_token"]))
    check(status == 400 and proof_state(latest)["state"] == "granted",
          "older tab cannot burn newer preview")
    status, _ = json_post(PREFIX + "/finish", s,
                          finish_payload(stale, assertion(k, f, stale["options"], 3)))
    check(status == 400 and proof_state(stale)["state"] == "prepared",
          "stale factor version cannot consume or authorize a new claim")
    check(json_post(PREFIX + "/confirm", s, confirm_payload(latest, granted))[0] == 200,
          "latest own preview remains confirmable")

    counter = 3
    for action in ["replace", "revoke"]:
        start = start_proof(s, f["connected"], action)
        finished = finish_proof(s, f, k, start, counter)
        status, receipt = json_post(PREFIX + "/confirm", s, confirm_payload(start, finished))
        check(status == 200 and receipt == {
            "status": "verified", "execution_enabled": False, "action": action,
            "platform_account_id": str(f["connected"]),
        }, "existing connection proof remains verification-only")
        counter += 1

    with admin() as db:
        actual = db.execute(
            "SELECT status,credential_revision,storage_version FROM platform.credential_connections "
            "WHERE tenant_id=%s AND connection_id=%s", (f["tenant"], f["connection"]),
        ).fetchone()
        registered = db.execute(
            "SELECT count(*) AS n FROM platform.credential_connections WHERE tenant_id=%s "
            "AND platform_account_id=%s", (f["tenant"], f["account"]),
        ).fetchone()["n"]
    check(actual == {"status": "active", "credential_revision": 1, "storage_version": 1} and registered == 0,
          "no credential create replace revoke or broker execution")
    check(json_post("/api/credentials/step-up", s,
                    {"platform_account_id": str(f["account"]), "action": "register"})[0] == 503,
          "legacy credential start remains gated after successful proof")
    check(json_post("/api/credentials/confirm", s,
                    {"confirmed": True, "confirmation_token": latest["confirmation_token"]})[0] == 503,
          "legacy credential confirmation remains gated after successful proof")


def run():
    global STAGE
    if os.environ.get("PASSKEY_CHECK_ORIGIN") != ORIGIN or os.environ.get("PASSKEY_CHECK_ISSUER") != ISSUER:
        raise CheckFailure("fixed synthetic test origins")
    with fixture_state():
        pass
    check(True, "protected synthetic fixture-state validated before writes")
    deadline = monotonic() + 60
    while True:
        try:
            if request("/api/health")[0] == 200:
                break
        except (URLError, TimeoutError, OSError):
            pass
        if monotonic() >= deadline:
            raise CheckFailure("isolated HTTPS BFF becomes ready")
        sleep(0.5)
    STAGE = "unique PostgreSQL fixture"
    f = fixture()
    try:
        STAGE = "protected synthetic sessions"
        s, other_session, k = session(f), session(f), key()
        STAGE = "complete registration HTTP flow"
        status, page, _ = request("/security/passkeys", s)
        check(status == 200 and "Einmaliges Registrierungsticket" in page, "own enrollment page and fixture session")
        status, page, _ = request("/security/passkeys/verify", s)
        check(status == 200 and "Passkey-Bestätigung prüfen" in page and "proof-account" not in page,
              "proof page requires a registered factor")
        for overrides, name in [
            ({"Origin": "https://other.invalid"}, "cross-origin enrollment rejected"),
            ({"X-CSRF-Token": b64(secrets.token_bytes(32))}, "wrong enrollment CSRF rejected"),
            ({"Sec-Fetch-Site": "cross-site"}, "cross-site enrollment rejected"),
        ]:
            status, _ = json_post("/api/passkeys/enrollment/start", s, {"token": f["token"]}, headers=overrides)
            check(status == 400 and ticket_state(f)["state"] == "issued", name)
        duplicate = b'{"token":"' + f["token"].encode() + b'","token":"' + f["token"].encode() + b'"}'
        status, _ = json_post("/api/passkeys/enrollment/start", s, None, raw=duplicate)
        check(status == 400 and ticket_state(f)["state"] == "issued", "duplicate ticket input cannot claim")
        status, start = json_post("/api/passkeys/enrollment/start", s, {"token": f["token"]})
        check(status == 200 and set(start) == {"attempt_id", "options"}, "full enrollment start response")
        check(start["options"]["user"]["id"] == f["user_handle"] and start["options"]["rp"]["id"] == RP,
              "issued opaque handle and exact registration RP")
        check(ticket_state(f)["state"] == "claimed", "ticket claim committed before client crypto")
        check(json_post("/api/passkeys/enrollment/start", s, {"token": f["token"]})[0] == 400,
              "ticket replay rejected")
        credential = registration(k, start["options"])
        payload = {"attempt_id": start["attempt_id"], "credential": credential}
        status, _ = json_post("/api/passkeys/enrollment/finish", other_session, payload)
        check(status == 400 and ticket_state(f)["state"] == "claimed",
              "another session cannot burn the enrollment attempt")
        status, receipt = json_post("/api/passkeys/enrollment/finish", s, payload)
        check(status == 200 and receipt == {"registered": True}, "positive complete actual BFF enrollment")
        check(ticket_state(f)["state"] == "finished", "registration committed in PostgreSQL")
        saved = credential_state(f)
        check(saved["credential_id"] == k["credential"] and saved["public_key"] == k["cose"]
              and (saved["storage_version"], saved["sign_count"], saved["status"]) == (1, 0, "active"),
              "actual verified P256 candidate persisted")
        check(json_post("/api/passkeys/enrollment/finish", s, payload)[0] == 400,
              "enrollment attempt replay rejected")
        status, page, _ = request("/security/passkeys", s)
        check(status == 200 and "Dein Passkey ist registriert." in page, "updated status from authenticated PG context")
        status, page, _ = request("/security/passkeys/verify", s)
        check(status == 200 and "Passkey-Bestätigung prüfen" in page and "proof-account" in page
              and "Synthetic unconnected browser account" in page and "Synthetic connected browser account" in page,
              "registered proof page displays only authenticated own account choices")
        for path, payload in [
            (PREFIX + "/start", {"platform_account_id": str(uuid4()), "action": "register"}),
            (PREFIX + "/start", {"platform_account_id": str(f["account"]), "action": "register", "api_key": "synthetic"}),
        ]:
            check(json_post(path, s, payload)[0] == 400, "unauthorized target or broker-key field rejected")
        status, _ = json_post(PREFIX + "/start", None,
                              {"platform_account_id": str(f["account"]), "action": "register"})
        check(status == 401, "unauthenticated proof has no authority")
        for overrides in [{"Origin": "https://other.invalid"},
                          {"X-CSRF-Token": b64(secrets.token_bytes(32))},
                          {"Sec-Fetch-Site": "cross-site"}]:
            check(json_post(PREFIX + "/start", s,
                            {"platform_account_id": str(f["account"]), "action": "register"}, headers=overrides)[0] == 403,
                  "browser proof Origin CSRF and fetch metadata gate")
        STAGE = "proof-only HTTP and PostgreSQL flow"
        check_actions(f, s, other_session, k)
    finally:
        # Close only the actor created in this unique synthetic fixture. Immutable
        # registry/proof/audit rows remain; never delete/reset the fixture database.
        with admin() as db:
            db.execute("UPDATE platform.users SET active=false WHERE id=%s", (f["user"],))
    print(f"PASS: {CHECKS} isolated HTTPS/BFF/PG checks; synthetic keys and approval only; no hardware or email attestation.")


def run_disabled():
    """Optional second internal Cockpit verifies the same image with flag0."""
    global STAGE
    if os.environ.get("PASSKEY_CHECK_ORIGIN") != ORIGIN or os.environ.get("PASSKEY_CHECK_ISSUER") != ISSUER:
        raise CheckFailure("fixed synthetic test origins")
    with fixture_state():
        pass
    check(True, "protected synthetic fixture-state validated before writes")
    deadline = monotonic() + 60
    while True:
        try:
            if request("/api/health", origin=DISABLED_ORIGIN)[0] == 200:
                break
        except (URLError, TimeoutError, OSError):
            pass
        if monotonic() >= deadline:
            raise CheckFailure("disabled isolated HTTPS BFF becomes ready")
        sleep(0.5)
    STAGE = "disabled preview fixture"
    f = fixture()
    try:
        s = session(f)
        status, page, _ = request("/security/passkeys/verify", s, origin=DISABLED_ORIGIN)
        check(status == 200 and "noch nicht freigeschaltet" in page and "proof-account" not in page,
              "disabled proof page has no begin controls")
        token = b64(secrets.token_bytes(32))
        for operation, payload in [
            ("start", {"platform_account_id": str(f["account"]), "action": "register"}),
            ("finish", {"attempt_id": str(uuid4()), "credential": {}, "confirmation_token": token}),
            ("grant", {"grant_id": str(uuid4()), "confirmation_token": token}),
            ("confirm", {"grant_id": str(uuid4()), "confirmation_token": token}),
        ]:
            status, _ = json_post(PREFIX + "/" + operation, s, payload, origin=DISABLED_ORIGIN)
            check(status == 503, "disabled proof route stays closed")
        with admin() as db:
            proof_count = db.execute(
                "SELECT count(*) AS n FROM platform.passkey_action_proofs WHERE tenant_id=%s AND user_id=%s",
                (f["tenant"], f["user"]),
            ).fetchone()["n"]
            key_count = db.execute(
                "SELECT count(*) AS n FROM platform.passkey_credentials WHERE tenant_id=%s AND user_id=%s",
                (f["tenant"], f["user"]),
            ).fetchone()["n"]
        check(proof_count == 0 and key_count == 0 and ticket_state(f)["state"] == "issued",
              "disabled routes cause no proof factor or ticket state changes")
    finally:
        with admin() as db:
            db.execute("UPDATE platform.users SET active=false WHERE id=%s", (f["user"],))
    print(f"PASS: {CHECKS} isolated disabled-preview HTTPS/BFF/PG checks; no proof or factor mutation.")


def main():
    try:
        if sys.argv[1:] == ["--disabled-only"]:
            run_disabled()
        elif not sys.argv[1:]:
            run()
        else:
            raise CheckFailure("supported check mode")
        return 0
    except CheckFailure as failure:
        print("FAIL: " + str(failure), file=sys.stderr)
    except Exception:
        # Connection strings, cookies, tickets and WebAuthn buffers are never logged.
        print("FAIL: " + STAGE + " unavailable; inspect protected fixture state.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
