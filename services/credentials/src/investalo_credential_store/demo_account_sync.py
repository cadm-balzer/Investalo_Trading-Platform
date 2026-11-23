"""Session-authorized Demo account GETs; keys remain inside the credential service."""
import hashlib
import hmac
import json
import os
import re
import threading
import time
from uuid import UUID

from investalo_bitget import OwnerContext, parse
from investalo_bitget.demo_trading_identity import trading_identity
from investalo_bitget.futures_demo import DemoBinding
from investalo_bitget.futures_demo_read import DemoReadCredential, SignedDemoReadRequest
from investalo_bitget.futures_demo_preview import public_demo_btc_get
from investalo_bitget.models import AccountBinding, ProductType
from investalo_credentials import dump_envelope

from .demo_store import DemoStoreAuthority
from .demo_trading_store import DemoTradingCredentialStore
from .passkey_request_assertion import PasskeyRequestContext, _decode, _json
from .request_assertion import OnboardingRejected

PATH = "/v1/bitget-demo-trading/account-read"
KIND = "investalo-demo-account-read/1"
SCHEMA = "investalo-demo-account/1"
CONTEXT = ("tenant_id", "user_id", "subject", "auth_epoch", "oidc_auth_time",
           "session_binding", "session_expires_at")
FIELDS = frozenset(CONTEXT + ("kind", "aud", "oidc_issuer", "origin",
    "iat", "exp", "jti", "htm", "htu", "body_sha256"))
TARGET_FIELDS = frozenset(("platform_account_id", "connection_id",
                          "credential_revision", "storage_version"))
MAX_VIEW_BYTES = 65536


def decimal(value, *, signed=False):
    number = parse.amount(value, signed=signed)
    return None if number is None else format(number, "f")


def public_amount(value, *, signed=False):
    if (type(value) is not str or len(value) > 96
            or re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value) is None):
        raise ValueError()
    return parse.amount(value, signed=signed)


def positions(response):
    rows, at = parse.envelope(response)
    if type(rows) is not list or len(rows) > 100:
        raise ValueError()
    result, seen = [], set()
    for row in rows:
        if type(row) is not dict:
            raise ValueError()
        symbol, side, mode = row.get("symbol"), row.get("holdSide"), row.get("marginMode")
        if (type(symbol) is not str or not re.fullmatch("[A-Z0-9]{2,30}", symbol)
                or row.get("marginCoin") != "USDT" or side not in ("long", "short")
                or mode not in ("isolated", "crossed") or (symbol, side) in seen):
            raise ValueError()
        seen.add((symbol, side))
        quantity = parse.amount(row.get("total"))
        if quantity is None:
            raise ValueError()
        if not quantity:
            continue
        liquidation = parse.amount(row.get("liquidationPrice"), signed=True)
        result.append(dict(symbol=symbol, side=side, quantity=format(quantity, "f"),
            entry_price=decimal(row.get("openPriceAvg")), mark_price=decimal(row.get("markPrice")),
            unrealized_pnl=decimal(row.get("unrealizedPL"), signed=True),
            leverage=decimal(row.get("leverage")), margin_mode=mode,
            liquidation_price=None if liquidation is None or liquidation <= 0 else format(liquidation, "f")))
    return sorted(result, key=lambda p: (p["symbol"], p["side"])), at


def validate_view(value):
    """Only explicit public data, never private native identity or response fields."""
    if (type(value) is not dict or set(value) != {
            "schema", "tenant_id", "account_id", "observed_at", "currency", "wallet", "positions"}
            or value["schema"] != SCHEMA or value["currency"] != "USDT"
            or type(value["positions"]) is not list or len(value["positions"]) > 100):
        raise ValueError()
    for key in ("tenant_id", "account_id"):
        if str(UUID(value[key])) != value[key]:
            raise ValueError()
    from datetime import datetime
    observed = datetime.fromisoformat(value["observed_at"])
    if observed.tzinfo is None:
        raise ValueError()
    keys = {"equity", "available", "locked", "unrealized_pnl", "isolated_margin", "crossed_margin"}
    if type(value["wallet"]) is not dict or set(value["wallet"]) != keys:
        raise ValueError()
    for amount in value["wallet"].values():
        if amount is not None:
            public_amount(amount, signed=True)
    seen = set()
    for p in value["positions"]:
        if (type(p) is not dict or set(p) != {"symbol", "side", "quantity", "entry_price",
                "mark_price", "unrealized_pnl", "leverage", "margin_mode", "liquidation_price"}
                or type(p["symbol"]) is not str or not re.fullmatch("[A-Z0-9]{2,30}", p["symbol"])
                or p["side"] not in ("long", "short") or p["margin_mode"] not in ("isolated", "crossed")
                or (p["symbol"], p["side"]) in seen):
            raise ValueError()
        seen.add((p["symbol"], p["side"]))
        if public_amount(p["quantity"]) <= 0:
            raise ValueError()
        for key in ("entry_price", "mark_price", "unrealized_pnl", "leverage", "liquidation_price"):
            if p[key] is not None:
                public_amount(p[key], signed=key == "unrealized_pnl")
    if len(json.dumps(value, separators=(",", ":")).encode()) > MAX_VIEW_BYTES:
        raise ValueError()
    return value


