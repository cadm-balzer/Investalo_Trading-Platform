"""Offline scoped cumulative-order checks, never a durable outbox or fill ledger."""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, localcontext
import re

from .futures_demo import DemoIntent, DemoRejected, clock, number, SYMBOLS
from .futures_demo_market import BTCMarketIntent
from .parse import amount, envelope, EPOCH, timestamp_ms

FRESH_MS = 5_000
TERMINAL = frozenset(("filled", "canceled"))


def frame(response, intent, context, now_ms):
    if type(intent) not in (DemoIntent, BTCMarketIntent):
        raise DemoRejected("invalid_intent")
    intent.binding.check(context)
    clock(now_ms)
    raw, at = envelope(response)
    delta = at - EPOCH
    at_ms = delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000
    if not 0 <= now_ms - at_ms <= FRESH_MS:
        raise DemoRejected("stale_or_future_response")
    return raw, at_ms


def native_id(value, *, optional=False):
    if optional and value in (None, ""):
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,39}", value):
        raise DemoRejected("invalid_order_id")
    return value


@dataclass(frozen=True, repr=False)
class DemoTrace:
    """Pure replay candidate; caller must durably CAS before any network send."""
    intent: DemoIntent
    state: str = "prepared"
    dispatch_ms: int | None = None
    order_id: str | None = None
    observation: OrderObservation | None = None

    def __post_init__(self):
        if (type(self.intent) not in (DemoIntent, BTCMarketIntent) or self.state not in
                ("prepared", "submission_unknown", "acknowledged", "live",
                 "partially_filled", "filled", "canceled")):
            raise DemoRejected("invalid_trace")
        native_id(self.order_id, optional=True)
        if self.state == "prepared":
            if self.dispatch_ms is not None or self.order_id is not None or self.observation is not None:
                raise DemoRejected("invalid_trace")
        else:
            clock(self.dispatch_ms)
        if self.observation is not None:
            if (not isinstance(self.observation, OrderObservation)
                    or self.observation.intent_digest != self.intent.intent_digest
                    or self.state != self.observation.state
                    or self.order_id != self.observation.order_id
                    or self.observation.created_ms < self.dispatch_ms
                    or self.observation.quantity > self.intent.quantity
                    or self.state == "filled" and self.observation.quantity != self.intent.quantity
                    or self.state in ("partially_filled", "canceled")
                    and self.observation.quantity == self.intent.quantity):
                raise DemoRejected("invalid_trace")
            average = self.observation.average_price
            if (type(self.intent) is DemoIntent and average is not None and (
                self.intent.action == "open_long" and average > self.intent.limit_price
                or self.intent.action == "reduce_long" and average < self.intent.limit_price
            )):
                raise DemoRejected("fill_outside_limit")
        elif self.state in ("live", "partially_filled", "filled", "canceled"):
            raise DemoRejected("missing_observation")

    @property
    def can_submit(self):
        return self.state == "prepared"

    def dispatched(self, *, context, at_ms):
        self.intent.binding.check(context)
        clock(at_ms)
        if not self.can_submit:
            raise DemoRejected("resend_denied")
        return replace(self, state="submission_unknown", dispatch_ms=at_ms)


def acknowledge(trace, response, *, context, now_ms):
    if not isinstance(trace, DemoTrace) or trace.state != "submission_unknown":
        raise DemoRejected("unexpected_acknowledgement")
    raw, at_ms = frame(response, trace.intent, context, now_ms)
    if (at_ms < trace.dispatch_ms or not isinstance(raw, dict)
            or raw.get("clientOid") != trace.intent.client_oid):
        raise DemoRejected("acknowledgement_mismatch")
    # Successful reduce-only acknowledgement may omit orderId. Never invent fills.
    return replace(trace, state="acknowledged",
                   order_id=native_id(raw.get("orderId"), optional=True))


