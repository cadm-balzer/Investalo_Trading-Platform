"""Operative Demo onboarding: one fixed native identity GET, then own019/018.

Trusted private setup binds one actor/account/Bitget UID and attests Demo creation.
Broker triples arrive only over the existing Passkey-authorized mTLS boundary.
"""
from contextlib import contextmanager
import hashlib
import json
import os
import re
import ssl
import sys
import threading
import tempfile
import time
from uuid import UUID

import psycopg
from investalo_credentials import KEKRing
from investalo_bitget import OwnerContext, parse, BitgetRejected
from investalo_bitget.models import AccountBinding
from investalo_bitget.demo_trading_identity import ALLOWED, REQUIRED, trading_identity
from investalo_bitget.futures_demo import DemoBinding, digest
from investalo_bitget.futures_demo_read import (
    DemoReadCredential, SignedDemoReadRequest, HTTPSDemoReadTransport,
)
from .client import CONTEXT_SQL, ROLE_SQL, _row
from .development_runtime import _read, _checked_file, _object, _invalid_constant
from .models import StoreContext
from .onboarding import _request
from .demo_trading_passkey_assertion import DemoTradingPasskeyRequestVerifier
from .demo_trading_passkey_onboarding import DemoTradingPasskeyOnboarding
from .demo_trading_secret import DemoTradingSecretSpec, PURPOSE
from .private_asgi import create_private_asgi_server
from .private_http import DemoTradingCredentialHTTPApplication
from .request_assertion import OnboardingRejected

ROOT = "/run/demo-trading-executor"
SCHEMA = "investalo-demo-trading-runtime/1"
LOGIN = "investalo_demo_trading_credential"
KEY_VERSION = "demo-trading-v1"
DIAGNOSTIC_AUTHORITIES = ALLOWED | frozenset((
    "smow", "ttow", "wtow", "wwow", "chow", "p2p", "pllw", "pllr", "taxw",
    "trade", "readonly",
))
FIELDS = frozenset(("schema", "tenant_id", "user_id", "account_id", "broker_uid",
    "parent_uid", "egress_ip", "ip_binding", "origin", "oidc_issuer", "created_in_bitget_demo_mode",
    "signing_sha256", "kek_sha256", "client_certificate_sha256"))


def configuration(value):
    try:
        if (type(value) is not dict or set(value) != FIELDS or value["schema"] != SCHEMA
                or value["created_in_bitget_demo_mode"] is not True
                or value["ip_binding"] not in ("single_ip", "unavailable_in_demo")):
            raise ValueError()
        result = dict(value)
        for name in ("tenant_id", "user_id", "account_id"):
            if type(value[name]) is not str or str(UUID(value[name])) != value[name]:
                raise ValueError()
            result[name] = UUID(value[name])
        for name in ("signing_sha256", "kek_sha256", "client_certificate_sha256"):
            if type(value[name]) is not str or not re.fullmatch("[a-f0-9]{64}", value[name]):
                raise ValueError()
        if value["signing_sha256"] == value["kek_sha256"]:
            raise ValueError()
        # Fixed approved Cockpit; a manifest cannot redirect JWT audiences.
        if (value["origin"] != "https://cockpit.investalo.de"
                or value["oidc_issuer"] != "https://auth.cockpit.investalo.de"):
            raise ValueError()
        binding = AccountBinding(OwnerContext(result["tenant_id"], result["user_id"]),
            value["broker_uid"], value["parent_uid"], expected_egress_ip=value["egress_ip"])
        if (type(value["parent_uid"]) is not str or binding.expected_egress_ip is None
                or binding.expected_egress_ip != value["egress_ip"]):
            raise ValueError()
        return result
    except Exception:
        raise OnboardingRejected("unavailable") from None


