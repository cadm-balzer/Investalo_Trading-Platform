"""Explicit isolated synthetic Demo executor. Never accepts actual broker keys."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import ssl
import sys
import time
from uuid import UUID

from investalo_bitget.futures_demo import DemoBinding
from .client import ROLE_SQL, CONTEXT_SQL, _row
from .development_runtime import (
    OWNER_UID, DATABASE, LOGIN_ROLE, PASSWORD_PATH, PG_CA_PATH, OIDC_ISSUER, ORIGIN,
    _checked_file, _read, _object, _invalid_constant, _environment, _connect_factory,
)
from .keyfiles import DevelopmentKeyFileProvider, KeyFile
from .models import StoreContext, _PrivateImmutable
from .onboarding import _request
from .demo_trading_passkey_assertion import DemoTradingPasskeyRequestVerifier
from .demo_trading_passkey_onboarding import DemoTradingPasskeyOnboarding
from .demo_trading_secret import DemoTradingSecretSpec
from .private_asgi import create_private_asgi_server
from .private_http import DemoTradingCredentialHTTPApplication
from .request_assertion import OnboardingRejected

ROOT = "/run/demo-trading-executor"
SCHEMA = "investalo-demo-trading-credential-acceptance/1"
KEY_VERSION = "synthetic-demo-trading-acceptance"
API_KEY = "synthetic-demo-trading-acceptance-api"
SECRET = "synthetic-demo-trading-acceptance-secret-ß".encode()
PASSPHRASE = "synthetic-demo-trading-acceptance-passphrase"
EGRESS_IP = "192.0.2.18"
FIELDS = frozenset(("schema", "tenant_id", "user_id", "account_id", "uncertain_account_id",
                    "broker_uid", "uncertain_broker_uid", "signing_sha256", "kek_sha256", "client_certificate_sha256",
                    "provisioning_digest"))
CAPABILITIES = """SELECT current_database(),
pg_catalog.has_function_privilege(session_user,
 pg_catalog.to_regprocedure('platform.demo_trading_credential_consume_passkey_authorization(jsonb)'),'EXECUTE'),
pg_catalog.has_function_privilege(session_user,
 pg_catalog.to_regprocedure('platform.demo_trading_credential_lock_passkey_execution(jsonb)'),'EXECUTE'),
