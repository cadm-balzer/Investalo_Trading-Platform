"""Read-only initial Demo checks. This report cannot authorize an order."""
from decimal import Decimal
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import json
import threading

from investalo_bitget import parse
from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.futures_demo_account import CONFIGS, AXES, _pages, DemoPacket, DemoReadPlan
from investalo_bitget.transport import ReadResponse

SCHEMA = "investalo-demo-startup/1"
BLOCKERS = frozenset(("initial_balance_changed", "wallet_unknown", "wallet_collateral",
    "positions_present", "orders_present", "order_pages_incomplete", "configuration_mismatch"))
PAGE_REASONS = frozenset(("foreign_account_packet", "stale_account_packet",
    "pending_page_sequence_mismatch", "invalid_pending_page", "invalid_order_id",
    "invalid_pending_order", "duplicate_or_regressed_pending_id",
    "wrong_pending_status", "invalid_pending_cursor"))


def pending_failure(error, response):
    """Private fixed classifications only; never copy native values or messages."""
    reason = str(error) if type(error) is DemoRejected else None
    raw, _ = parse.envelope(response)
    shape = dict(data="object" if type(raw) is dict else "other",
                 rows="missing", cursor="missing")
    if type(raw) is dict:
        if "entrustedList" in raw:
            rows = raw["entrustedList"]
            shape["rows"] = "array" if type(rows) is list else "null" if rows is None else "other"
            if type(rows) is list:
                shape["row_count"] = min(len(rows), 101)
        if "endId" in raw:
            cursor = raw["endId"]
            shape["cursor"] = ("null" if cursor is None else
                "empty_string" if type(cursor) is str and cursor == "" else
                "zero_string" if type(cursor) is str and cursor == "0" else
                "zero_integer" if type(cursor) is int and cursor == 0 else
                "other")
    return dict(reason=reason if reason in PAGE_REASONS else "unclassified", shape=shape)


def startup_pending_response(response):
    """Native Demo empty-page variant; preserve the original envelope clock."""
    raw, _ = parse.envelope(response)
    if (type(raw) is dict and set(raw) == {"entrustedList", "endId"}
            and raw["entrustedList"] is None and raw["endId"] is None):
        frame = json.loads(response.body)
        frame["data"] = dict(entrustedList=[], endId=None)
        return ReadResponse(response.status, json.dumps(frame, separators=(",", ":")).encode())
    return response


def inspect_startup(get, binding, owner, account, wallet):
    configs, clocks = [], [datetime.fromisoformat(account["observed_at"])]
    blockers = set()
    if wallet.available is None or wallet.account_equity is None:
        blockers.add("wallet_unknown")
    elif wallet.available != Decimal("10000") or wallet.account_equity != Decimal("10000"):
        blockers.add("initial_balance_changed")
    if any(v is None for v in (wallet.locked, wallet.isolated_margin,
                               wallet.crossed_margin, wallet.unrealized_pnl)):
        blockers.add("wallet_unknown")
    if (wallet.asset_mode != "single" or wallet.assets not in (None, ())
            or any(v != Decimal(0) for v in (wallet.coupon, wallet.grant, wallet.locked,
                wallet.isolated_margin, wallet.crossed_margin, wallet.unrealized_pnl))):
        blockers.add("wallet_collateral")
    if account["positions"]:
        blockers.add("positions_present")
    cancelled, failure_lock, first_failure = threading.Event(), threading.Lock(), []

    def job(function, axis):
        if cancelled.is_set():
            raise ValueError()
        try:
            return function(axis)
        except Exception as error:
            if not hasattr(error, "_demo_startup_stage"):
                error._demo_startup_stage = axis + ":parse"
            with failure_lock:
                if not first_failure:
                    first_failure.append(error)
            cancelled.set()
            raise

    def request(axis, cursor=None):
        if cancelled.is_set():
            raise ValueError()
        return get(axis, cursor)

    def configuration(symbol):
        response = request(symbol)
        raw, at = parse.envelope(response)
        if type(raw) is not dict:
            raise ValueError()
        # The exact requested symbol is bound by the signed GET; some native
        # account replies omit symbol. An explicitly conflicting value rejects.
        if "symbol" in raw and raw["symbol"] != symbol:
            raise ValueError()
        margin = raw.get("marginMode") if raw.get("marginMode") in ("isolated", "crossed") else None
        mode = raw.get("posMode") if raw.get("posMode") in ("one_way_mode", "hedge_mode") else None
        assets = raw.get("assetMode") if raw.get("assetMode") in ("single", "union") else None
        native_leverage = raw.get("isolatedLongLever")
        # Bitget's declared string field also appears as an integer in its
        # current official example. Booleans/floats never become a leverage.
        if type(native_leverage) is int and 1 <= native_leverage <= 125:
            native_leverage = str(native_leverage)
        leverage = parse.amount(native_leverage)
        matches = (raw.get("marginCoin") == "USDT" and margin == "isolated"
                   and mode == "one_way_mode" and assets == "single" and leverage == Decimal(2))
        return dict(symbol=symbol, margin_mode=margin, position_mode=mode, asset_mode=assets,
            long_leverage=None if leverage is None else format(leverage, "f"), matches=matches), at

    def orders(axis):
        times = []
        pages, cursor = [], None
        for _ in range(10):
            response = request(axis, cursor)
            packet = DemoPacket(DemoReadPlan(binding, axis, cursor),
                                startup_pending_response(response))
            pages.append(packet)
            _, at = parse.envelope(response)
            times.append(at)
            # Use the existing bounded, monotonic cursor/ID/status validator.
            try:
                rows, complete = _pages(pages, axis, binding, owner,
                                        int(datetime.now(timezone.utc).timestamp() * 1000))
            except Exception as error:
                error._demo_pending_failure = pending_failure(error, response)
                raise
            if complete:
                break
            raw, _ = parse.envelope(response)
            cursor = raw["endId"]
            if not cursor:
                break
        return dict(category=axis, count=len(rows), pages=len(pages), complete=complete), {
            row["orderId"] for row in rows}, times

    # Independent configs/families overlap, at most three sockets. Every GET
    # still passes the caller's paced, fresh before/after credential guards.
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="demo-startup") as pool:
        try:
            # One queue lets a pending family use a free worker while the
            # final independent config is in flight; no whole-group barrier.
            results = list(pool.map(lambda axis: job(
                configuration if axis in CONFIGS else orders, axis), (*CONFIGS, *AXES[2:])))
            projected, pending = results[:len(CONFIGS)], results[len(CONFIGS):]
        except Exception:
            cancelled.set()
            if first_failure:
                raise first_failure[0] from None
            raise
    for config, at in projected:
        configs.append(config)
        clocks.append(at)
        if not config["matches"]:
            blockers.add("configuration_mismatch")
    counts, seen_ids = [], set()
    for count, ids, times in pending:
        if seen_ids & ids:
            raise ValueError()
        seen_ids.update(ids)
        if count["count"]:
            blockers.add("orders_present")
        if not count["complete"]:
            blockers.add("order_pages_incomplete")
        counts.append(count)
        clocks.extend(times)
    if not 0 <= (datetime.now(timezone.utc) - min(clocks)).total_seconds() <= 5:
        raise ValueError()
    return validate_startup(dict(schema=SCHEMA, account=account, observed_at=min(clocks).isoformat(),
        configurations=configs, orders=counts, blockers=sorted(blockers),
        expected_initial_usdt="10000", pending_scope_verified=False, costs_verified=False, execution_enabled=False))