@dataclass(frozen=True, repr=False)
class OrderObservation:
    intent_digest: str
    order_id: str
    state: str
    quantity: Decimal
    average_price: Decimal | None
    reported_fee: Decimal | None
    created_ms: int
    updated_ms: int
    response_ms: int

    def __post_init__(self):
        if (not isinstance(self.intent_digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", self.intent_digest)
                or self.state not in ("live", "partially_filled", "filled", "canceled")):
            raise DemoRejected("invalid_order_observation")
        native_id(self.order_id)
        number(self.quantity, zero=True)
        if (self.quantity == 0 and self.average_price is not None
                or self.quantity > 0 and self.average_price is None
                or self.state == "live" and self.quantity != 0
                or self.state in ("partially_filled", "filled") and self.quantity == 0):
            raise DemoRejected("invalid_cumulative_fill")
        if self.average_price is not None:
            number(self.average_price)
        if self.reported_fee is not None:
            if not isinstance(self.reported_fee, Decimal):
                raise DemoRejected("invalid_fee")
            number(self.reported_fee.copy_abs(), zero=True)
        for value in (self.created_ms, self.updated_ms, self.response_ms):
            clock(value)
        if not self.created_ms <= self.updated_ms <= self.response_ms:
            raise DemoRejected("invalid_order_clock")


def order_detail(response, intent, *, context, now_ms):
    raw, at_ms = frame(response, intent, context, now_ms)
    if not isinstance(raw, dict):
        raise DemoRejected("invalid_order_detail")
    expected = {
        "symbol": intent.grid.symbol, "clientOid": intent.client_oid,
        "marginCoin": "USDT", "marginMode": "isolated",
        "posMode": "one_way_mode", "orderType": "market" if type(intent) is BTCMarketIntent else "limit",
        "side": "buy" if intent.action == "open_long" else "sell",
        "reduceOnly": "NO" if intent.action == "open_long" else "YES",
    }
    if type(intent) is DemoIntent:
        expected["force"] = "ioc"
    for key, value in expected.items():
        actual = raw.get(key)
        if key in ("symbol", "marginCoin", "reduceOnly") and isinstance(actual, str):
            if not actual.isascii():
                raise DemoRejected("order_identity_mismatch")
            actual = actual.upper()  # documented native example uses lower case
        if actual != value:
            raise DemoRejected("order_identity_mismatch")
    if (raw.get("posSide") not in ("net", "long")
            or amount(raw.get("leverage")) != Decimal(2)
            or amount(raw.get("size")) != intent.quantity
            or type(intent) is DemoIntent and amount(raw.get("price")) != intent.limit_price):
        raise DemoRejected("order_terms_mismatch")
    state = raw.get("state")
    qty = amount(raw.get("baseVolume"))
    average = amount(raw.get("priceAvg"))
    if (state not in ("live", "partially_filled", "filled", "canceled")
            or qty is None or not 0 <= qty <= intent.quantity
            or state == "live" and qty != 0
            or state == "partially_filled" and not 0 < qty < intent.quantity
            or state == "filled" and qty != intent.quantity
            or state == "canceled" and qty == intent.quantity):
        raise DemoRejected("invalid_cumulative_fill")
    if qty == 0:
        if average not in (None, Decimal(0)):
            raise DemoRejected("average_without_fill")
        average = None
    elif (average is None or average <= 0
          or type(intent) is DemoIntent and (
              intent.action == "open_long" and average > intent.limit_price
              or intent.action == "reduce_long" and average < intent.limit_price)):
        raise DemoRejected("fill_outside_limit")
    # Fee sign/availability retained exactly; this is NOT a calibrated net-PnL ledger.
    fee = amount(raw.get("fee"), signed=True)
    created, updated = raw.get("cTime"), raw.get("uTime")
    created, updated = timestamp_ms(created), timestamp_ms(updated)
    if not created <= updated <= at_ms:
        raise DemoRejected("invalid_order_clock")
    return OrderObservation(intent.intent_digest, native_id(raw.get("orderId")),
                            state, qty, average, fee, created, updated, at_ms)


def observe(trace, response, *, context, now_ms):
    if not isinstance(trace, DemoTrace) or trace.can_submit:
        raise DemoRejected("order_not_dispatched")
    current = order_detail(response, trace.intent, context=context, now_ms=now_ms)
    return apply_observation(trace, current)


def apply_observation(trace, current):
    """Replay already validated private journal evidence; grants no HTTP authority."""
    if (not isinstance(trace, DemoTrace) or trace.can_submit
            or not isinstance(current, OrderObservation)
            or current.intent_digest != trace.intent.intent_digest):
        raise DemoRejected("order_receipt_mismatch")
    if (current.response_ms < trace.dispatch_ms or current.created_ms < trace.dispatch_ms
            or trace.order_id is not None and trace.order_id != current.order_id):
        raise DemoRejected("order_receipt_mismatch")
    old = trace.observation
    if old is not None:
        if (current.created_ms != old.created_ms
                or current.updated_ms < old.updated_ms
                or current.response_ms < old.response_ms or current.quantity < old.quantity
                or current.quantity == old.quantity and current.average_price != old.average_price
                or old.state == "partially_filled" and current.state == "live"):
            raise DemoRejected("order_regression")
        # A later poll may report a fee where an earlier snapshot omitted it.
        old_terms = (old.state, old.quantity, old.average_price)
        terms = (current.state, current.quantity, current.average_price)
        if ((old.state in TERMINAL or current.updated_ms == old.updated_ms) and terms != old_terms
                or old.reported_fee is not None and current.reported_fee != old.reported_fee
                and current.updated_ms == old.updated_ms):
            raise DemoRejected("contradictory_order_snapshot")
    return replace(trace, state=current.state, order_id=current.order_id, observation=current)


def position_quantity(response, intent, *, context, now_ms):
    """Whole USDT product snapshot; unsupported/foreign exposure stops this profile."""
    raw, _ = frame(response, intent, context, now_ms)
    return position_quantities(raw).get(intent.grid.symbol, Decimal(0))


def position_quantities(raw):
    """Validate the complete native product projection; no account/HTTP authority."""
    if not isinstance(raw, list) or len(raw) > 1000:
        raise DemoRejected("invalid_positions")
    result = {}
    for row in raw:
        if not isinstance(row, dict):
            raise DemoRejected("invalid_positions")
        symbol = row.get("symbol")
        symbol = symbol.upper() if isinstance(symbol, str) and symbol.isascii() else None
        if not isinstance(symbol, str) or symbol not in SYMBOLS or symbol in result:
            raise DemoRejected("unsupported_or_duplicate_position")
        margin_coin = row.get("marginCoin")
        if (not isinstance(margin_coin, str) or not margin_coin.isascii()
                or margin_coin.upper() != "USDT"
                or row.get("holdSide") != "long" or row.get("marginMode") != "isolated"
                or row.get("posMode") != "one_way_mode"
                or amount(row.get("leverage")) != Decimal(2)):
            raise DemoRejected("unsupported_position_profile")
        total, available, locked = (amount(row.get(key)) for key in ("total", "available", "locked"))
        if any(value is None for value in (total, available, locked)):
            raise DemoRejected("incomplete_position")
        with localcontext() as ctx:
            ctx.prec = 160
            if total != available + locked:
                raise DemoRejected("position_quantity_mismatch")
        result[symbol] = total
    return result


def check_position(trace, response, *, context, now_ms):
    """Equality evidence only; never authorizes a new entry, recovery or net-PnL."""
    if not isinstance(trace, DemoTrace) or trace.observation is None:
        raise DemoRejected("missing_order_observation")
    _, at_ms = frame(response, trace.intent, context, now_ms)
    if at_ms < trace.observation.response_ms:
        raise DemoRejected("position_precedes_order")
    actual = position_quantity(response, trace.intent, context=context, now_ms=now_ms)
    with localcontext() as ctx:
        ctx.prec = 160
        expected = (trace.intent.before_quantity + trace.observation.quantity
                    if trace.intent.action == "open_long"
                    else trace.intent.before_quantity - trace.observation.quantity)
    number(expected, zero=True)
    if actual != expected:
        raise DemoRejected("position_reconciliation_required")
    return actual