class DemoAccountReader:
    def __init__(self, config, context, *, connect, keyring, signing_key, native,
                 market_read=public_demo_btc_get):
        self.config, self.context = config, context
        self.connect, self.keyring, self.signing_key, self.native = connect, keyring, signing_key, native
        self.seen, self.seen_lock, self.pid = {}, threading.Lock(), os.getpid()
        self.market_read = market_read

    def _authorize(self, context, token, body):
        try:
            if type(context) is not PasskeyRequestContext:
                raise ValueError()
            a, b, c = token.split(".")
            if _json(_decode(a)) != {"alg": "HS256", "typ": "JWT"}:
                raise ValueError()
            mac = hmac.digest(self.signing_key, (a + "." + b).encode("ascii"), "sha256")
            if not hmac.compare_digest(mac, _decode(c)):
                raise ValueError()
            claims, now = _json(_decode(b)), int(time.time())
            if (set(claims) != FIELDS or claims["kind"] != KIND
                    or claims["aud"] != "investalo-demo-account-read"
                    or claims["oidc_issuer"] != self.config["oidc_issuer"]
                    or claims["origin"] != self.config["origin"]
                    or claims["htm"] != "POST" or claims["htu"] != PATH
                    or claims["body_sha256"] != hashlib.sha256(body).hexdigest()):
                raise ValueError()
            for key in CONTEXT:
                actual = getattr(context, key)
                actual = str(actual) if isinstance(actual, UUID) else actual
                if type(claims[key]) is not type(actual) or claims[key] != actual:
                    raise ValueError()
            if (any(type(claims[k]) is not int for k in ("iat", "exp"))
                    or not 0 <= now - claims["iat"] <= 15
                    or not now < claims["exp"] <= min(claims["iat"] + 15, context.session_expires_at)
                    or context.oidc_auth_time > now + 5 or os.getpid() != self.pid
                    or context.tenant_id != self.context.tenant_id or context.user_id != self.context.user_id):
                raise ValueError()
            jti = str(UUID(claims["jti"]))
            if jti != claims["jti"]:
                raise ValueError()
            target = _json(body)
            if (type(target) is not dict or set(target) not in (TARGET_FIELDS, TARGET_FIELDS | {"inspection"})
                    or "inspection" in target and target["inspection"] not in ("startup", "btc-test", "btc-market")
                    or str(UUID(target["platform_account_id"])) != target["platform_account_id"]
                    or target["platform_account_id"] != str(self.config["account_id"])
                    or str(UUID(target["connection_id"])) != target["connection_id"]
                    or type(target["credential_revision"]) is not int or target["credential_revision"] != 1
                    or type(target["storage_version"]) is not int or not 1 <= target["storage_version"] < 2**53):
                raise ValueError()
            with self.seen_lock:
                self.seen = {k: v for k, v in self.seen.items() if v > now}
                if jti in self.seen or len(self.seen) >= 256:
                    raise ValueError()
                self.seen[jti] = claims["exp"]
            return target, claims["exp"] * 1000
        except Exception:
            raise OnboardingRejected("access_denied") from None

    def __call__(self, request_context, token, body):
        target, expires = self._authorize(request_context, token, body)
        if not self.native.lock.acquire(blocking=False):
            raise OnboardingRejected("unavailable")
        phase, sent, grant_source = threading.local(), 0, {}
        phase.stage = "scope"
        started = time.time_ns() // 1_000_000
        def report(stage, error=None):
            diagnostic = getattr(self.native, "diagnostic", None)
            if target.get("inspection") not in ("startup", "btc-test", "btc-market") or not callable(diagnostic):
                return
            try:
                value = dict(schema=("investalo-demo-btc-test-diagnostic/1" if target.get("inspection") in ("btc-test", "btc-market")
                    else "investalo-demo-startup-diagnostic/1"), stage=stage, sent=sent,
                    elapsed_ms=time.time_ns() // 1_000_000 - started,
                    error_type=None if error is None else type(error).__name__,
                    http_status=getattr(self.native, "native_status", None),
                    provider_code=getattr(self.native, "native_code", None))
                if error is not None and hasattr(error, "_demo_pending_failure"):
                    value["pending_failure"] = error._demo_pending_failure
                if target.get("inspection") in ("btc-test", "btc-market") and "source" in grant_source:
                    value["grant_source"] = grant_source["source"]
                diagnostic(value)
            except Exception:
                pass
        try:
            cfg, native = self.config, self.native
            start = time.time_ns() // 1_000_000
            if native.last is not None and start - native.last < 1000:
                raise ValueError()
            native.last = start  # Failed identity reads consume the same registration quota.
            owner = OwnerContext(self.context.tenant_id, self.context.user_id)
            binding = DemoBinding(owner, self.context_account(), UUID(target["connection_id"]), cfg["broker_uid"])
            authority = DemoStoreAuthority(self.context, auth_epoch=request_context.auth_epoch,
                auth_time_ms=request_context.oidc_auth_time * 1000, expires_ms=expires)
            store = DemoTradingCredentialStore(authority, connect=self.connect)
            original = store.read_snapshot(binding, owner)
            if (original.storage_version != target["storage_version"]
                    or original.spec.parent_uid != cfg["parent_uid"]
                    or original.spec.egress_ip != cfg["egress_ip"]):
                raise ValueError()
            provider = store.provider(original.spec, expected_storage=original.storage_version,
                load_keyring=self.keyring)
            lease = provider(binding, owner)
            credential = DemoReadCredential(binding, lease.credentials, cfg["parent_uid"],
                cfg["egress_ip"], original.spec.provisioning_digest, 1, expires)

            def guard():
                native.guard()
                current = store.read_snapshot(binding, owner)
                if time.time_ns() // 1_000_000 - start > 5000:
                    phase.stage += ":cohort_timeout"
                    raise ValueError()
                if (current.spec.record() != original.spec.record()
                        or current.storage_version != original.storage_version
                        or dump_envelope(current.envelope) != dump_envelope(original.envelope)):
                    raise ValueError()

            last_get, start_lock = None, threading.Lock()
            def get(axis, cursor=None):
                nonlocal last_get, sent
                try:
                    phase.stage = axis + ":before_request"
                    # Only starts serialize; network and post-response guards
                    # overlap. Fresh actor/storage checks follow any pacing wait.
                    with start_lock:
                        if target.get("inspection") in ("startup", "btc-test", "btc-market") and last_get is not None:
                            time.sleep(max(0, .11 - (time.monotonic() - last_get)))
                        guard()
                        last_get = time.monotonic()
                        phase.stage = axis + ":native_request"
                        sent += 1
                        public = target.get("inspection") in ("btc-test", "btc-market") and axis in ("contracts", "ticker")
                        if public and cursor is not None:
                            raise ValueError()
                        request = None if public else SignedDemoReadRequest(credential,
                            timestamp_ms=time.time_ns() // 1_000_000, axis=axis, cursor=cursor)
                    response = self.market_read(axis) if public else native.transport(request)
                    phase.stage = axis + ":after_request"
                    guard()
                    _, at = parse.envelope(response)
                    delta = time.time_ns() // 1_000_000 - int(at.timestamp() * 1000)
                    if not 0 <= delta <= 5000:
                        raise ValueError()
                    phase.stage = axis + ":parse"
                    return response
                except Exception as error:
                    error._demo_startup_stage = phase.stage
                    raise

            identity = trading_identity(get("identity"))
            ip_bound = cfg["ip_binding"] == "single_ip"
            AccountBinding(owner, cfg["broker_uid"], cfg["parent_uid"],
                expected_egress_ip=cfg["egress_ip"] if ip_bound else None).validate(owner, identity, require_ip=ip_bound)
            if (identity.authorities != original.spec.authorities
                    or ip_bound and identity.ip_whitelist != (cfg["egress_ip"],)
                    or not ip_bound and identity.ip_whitelist not in (None, ())):
                raise ValueError()
            accounts, wallet_at = parse.futures_accounts(get("wallet"), ProductType.USDT)
            if len(accounts) != 1 or accounts[0].margin_coin != "USDT":
                raise ValueError()
            open_positions, positions_at = positions(get("positions"))
            guard()
            a = accounts[0]
            def text(amount):
                return None if amount is None else format(amount, "f")
            view = validate_view(dict(schema=SCHEMA, tenant_id=str(owner.tenant_id),
                account_id=str(binding.account_id), observed_at=min(wallet_at, positions_at).isoformat(),
                currency="USDT", wallet=dict(equity=text(a.account_equity), available=text(a.available),
                locked=text(a.locked), unrealized_pnl=text(a.unrealized_pnl),
                isolated_margin=text(a.isolated_margin), crossed_margin=text(a.crossed_margin)),
                positions=open_positions))
            if target.get("inspection") == "startup":
                from .demo_startup_check import inspect_startup
                result = inspect_startup(get, binding, owner, view, a)
                guard()
                report("completed")
                return result
            if target.get("inspection") in ("btc-test", "btc-market"):
                from .demo_btc_test_check import inspect_btc_test
                result = inspect_btc_test(get, binding, owner, view, a,
                    on_grant_source=lambda source: grant_source.update(source=source),
                    market_test=target.get("inspection") == "btc-market")
                guard()
                report("completed")
                return result
            return view
        except Exception as error:
            # Fixed stage/count/timing/status and allowlisted shape only. No context, body,
            # native reply, UID, API triple or provider message is persisted.
            report(getattr(error, "_demo_startup_stage", phase.stage), error)
            raise OnboardingRejected("unavailable") from None
        finally:
            if target.get("inspection") in ("startup", "btc-test", "btc-market"):
                self.native.last = time.time_ns() // 1_000_000
            self.native.lock.release()

    def context_account(self):
        return UUID(str(self.config["account_id"]))