def validate_startup(value):
    from .demo_account_sync import validate_view, public_amount
    if (type(value) is not dict or set(value) != {"schema", "account", "observed_at",
            "configurations", "orders", "blockers", "expected_initial_usdt",
            "pending_scope_verified", "costs_verified", "execution_enabled"}
            or value["schema"] != SCHEMA or value["expected_initial_usdt"] != "10000"
            or any(value[k] is not False for k in ("pending_scope_verified", "costs_verified", "execution_enabled"))):
        raise ValueError()
    validate_view(value["account"])
    at = datetime.fromisoformat(value["observed_at"])
    if at.tzinfo is None or at > datetime.fromisoformat(value["account"]["observed_at"]):
        raise ValueError()
    configs = value["configurations"]
    if (type(configs) is not list or len(configs) != len(CONFIGS)
            or tuple(c.get("symbol") for c in configs if type(c) is dict) != CONFIGS):
        raise ValueError()
    for c in configs:
        if (set(c) != {"symbol", "margin_mode", "position_mode", "asset_mode", "long_leverage", "matches"}
                or c["margin_mode"] not in (None, "isolated", "crossed")
                or c["position_mode"] not in (None, "one_way_mode", "hedge_mode")
                or c["asset_mode"] not in (None, "single", "union") or type(c["matches"]) is not bool):
            raise ValueError()
        leverage = None if c["long_leverage"] is None else public_amount(c["long_leverage"])
        if c["matches"] and (c["margin_mode"] != "isolated" or c["position_mode"] != "one_way_mode"
                            or c["asset_mode"] != "single" or leverage != Decimal(2)):
            raise ValueError()
    if type(value["orders"]) is not list or len(value["orders"]) != 5:
        raise ValueError()
    for axis, o in zip(AXES[2:], value["orders"]):
        if (type(o) is not dict or set(o) != {"category", "count", "pages", "complete"}
                or o["category"] != axis or type(o["count"]) is not int or not 0 <= o["count"] <= 1000
                or type(o["pages"]) is not int or not 1 <= o["pages"] <= 10 or type(o["complete"]) is not bool):
            raise ValueError()
    if (type(value["blockers"]) is not list or value["blockers"] != sorted(set(value["blockers"]))
            or any(type(b) is not str or b not in BLOCKERS for b in value["blockers"])):
        raise ValueError()
    for blocker, required in (
            ("configuration_mismatch", any(not c["matches"] for c in configs)),
            ("orders_present", any(o["count"] for o in value["orders"])),
            ("order_pages_incomplete", any(not o["complete"] for o in value["orders"])),
            ("positions_present", bool(value["account"]["positions"]))):
        if required != (blocker in value["blockers"]):
            raise ValueError()
    wallet = value["account"]["wallet"]
    known = wallet["equity"] is not None and wallet["available"] is not None
    changed = known and (public_amount(wallet["equity"], signed=True) != Decimal(10000)
                        or public_amount(wallet["available"], signed=True) != Decimal(10000))
    if bool(changed) != ("initial_balance_changed" in value["blockers"]):
        raise ValueError()
    if any(v is None for v in wallet.values()) and "wallet_unknown" not in value["blockers"]:
        raise ValueError()
    if len(json.dumps(value, separators=(",", ":")).encode()) > 65536:
        raise ValueError()
    return value
