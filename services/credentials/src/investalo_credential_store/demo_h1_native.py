"""Current native profile/pending admission and once-only flat-account setup."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import hashlib
import json
import os
import ssl
import threading
import time
from urllib.request import Request, build_opener, HTTPSHandler, ProxyHandler

from investalo_bitget import parse
from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.futures_demo_account import DemoPacket, DemoReadPlan, _pages
from investalo_bitget.futures_demo_read import DemoReadCredential, SignedDemoReadRequest, HTTPSDemoReadTransport
from investalo_bitget.futures_demo_margin import margin_snapshot
from investalo_bitget.futures_demo_basket import BasketFundingIntent
from investalo_bitget.futures_demo_registry import _directory, _file
from investalo_bitget.signing import hmac_sha256_base64
from investalo_bitget.transport import _NoRedirect
from .demo_startup_check import startup_pending_response
from .demo_start_account import NativeStartAccountSource
from .demo_basket_orders import milliseconds

FAMILIES = ("live", "partially_filled", "normal_plan", "track_plan", "profit_loss")
D = Decimal


def profile_matches(raw):
    leverage = raw.get("isolatedLongLever")
    return (raw.get("marginCoin") == "USDT" and raw.get("marginMode") == "isolated"
        and raw.get("posMode") == "one_way_mode" and raw.get("assetMode") == "single"
        and (type(leverage) is int and leverage == 2 or type(leverage) is str and leverage == "2"))


class DemoH1NativeGuard:
    def __init__(self, provider, policy, guard, *, transport=None, milliseconds=lambda: time.time_ns()//1_000_000):
        self.provider, self.policy, self.guard = provider, policy, guard
        self.transport, self.now = transport or HTTPSDemoReadTransport(3), milliseconds
        self.pacing, self.last = threading.Lock(), None

    def get(self, axis, cursor=None):
        with self.pacing:
            if self.last is not None:
                time.sleep(max(0, .11-(time.monotonic()-self.last)))
            self.guard()
            binding = self.provider._spec.binding
            lease = self.provider(binding, binding.owner)
            spec = lease.spec
            declaration = DemoReadCredential(binding, lease.credentials, spec.parent_uid, spec.egress_ip,
                spec.provisioning_digest, spec.credential_revision, lease.expires_ms)
            packet = SignedDemoReadRequest(declaration, timestamp_ms=self.now(), axis=axis, cursor=cursor)
            self.last = time.monotonic()
        result = self.transport(packet)
        self.guard()
        _, at = parse.envelope(result)
        if not 0 <= self.now()-milliseconds(at) <= 5000:
            raise DemoRejected("native_h1_source_stale")
        return result

    def pending_empty(self):
        binding = self.provider._spec.binding
        def family(axis):
            pages, cursor = [], None
            for _ in range(10):
                response = self.get(axis, cursor)
                pages.append(DemoPacket(DemoReadPlan(binding, axis, cursor), startup_pending_response(response)))
                rows, complete = _pages(pages, axis, binding, binding.owner, self.now())
                if rows:
                    raise DemoRejected("native_pending_orders_present")
                if complete:
                    return
                raw, _ = parse.envelope(response)
                cursor = raw["endId"]
            raise DemoRejected("native_pending_scope_incomplete")
        with ThreadPoolExecutor(max_workers=3) as pool:
            tuple(pool.map(family, FAMILIES))

    def configs(self, symbols):
        with ThreadPoolExecutor(max_workers=3) as pool:
            replies = tuple(pool.map(self.get, symbols))
        return {s: parse.envelope(r)[0] for s, r in zip(symbols, replies, strict=True)}

    def admit(self, journal, intent, receipt, context):
        start = self.now()
        if receipt != journal.receipt or context != intent.binding.owner:
            raise DemoRejected("original_native_admission_scope_changed")
        with ThreadPoolExecutor(max_workers=3) as pool:
            config, wallet, positions = tuple(pool.map(self.get, (intent.grid.symbol, "wallet", "positions")))
        raw, _ = parse.envelope(config)
        if type(raw) is not dict or not profile_matches(raw):
            raise DemoRejected("native_profile_not_ready")
        snapshot = margin_snapshot(wallet, positions, intent, context=context, now_ms=self.now(), policy=self.policy)
        ledger = journal.state.book.signal.economic.ledger
        owned = {b.symbol: b for b in ledger.baskets if b.quantity}
        native = {p.symbol: p for p in snapshot.positions}
        if (set(owned) != set(native)
                or any(native[s].quantity != b.quantity or abs(native[s].average_entry-b.average_entry) >
                       min(D(1).scaleb(native[s].average_entry.as_tuple().exponent),
                           ledger.plan.grid_rules[ledger.plan.symbols.index(s)].price_tick)
                       for s, b in owned.items())
                or abs(snapshot.collateral_without_upl-ledger.unposted_cash
                       -sum((b.isolated_balance for b in ledger.baskets), D(0))) > D(".00000004")):
            raise DemoRejected("native_owned_account_not_reconciled")
        self.pending_empty()
        if self.now()-start > 5000:
            raise DemoRejected("native_order_admission_cohort_expired")
        self.guard()

    def prepare_profiles(self, symbols, root, ip_binding):
        # Every settings POST requires a new independent flat-account proof and
        # all five current pending families empty. No setting change on positions.
        configured = self.configs(symbols)
        fd = _directory(root)
        try:
            for symbol in symbols:
                raw = configured[symbol]
                if profile_matches(raw):
                    continue
                if raw.get("posMode") != "one_way_mode" or raw.get("assetMode") != "single":
                    raise DemoRejected("native_position_or_asset_mode_requires_manual_setup")
                for kind, target, additions in (
                    ("margin", "/api/v2/mix/account/set-margin-mode", {"marginMode": "isolated"}),
                    ("leverage", "/api/v2/mix/account/set-leverage", {"leverage": "2"}),
                ):
                    current, _ = parse.envelope(self.get(symbol))
                    if kind == "margin" and current.get("marginMode") == "isolated":
                        continue
                    if kind == "leverage" and current.get("isolatedLongLever") in (2, "2"):
                        continue
                    proof = NativeStartAccountSource(self.provider, guard=self.guard, shared_lock=threading.Lock(),
                        ip_binding=ip_binding, transport=self.transport, milliseconds=self.now, policy=self.policy).read(
                            context=self.provider._spec.binding.owner)
                    if proof.account is None:
                        raise DemoRejected("native_settings_account_not_flat")
                    self.pending_empty()
                    body = json.dumps(dict(symbol=symbol, productType="USDT-FUTURES", marginCoin="USDT",
                                           **additions), separators=(",", ":")).encode()
                    name = hashlib.sha256((self.policy.policy_digest+target).encode()+body).hexdigest()
                    try:
                        mark = _file(fd, name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
                    except FileExistsError:
                        raise DemoRejected("native_configuration_unconfirmed_no_retry") from None
                    try:
                        raw_marker = json.dumps(dict(target=target, body_sha256=hashlib.sha256(body).hexdigest(),
                            account_source=proof.source_digest, policy_digest=self.policy.policy_digest)).encode()
                        if os.write(mark, raw_marker) != len(raw_marker):
                            raise OSError()
                        os.fsync(mark); os.fsync(fd)
                    finally:
                        os.close(mark)
                    self.guard()
                    lease = self.provider(self.provider._spec.binding, self.provider._spec.binding.owner)
                    timestamp = self.now()
                    signature = hmac_sha256_base64(lease.credentials._secret_key,
                        str(timestamp).encode()+b"POST"+target.encode()+body)
                    tls = ssl.create_default_context()
                    tls.minimum_version = ssl.TLSVersion.TLSv1_2
                    request = Request("https://api.bitget.com"+target, data=body, method="POST", headers={
                        "ACCESS-KEY": lease.credentials._api_key, "ACCESS-SIGN": signature,
                        "ACCESS-TIMESTAMP": str(timestamp), "ACCESS-PASSPHRASE": lease.credentials._passphrase,
                        "paptrading": "1", "Content-Type": "application/json"})
                    try:
                        with build_opener(ProxyHandler({}), HTTPSHandler(context=tls), _NoRedirect()).open(request, timeout=3) as r:
                            r.read(65537)
                    except Exception:
                        pass  # Unknown POST is never repeated. Only native GET can confirm.
                    self.guard()
                    result, _ = parse.envelope(self.get(symbol))
                    matches = (result.get("marginMode") == "isolated" if kind == "margin"
                               else result.get("isolatedLongLever") in (2, "2"))
                    if not matches:
                        raise DemoRejected("native_configuration_unconfirmed_no_retry")
        finally:
            os.close(fd)
