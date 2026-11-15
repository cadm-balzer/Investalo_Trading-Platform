"""Bounded offline account/order cohort checks; always advisory, never dispatch."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, localcontext
import hashlib
from urllib.parse import urlencode

from .futures_demo import DemoBinding, DemoRejected, SYMBOLS, clock, digest, number
from .futures_demo_outbox import OutboxReceipt, _trace_record
from .futures_demo_reconcile import DemoTrace, FRESH_MS, TERMINAL, native_id, position_quantities
from .models import ProductType
from .parse import EPOCH, amount, envelope, futures_accounts

AXES = ("wallet", "positions", "live", "partially_filled", "normal_plan", "track_plan", "profit_loss")
CONFIGS = tuple(sorted(SYMBOLS))
VERSION = "bitget-demo-account-check/1"


@dataclass(frozen=True, repr=False)
class DemoReadPlan:
    binding: DemoBinding
    axis: str
    cursor: str | None = None
    method: str = field(default="GET", init=False)
    target: str = field(init=False)
    headers: tuple = field(default=(("paptrading", "1"),), init=False)

    def __post_init__(self):
        if not isinstance(self.binding, DemoBinding) or not isinstance(self.axis, str):
            raise DemoRejected("invalid_read_plan")
        common = (("productType", "USDT-FUTURES"),)
        if self.axis == "wallet":
            path, query = "/api/v2/mix/account/accounts", common
        elif self.axis == "positions":
            path, query = "/api/v2/mix/position/all-position", common + (("marginCoin", "USDT"),)
        elif self.axis in CONFIGS:
            path, query = "/api/v2/mix/account/account", (
                ("symbol", self.axis),) + common + (("marginCoin", "USDT"),)
        elif self.axis in ("live", "partially_filled"):
            path, query = "/api/v2/mix/order/orders-pending", common + (
                ("status", self.axis), ("limit", "100"))
        elif self.axis in ("normal_plan", "track_plan", "profit_loss"):
            path, query = "/api/v2/mix/order/orders-plan-pending", common + (
                ("planType", self.axis), ("limit", "100"))
        else:
            raise DemoRejected("unsupported_read_axis")
        if self.cursor is not None:
            if self.axis in ("wallet", "positions", *CONFIGS):
                raise DemoRejected("unexpected_cursor")
            native_id(self.cursor)
            query += (("idLessThan", self.cursor),)
        object.__setattr__(self, "target", path + "?" + urlencode(query))


@dataclass(frozen=True, repr=False)
class DemoPacket:
    """Transport must bind this plan to its actual reply; not native UID proof."""
    plan: DemoReadPlan
    response: object


@dataclass(frozen=True, repr=False)
class AccountExpectation:
    """Trusted own declared baseline; never infer it from this same native cohort."""
    binding: DemoBinding
    initial_positions: tuple[tuple[str, Decimal], ...]
    expected_available: Decimal | None
    reserved_cash: Decimal

    def __post_init__(self):
        if (not isinstance(self.binding, DemoBinding) or not isinstance(self.initial_positions, tuple)
                or len(self.initial_positions) != len(CONFIGS)):
            raise DemoRejected("invalid_account_expectation")
        for pair in self.initial_positions:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise DemoRejected("invalid_account_expectation")
            number(pair[1], zero=True)
        if tuple(pair[0] for pair in self.initial_positions) != CONFIGS:
            raise DemoRejected("complete_sorted_initial_positions_required")
        if self.expected_available is not None:
            if not isinstance(self.expected_available, Decimal):
                raise DemoRejected("invalid_cash_expectation")
            number(self.expected_available.copy_abs(), zero=True)
        number(self.reserved_cash, zero=True)


@dataclass(frozen=True, repr=False)
class AccountCheck:
    binding_digest: str
    receipt: OutboxReceipt
    checked_at_ms: int
    earliest_response_ms: int
    latest_response_ms: int
    source_hashes: tuple[tuple[str, str | None, str], ...]
    available: Decimal | None
    account_equity: Decimal | None
    unrealized_pnl: Decimal | None
    positions: tuple[tuple[str, Decimal], ...]
    own_pending: tuple[str, ...]
    foreign_pending: tuple[str, ...]
    trigger_count: int
    blockers: tuple[str, ...]
    execution_ready: bool = field(default=False, init=False)
    cash_ledger_ready: bool = field(default=False, init=False)
    pending_scope_verified: bool = field(default=False, init=False)

    @property
    def matched(self):
        return not self.blockers

    def check_current(self, binding, receipt, *, context, now_ms):
        if not isinstance(binding, DemoBinding) or not isinstance(receipt, OutboxReceipt):
            raise DemoRejected("invalid_account_check_scope")
        binding.check(context)
        clock(now_ms)
        if (self.binding_digest != digest(binding.record()) or self.receipt != receipt
                or now_ms < self.checked_at_ms
                or not 0 <= now_ms - self.earliest_response_ms <= FRESH_MS):
            raise DemoRejected("obsolete_account_check")


def _frame(packet, binding, context, now_ms):
    if (not isinstance(packet, DemoPacket) or not isinstance(packet.plan, DemoReadPlan)
            or packet.plan.binding != binding):
        raise DemoRejected("foreign_account_packet")
    binding.check(context)
    raw, at = envelope(packet.response)
    delta = at - EPOCH
    millis = delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000
    if not 0 <= now_ms - millis <= FRESH_MS:
        raise DemoRejected("stale_account_packet")
    return raw, millis


def _pages(packets, axis, binding, context, now_ms):
    """Continue every nonempty endId to an empty terminal page; never assume a short page is final."""
    rows, cursor, complete, seen = [], None, False, set()
    for packet in packets:
        if complete or packet.plan.cursor != cursor:
            raise DemoRejected("pending_page_sequence_mismatch")
        raw, _ = _frame(packet, binding, context, now_ms)
        if (not isinstance(raw, dict) or "endId" not in raw
                or not isinstance(raw.get("entrustedList"), list)
                or len(raw["entrustedList"]) > 100):
            raise DemoRejected("invalid_pending_page")
        values = raw["entrustedList"]
        ending = native_id(raw["endId"], optional=True)
        page_ids = set()
        for row in values:
            if not isinstance(row, dict):
                raise DemoRejected("invalid_pending_order")
            identifier = native_id(row.get("orderId"))
            if identifier in seen or cursor is not None and int(identifier) >= int(cursor):
                raise DemoRejected("duplicate_or_regressed_pending_id")
            seen.add(identifier)
            page_ids.add(identifier)
            if axis in ("live", "partially_filled") and row.get("status") != axis:
                raise DemoRejected("wrong_pending_status")
            rows.append(row)
        if ending is not None:
            if not values or ending not in page_ids or cursor is not None and int(ending) >= int(cursor):
                raise DemoRejected("invalid_pending_cursor")
            cursor = ending
        elif not values:
            complete = True
        else:
            # Nonempty data without continuation cannot prove full product coverage.
            break
    return rows, complete


def check_account(expectation, receipt, traces, packets, *, context, now_ms):
    if not isinstance(expectation, AccountExpectation):
        raise DemoRejected("invalid_account_expectation")
    binding = expectation.binding
    binding.check(context)
    clock(now_ms)
    if (not isinstance(receipt, OutboxReceipt) or not isinstance(traces, tuple)
            or any(not isinstance(t, DemoTrace) or t.intent.binding != binding for t in traces)):
        raise DemoRejected("foreign_outbox_snapshot")
    keys = [str(t.intent.command_id) for t in traces]
    if (len(keys) != len(set(keys)) or len(traces) > 10_000
            or receipt.binding_digest != digest(binding.record())
            or receipt.state_digest != digest({"binding": binding.record(),
                "traces": [_trace_record(t) for t in sorted(traces, key=lambda t: str(t.intent.command_id))]})):
        raise DemoRejected("outbox_state_receipt_mismatch")
    if not isinstance(packets, tuple) or not 14 <= len(packets) <= 59:
        raise DemoRejected("bounded_complete_account_cohort_required")
    groups = {axis: [] for axis in (*AXES, *CONFIGS)}
    clocks, hashes = [], []
    for packet in packets:
        _, at = _frame(packet, binding, context, now_ms)
        axis = packet.plan.axis
        groups[axis].append(packet)
        clocks.append(at)
        hashes.append((axis, packet.plan.cursor, hashlib.sha256(packet.response.body).hexdigest()))
    for axis, pages in groups.items():
        if not pages or len(pages) > (1 if axis in ("wallet", "positions", *CONFIGS) else 10):
            raise DemoRejected("missing_or_duplicate_account_axis")
    blockers = set()
    for symbol in CONFIGS:
        raw, _ = _frame(groups[symbol][0], binding, context, now_ms)
        if not isinstance(raw, dict):
            raise DemoRejected("invalid_symbol_config")
        leverage = raw.get("isolatedLongLever")
        if (raw.get("marginCoin") != "USDT" or raw.get("assetMode") != "single"
                or raw.get("marginMode") != "isolated" or raw.get("posMode") != "one_way_mode"
                or not (type(leverage) is int and leverage == 2 or type(leverage) is str and leverage == "2")):
            blockers.add("unsupported_account_configuration")
    wallet, _ = futures_accounts(groups["wallet"][0].response, ProductType.USDT)
    if len(wallet) != 1 or wallet[0].margin_coin != "USDT":
        raise DemoRejected("single_usdt_wallet_required")
    wallet = wallet[0]
    if (wallet.asset_mode != "single" or wallet.crossed_margin != Decimal(0)
            or wallet.coupon != Decimal(0) or wallet.grant != Decimal(0)
            or wallet.assets not in (None, ())):
        blockers.add("unsupported_wallet_or_unknown_collateral")
    if any(value is None for value in (wallet.available, wallet.locked, wallet.account_equity,
                                       wallet.unrealized_pnl, wallet.isolated_margin)):
        blockers.add("wallet_amounts_unknown")
    if expectation.expected_available is None:
        blockers.add("cash_expectation_unknown")
    elif wallet.available != expectation.expected_available:
        blockers.add("cash_drift")
    if wallet.available is None or wallet.available < expectation.reserved_cash:
        blockers.add("cash_below_declared_reservations")
    raw, _ = _frame(groups["positions"][0], binding, context, now_ms)
    actual = position_quantities(raw)
    if (not any(actual.values())
            and (wallet.isolated_margin != Decimal(0) or wallet.unrealized_pnl != Decimal(0))):
        blockers.add("wallet_exposure_drift")
    expected, unresolved = dict(expectation.initial_positions), set()
    ordered = sorted((t for t in traces if t.dispatch_ms is not None),
                     key=lambda t: (t.dispatch_ms, str(t.intent.command_id)))
    if any(min(clocks) < max(t.dispatch_ms, t.observation.response_ms if t.observation else 0)
           for t in ordered):
        blockers.add("account_cohort_precedes_order_evidence")
    ticks = set()
    for trace in ordered:
        symbol = trace.intent.grid.symbol
        tick = (symbol, trace.dispatch_ms)
        if tick in ticks or symbol in unresolved or expected[symbol] != trace.intent.before_quantity:
            blockers.add("ambiguous_order_sequence")
            unresolved.add(symbol)
        ticks.add(tick)
        if trace.observation is None:
            unresolved.add(symbol)
        else:
            with localcontext() as ctx:
                ctx.prec = 160
                expected[symbol] += (trace.observation.quantity if trace.intent.action == "open_long"
                                     else -trace.observation.quantity)
            if trace.observation.quantity > 0 and trace.observation.reported_fee is None:
                blockers.add("order_fees_unknown")
        if trace.state not in TERMINAL:
            blockers.add("unresolved_order")
    for symbol in CONFIGS:
        if symbol not in unresolved and actual.get(symbol, Decimal(0)) != expected[symbol]:
            blockers.add("position_drift")
    own, foreign, ids = [], [], set()
    indexed = {t.intent.client_oid: t for t in traces}
    trigger_count = 0
    for axis in AXES[2:]:
        rows, complete = _pages(groups[axis], axis, binding, context, now_ms)
        if not complete:
            blockers.add("pending_coverage_incomplete")
        for row in rows:
            identifier = row["orderId"]
            if identifier in ids:
                raise DemoRejected("duplicate_pending_id_across_axes")
            ids.add(identifier)
            if axis not in ("live", "partially_filled"):
                trigger_count += 1
                blockers.add("trigger_orders_present")
                continue
            blockers.add("normal_orders_present")
            client_oid = row.get("clientOid")
            if client_oid is not None and (not isinstance(client_oid, str) or len(client_oid) > 128):
                raise DemoRejected("invalid_pending_client_id")
            trace = indexed.get(client_oid)
            if trace is None:
                foreign.append(identifier)
                blockers.add("foreign_orders_present")
            else:
                symbol = row.get("symbol")
                if (not isinstance(symbol, str) or not symbol.isascii()
                        or symbol.upper() != trace.intent.grid.symbol or trace.can_submit
                        or trace.state in TERMINAL or trace.order_id not in (None, identifier)
                        or amount(row.get("size")) != trace.intent.quantity):
                    blockers.add("own_pending_order_drift")
                own.append(identifier)
    return AccountCheck(digest(binding.record()), receipt, now_ms, min(clocks), max(clocks),
                        tuple(hashes), wallet.available, wallet.account_equity, wallet.unrealized_pnl,
                        tuple((s, actual.get(s, Decimal(0))) for s in CONFIGS),
                        tuple(own), tuple(foreign), trigger_count, tuple(sorted(blockers)))