class NativeDemoRegistration:
    """Single-process single-UID limiter; no retries or account/order requests."""
    def __init__(self, config, guard, *, transport=None, milliseconds=None, diagnostic=None, identity_diagnostic=None):
        self.config = configuration(config)
        self.guard = guard
        self.diagnostic = diagnostic
        self.identity_diagnostic = identity_diagnostic
        self.native_status = None
        self.native_code = None
        self.rights = {}
        self.transport = transport or HTTPSDemoReadTransport(timeout_seconds=3, diagnostic=self._native_result)
        self.milliseconds = milliseconds or (lambda: time.time_ns() // 1_000_000)
        self.lock = threading.Lock()
        self.last = None
        self.pid = os.getpid()

    def _native_result(self, status, code):
        self.native_status, self.native_code = status, code

    def _report(self, stage, outcome, error=None):
        if self.diagnostic is None:
            return
        reason = error.code.value if isinstance(error, BitgetRejected) else "rejected"
        try:
            self.diagnostic(dict(schema="investalo-demo-native-diagnostic/1",
                checked_ms=self.milliseconds(), stage=stage, outcome=outcome,
                reason=None if outcome == "accepted" else reason,
                http_status=self.native_status, provider_code=self.native_code, **self.rights))
        except Exception:
            pass

    def __call__(self, credentials, *, owner, account_id, connection_id, expires_ms):
        if os.getpid() != self.pid or not self.lock.acquire(blocking=False):
            raise OnboardingRejected("unavailable")
        stage = "scope"
        self.native_status = self.native_code = None
        self.rights = {}
        try:
            cfg = self.config
            start = self.milliseconds()
            if (owner != OwnerContext(cfg["tenant_id"], cfg["user_id"])
                    or account_id != cfg["account_id"] or type(connection_id) is not UUID
                    or type(expires_ms) is not int or not start < expires_ms <= start + 60_000
                    or self.last is not None and start - self.last < 1000):
                raise ValueError()
            self.guard()
            binding = DemoBinding(owner, account_id, connection_id, cfg["broker_uid"])
            declaration = digest(dict(schema=SCHEMA, purpose=PURPOSE,
                tenant_id=str(owner.tenant_id), user_id=str(owner.user_id),
                account_id=str(account_id), broker_uid=cfg["broker_uid"],
                parent_uid=cfg["parent_uid"], egress_ip=cfg["egress_ip"], ip_binding=cfg["ip_binding"],
                origin="operator_attested_bitget_demo_mode"))
            credential = DemoReadCredential(binding, credentials, cfg["parent_uid"],
                cfg["egress_ip"], declaration, 1, expires_ms)
            request = SignedDemoReadRequest(credential, timestamp_ms=start)
            self.last = start  # Failed sends consume this interval too.
            stage = "transport"
            response = self.transport(request)
            stage = "private_guard"
            self.guard()
            checked = self.milliseconds()
            stage = "identity"
            try:
                raw, _ = parse.envelope(response)
                values = raw.get("authorities") if type(raw) is dict else None
                if type(values) is list and len(values) <= 64:
                    known = {v for v in values if type(v) is str and v in DIAGNOSTIC_AUTHORITIES}
                    self.rights = dict(authorities=sorted(known),
                        missing_required=sorted(REQUIRED-known),
                        unexpected_count=sum(type(v) is not str or v not in ALLOWED for v in values),
                        uid_matches=raw.get("userId") == cfg["broker_uid"],
                        parent_matches=str(raw.get("parentId")) == cfg["parent_uid"])
            except Exception:
                pass  # Optional metadata cannot normalize or authorize native replies.
            identity = trading_identity(response)
            delta = identity.server_time - parse.EPOCH
            native_ms = delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000
            stage = "clock"
            if not start <= checked < expires_ms or checked - start > 5000 or not 0 <= checked - native_ms <= 5000:
                raise ValueError()
            if self.identity_diagnostic is not None:
                try:
                    self.identity_diagnostic(dict(schema="investalo-demo-native-identity/1",
                        tenant_id=str(owner.tenant_id), user_id=str(owner.user_id),
                        account_id=str(account_id), connection_id=str(connection_id),
                        broker_uid=identity.user_id, parent_uid=identity.parent_id,
                        authorities=list(identity.authorities), checked_ms=checked,
                        response_sha256=hashlib.sha256(response.body).hexdigest(),
                        registration_authorized=False))
                except Exception:
                    pass
            ip_bound = cfg["ip_binding"] == "single_ip"
            stage = "binding"
            AccountBinding(owner, cfg["broker_uid"], cfg["parent_uid"],
                expected_egress_ip=cfg["egress_ip"] if ip_bound else None).validate(
                    owner, identity, require_ip=ip_bound)
            if (ip_bound and identity.ip_whitelist != (cfg["egress_ip"],)
                    or not ip_bound and identity.ip_whitelist not in (None, ())):
                raise ValueError()
            evidence = digest(dict(schema="investalo-demo-trading-runtime-provisioning/1",
                binding=binding.record(), declaration_sha256=declaration,
                identity_response_sha256=hashlib.sha256(response.body).hexdigest(),
                native_time_ms=native_ms, checked_ms=checked, purpose=PURPOSE,
                authorities=list(identity.authorities), native_demo_creation_verified=False,
                native_ip_binding_verified=ip_bound, order_execution_enabled=False))
            stage = "secret_spec"
            result = DemoTradingSecretSpec(binding=binding, parent_uid=cfg["parent_uid"],
                egress_ip=cfg["egress_ip"], authorities=identity.authorities,
                provisioning_digest=evidence, credential_revision=1)
            self._report(stage, "accepted")
            return result
        except Exception as error:
            self._report(stage, "rejected", error)
            raise OnboardingRejected("unavailable") from None
        finally:
            self.lock.release()


def _write_private_record(value, filename):
    """Private tmpfs metadata, disposable and never an execution receipt."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir="/tmp", prefix=".demo-native-", delete=False) as f:
            temporary = f.name
            json.dump(value, f, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, filename)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)

def _write_native_diagnostic(value):
    _write_private_record(value, "/tmp/demo-trading-native-diagnostic.json")


def _write_native_identity(value):
    # Only successful strict native identity parsing reaches this private record.
    _write_private_record(value, "/tmp/demo-trading-native-identity.json")


def create_application():
    if os.geteuid() != 10003 or any(name.startswith("PG") for name in os.environ):
        raise OnboardingRejected("unavailable")
    raw = _read(ROOT + "/config", limit=4096)
    config = configuration(json.loads(raw, object_pairs_hook=_object, parse_constant=_invalid_constant))

    def guarded_file(name, expected=None, exact=None):
        value = _read(ROOT + "/" + name, limit=exact or 4096, exact=exact)
        if expected is not None and hashlib.sha256(value).hexdigest() != expected:
            raise OnboardingRejected("unavailable")
        return value

    def guard():
        if _read(ROOT + "/config", limit=4096) != raw:
            raise OnboardingRejected("unavailable")
        guarded_file("signing-key", config["signing_sha256"], 32)

    def keyring():
        guard()
        return KEKRing(((KEY_VERSION, guarded_file("kek", config["kek_sha256"], 32)),),
                       active_version=KEY_VERSION)

    guard()
    keyring()
    password = guarded_file("database-password").decode("ascii")
    if not re.fullmatch("[A-Za-z0-9_-]{64}", password):
        raise OnboardingRejected("unavailable")
    _read("/run/secrets/local_ca_cert", limit=32768, owner=None, mode=0o444)

    @contextmanager
    def connect():
        if any(name.startswith("PG") for name in os.environ):
            raise OnboardingRejected("unavailable")
        guard()
        with psycopg.connect(host="postgres", port=5432, dbname="investalo", user=LOGIN,
                password=password, sslmode="verify-full", sslrootcert="/run/secrets/local_ca_cert",
                connect_timeout=5, autocommit=False, gssencmode="disable",
                options="-c statement_timeout=10000 -c lock_timeout=5000") as db:
            yield db

    context = StoreContext(tenant_id=config["tenant_id"], user_id=config["user_id"], expected_login_role=LOGIN)
    with connect() as db, db.cursor() as cursor:
        cursor.execute(ROLE_SQL)
        role = _row(cursor, 8)
        if role[:2] != (LOGIN, LOGIN) or any(role[2:7]) or role[7] is not True:
            raise OnboardingRejected("unavailable")
        cursor.execute(CONTEXT_SQL)
        if _row(cursor, 2) != (config["tenant_id"], config["user_id"]):
            raise OnboardingRejected("unavailable")
    verifier = DemoTradingPasskeyRequestVerifier(
        key=guarded_file("signing-key", config["signing_sha256"], 32),
        oidc_issuer=config["oidc_issuer"], origin=config["origin"], clock=lambda: int(time.time()))
    provision = NativeDemoRegistration(json.loads(raw), guard, diagnostic=_write_native_diagnostic,
                                      identity_diagnostic=_write_native_identity)

    def execute(request_context, action, token, body):
        guard()
        if _request(action, body)[0] != config["account_id"]:
            raise OnboardingRejected("invalid_request")
        return DemoTradingPasskeyOnboarding(context, connect=connect, verifier=verifier,
            request_context=request_context, provision=provision, load_keyring=keyring,
            expected_egress_ip=config["egress_ip"]).apply(action, token=token, body=body)

    return config, DemoTradingCredentialHTTPApplication(context, execute, enabled=True)


def main(argv=None):
    server = None
    try:
        if (sys.argv[1:] if argv is None else argv) != ["--bitget-demo-trading"]:
            raise ValueError()
        config, application = create_application()
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        tls.verify_mode = ssl.CERT_REQUIRED
        tls.load_verify_locations(cadata=_read(ROOT + "/client-ca", limit=32768).decode("ascii"))
        with _checked_file(ROOT + "/tls-certificate", limit=32768) as (cert, _):
            with _checked_file(ROOT + "/tls-private-key", limit=32768) as (key, _):
                tls.load_cert_chain(f"/proc/self/fd/{cert}", f"/proc/self/fd/{key}")
        server = create_private_asgi_server(("0.0.0.0", 9443), tls_context=tls,
            client_certificate_sha256=frozenset((config["client_certificate_sha256"],)),
            application=application, timeout_seconds=20, max_workers=4)
        server.serve_forever()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("Demo trading runtime unavailable.", file=sys.stderr)
        return 1
    finally:
        if server is not None:
            server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