pg_catalog.has_function_privilege(session_user,
 pg_catalog.to_regprocedure('platform.demo_trading_credential_finish_passkey_authorization(jsonb,text)'),'EXECUTE')"""
ERROR = "Synthetic Demo acceptance runtime rejected."


class DemoTradingAcceptanceRejected(ValueError):
    def __init__(self):
        super().__init__("demo_trading_acceptance_runtime_rejected")


class DemoTradingAcceptanceConfig(_PrivateImmutable):
    __slots__ = tuple(sorted(FIELDS - {"schema"}))

    def __init__(self, value):
        try:
            if type(value) is not dict or set(value) != FIELDS or value["schema"] != SCHEMA:
                raise ValueError()
            for name in ("tenant_id", "user_id", "account_id", "uncertain_account_id"):
                if type(value[name]) is not str or str(UUID(value[name])) != value[name]:
                    raise ValueError()
                object.__setattr__(self, name, UUID(value[name]))
            if self.account_id == self.uncertain_account_id:
                raise ValueError()
            import re
            for name in ("broker_uid", "uncertain_broker_uid"):
                if type(value[name]) is not str or not re.fullmatch(r"[1-9][0-9]{0,19}", value[name]):
                    raise ValueError()
                object.__setattr__(self, name, value[name])
            if self.broker_uid == self.uncertain_broker_uid:
                raise ValueError()
            for name in ("signing_sha256", "kek_sha256", "client_certificate_sha256", "provisioning_digest"):
                if type(value[name]) is not str or not re.fullmatch("[a-f0-9]{64}", value[name]):
                    raise ValueError()
                object.__setattr__(self, name, value[name])
            if hmac.compare_digest(self.signing_sha256, self.kek_sha256):
                raise ValueError()
        except Exception:
            raise DemoTradingAcceptanceRejected() from None


def synthetic_request(config, action, body):
    """Fixed canaries and accounts checked before any durable consume."""
    try:
        if type(config) is not DemoTradingAcceptanceConfig or action not in ("register", "revoke"):
            raise ValueError()
        account, _, _, _, credentials, _ = _request(action, body)
        if account not in (config.account_id, config.uncertain_account_id):
            raise ValueError()
        if action == "register" and (
                credentials._api_key != API_KEY or not hmac.compare_digest(credentials._secret_key, SECRET)
                or credentials._passphrase != PASSPHRASE):
            raise ValueError()
    except Exception:
        raise OnboardingRejected("invalid_request") from None


def create_application(config):
    try:
        if type(config) is not DemoTradingAcceptanceConfig:
            raise ValueError()
        _environment()
        signing = _read(ROOT + "/signing-key", limit=32, exact=32)
        if hashlib.sha256(signing).hexdigest() != config.signing_sha256:
            raise ValueError()
        ring = DevelopmentKeyFileProvider(ROOT + "/keks",
            (KeyFile(KEY_VERSION, "active.key", config.kek_sha256),),
            active_version=KEY_VERSION, development_mode=True, owner_uid=OWNER_UID).load()
        password = _read(PASSWORD_PATH, limit=128).decode("ascii")
        import re
        if not re.fullmatch("[A-Za-z0-9_-]{32,128}", password):
            raise ValueError()
        _read(PG_CA_PATH, limit=32768, owner=None, mode=0o444)
        connect = _connect_factory(password)
        context = StoreContext(tenant_id=config.tenant_id, user_id=config.user_id, expected_login_role=LOGIN_ROLE)
        with connect() as db:
            with db.cursor() as cursor:
                cursor.execute(ROLE_SQL)
                role = _row(cursor, 8)
                if role[:2] != (LOGIN_ROLE, LOGIN_ROLE) or any(role[2:7]) or role[7] is not True:
                    raise ValueError()
                cursor.execute(CONTEXT_SQL)
                if _row(cursor, 2) != (config.tenant_id, config.user_id):
                    raise ValueError()
                cursor.execute(CAPABILITIES)
                if _row(cursor, 4) != (DATABASE, True, True, True):
                    raise ValueError()
        verifier = DemoTradingPasskeyRequestVerifier(key=signing, oidc_issuer=OIDC_ISSUER, origin=ORIGIN,
                                             clock=lambda: int(time.time()))

        def provision(credentials, *, owner, account_id, connection_id, expires_ms):
            if expires_ms <= time.time_ns() // 1_000_000:
                raise OnboardingRejected("invalid_request")
            # Declared synthetic UID/parent/IP/provenance, no native HTTP.
            uid = config.uncertain_broker_uid if account_id == config.uncertain_account_id else config.broker_uid
            return DemoTradingSecretSpec(binding=DemoBinding(owner, account_id, connection_id, uid),
                parent_uid="0", egress_ip=EGRESS_IP, authorities=["coow","cpow","stow"], provisioning_digest=config.provisioning_digest,
                credential_revision=1)

        def execute(request_context, action, token, body):
            synthetic_request(config, action, body)
            executor = DemoTradingPasskeyOnboarding(context, connect=connect, verifier=verifier,
                request_context=request_context, provision=provision, load_keyring=lambda: ring,
                expected_egress_ip=EGRESS_IP)
            result = executor.apply(action, token=token, body=body)
            if action == "register" and _request(action, body)[0] == config.uncertain_account_id:
                # Deliberate isolated post-commit acknowledgement loss. The
                # completed019 row must survive and019 must never be rearmed.
                raise OnboardingRejected("unavailable")
            return result

        return DemoTradingCredentialHTTPApplication(context, execute, enabled=True)
    except Exception:
        raise DemoTradingAcceptanceRejected() from None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    server = None
    try:
        if argv != ["--synthetic-demo-trading"] or os.geteuid() != OWNER_UID:
            raise ValueError()
        config = DemoTradingAcceptanceConfig(json.loads(_read(ROOT + "/config", limit=4096),
            object_pairs_hook=_object, parse_constant=_invalid_constant))
        application = create_application(config)
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        tls.verify_mode = ssl.CERT_REQUIRED
        tls.load_verify_locations(cadata=_read(ROOT + "/client-ca", limit=32768).decode("ascii"))
        with _checked_file(ROOT + "/tls-certificate", limit=32768) as (certificate, _):
            with _checked_file(ROOT + "/tls-private-key", limit=32768) as (key, _):
                tls.load_cert_chain(f"/proc/self/fd/{certificate}", f"/proc/self/fd/{key}")
        server = create_private_asgi_server(("0.0.0.0", 9443), tls_context=tls,
            client_certificate_sha256=frozenset((config.client_certificate_sha256,)),
            application=application, timeout_seconds=20, max_workers=4)
        server.serve_forever()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print(ERROR, file=sys.stderr)
        return 1
    finally:
        if server is not None:
            server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
