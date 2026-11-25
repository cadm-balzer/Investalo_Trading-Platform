"""Own Classic Demo basket Market packets; independent of the small BTC test."""
from dataclasses import dataclass, field
from decimal import Decimal, localcontext, ROUND_FLOOR
import hashlib
import json
from urllib.parse import urlencode
from uuid import UUID

from . import parse
from .futures_demo import DemoBinding, DemoRejected, SYMBOLS, PLACE_PATH, DETAIL_PATH, POSITIONS_PATH
from .futures_demo import clock, digest, number, text
from .futures_demo_reconcile import OrderObservation, native_id, position_quantities

VERSION = "bitget-classic-demo-basket-market/1"


@dataclass(frozen=True)
class BasketMarketGrid:
    symbol: str
    quantity_step: Decimal
    price_tick: Decimal
    min_quantity: Decimal
    min_notional: Decimal
    max_market_quantity: Decimal | None
    approved_policy_digest: str | None = None

    def __post_init__(self):
        if self.symbol not in SYMBOLS:
            raise DemoRejected("unsupported_basket_symbol")
        for value in (self.quantity_step, self.price_tick, self.min_quantity, self.min_notional):
            number(value)
        if self.approved_policy_digest is not None and (
                type(self.approved_policy_digest) is not str or len(self.approved_policy_digest) != 64
                or any(c not in "0123456789abcdef" for c in self.approved_policy_digest)):
            raise DemoRejected("invalid_approved_native_policy")
        if self.max_market_quantity is None:
            if self.approved_policy_digest is None:
                raise DemoRejected("unconfirmed_market_maximum_not_approved")
        else:
            number(self.max_market_quantity)
        if self.max_market_quantity is not None and self.max_market_quantity < self.min_quantity:
            raise DemoRejected("invalid_basket_native_maximum")

    def check(self, quantity, price):
        number(quantity); number(price)
        with localcontext() as precision:
            precision.prec = 160
            if (quantity % self.quantity_step or quantity < self.min_quantity
                    or self.max_market_quantity is not None and quantity > self.max_market_quantity
                    or quantity * price < self.min_notional):
                raise DemoRejected("basket_order_outside_native_grid")

    def record(self):
        return {key: text(value) if isinstance(value, Decimal) else value for key, value in vars(self).items()
                if key != "approved_policy_digest" or value is not None}


@dataclass(frozen=True, repr=False)
class BasketMarketIntent:
    binding: DemoBinding
    journal_id: UUID
    command_id: str
    order_digest: str
    grid: BasketMarketGrid
    stage: int
    cycle: int
    quantity: Decimal
    planning_price: Decimal
    planned_margin: Decimal
    before_quantity: Decimal
    before_average: Decimal
    prepared_ms: int
    client_oid: str = field(init=False)
    intent_digest: str = field(init=False)

    def __post_init__(self):
        if (type(self.binding) is not DemoBinding or type(self.journal_id) is not UUID
                or type(self.command_id) is not str or not 1 <= len(self.command_id) <= 128
                or self.command_id.strip() != self.command_id
                or type(self.grid) is not BasketMarketGrid or type(self.stage) is not int
                or not 1 <= self.stage <= 5 or type(self.cycle) is not int or self.cycle < 1
                or type(self.order_digest) is not str or len(self.order_digest) != 64
                or any(c not in "0123456789abcdef" for c in self.order_digest)):
            raise DemoRejected("invalid_basket_intent")
        clock(self.prepared_ms)
        self.grid.check(self.quantity, self.planning_price)
        number(self.planned_margin)
        number(self.before_quantity, zero=True); number(self.before_average, zero=True)
        if bool(self.before_quantity) != bool(self.before_average):
            raise DemoRejected("invalid_basket_original_position")
        with localcontext() as precision:
            precision.prec = 160
            desired = ((self.planned_margin * 2 / self.planning_price / self.grid.quantity_step)
                       .to_integral_value(rounding=ROUND_FLOOR) * self.grid.quantity_step)
            if self.quantity != desired:
                raise DemoRejected("basket_quantity_must_use_full_own_margin_times_leverage")
        key = dict(version=VERSION, binding=self.binding.record(),
                   journal=str(self.journal_id), command=self.command_id)
        object.__setattr__(self, "client_oid", "ivb" + digest(key)[:29])
        terms = dict(key, order=self.order_digest, grid=self.grid.record(), stage=self.stage, cycle=self.cycle,
                     quantity=text(self.quantity), planning_price=text(self.planning_price),
                     planned_margin=text(self.planned_margin), before_quantity=text(self.before_quantity),
                     before_average=text(self.before_average), prepared_ms=self.prepared_ms)
        object.__setattr__(self, "intent_digest", digest(terms))

    def __repr__(self):
        return "BasketMarketIntent(<private>)"


@dataclass(frozen=True, repr=False)
class BasketExitIntent:
    binding: DemoBinding
    journal_id: UUID
    command_id: str
    order_digest: str
    grid: BasketMarketGrid
    cycle: int
    quantity: Decimal
    planning_price: Decimal
    before_quantity: Decimal
    before_average: Decimal
    prepared_ms: int
    client_oid: str = field(init=False)
    intent_digest: str = field(init=False)

    def __post_init__(self):
        if (type(self.binding) is not DemoBinding or type(self.journal_id) is not UUID
                or type(self.command_id) is not str or not 1 <= len(self.command_id) <= 128
                or self.command_id.strip() != self.command_id
                or type(self.grid) is not BasketMarketGrid
                or type(self.cycle) is not int or self.cycle < 1
                or type(self.order_digest) is not str or len(self.order_digest) != 64
                or any(c not in "0123456789abcdef" for c in self.order_digest)):
            raise DemoRejected("invalid_basket_exit_intent")
        clock(self.prepared_ms)
        self.grid.check(self.quantity, self.planning_price)
        number(self.before_quantity); number(self.before_average)
        if self.quantity != self.before_quantity:
            raise DemoRejected("exit_must_use_exact_owned_long_quantity")
        key = dict(version="bitget-classic-demo-basket-exit/1", binding=self.binding.record(),
                   journal=str(self.journal_id), command=self.command_id)
        object.__setattr__(self, "client_oid", "ivx" + digest(key)[:29])
        terms = dict(key, order=self.order_digest, grid=self.grid.record(), cycle=self.cycle,
            quantity=text(self.quantity), planning_price=text(self.planning_price),
            before_quantity=text(self.before_quantity), before_average=text(self.before_average),
            prepared_ms=self.prepared_ms)
        object.__setattr__(self, "intent_digest", digest(terms))

    def __repr__(self):
        return "BasketExitIntent(<private>)"


@dataclass(frozen=True, repr=False)
class BasketFundingIntent:
    """Read-only original journal window; cannot be converted into an order."""
    binding: DemoBinding
    journal_id: UUID
    book_digest: str
    from_ms: int
    prepared_ms: int
    intent_digest: str = field(init=False)

    def __post_init__(self):
        if (type(self.binding) is not DemoBinding or type(self.journal_id) is not UUID
                or type(self.book_digest) is not str or len(self.book_digest) != 64
                or any(c not in "0123456789abcdef" for c in self.book_digest)
                or not clock(self.from_ms) <= clock(self.prepared_ms)
                or self.prepared_ms - self.from_ms > 30 * 86400000):
            raise DemoRejected("invalid_basket_funding_read_scope")
        object.__setattr__(self, "intent_digest", digest(dict(version="bitget-demo-basket-funding-read/1",
            binding=self.binding.record(), journal=str(self.journal_id), book=self.book_digest,
            from_ms=self.from_ms, prepared_ms=self.prepared_ms)))

    @property
    def order_digest(self):
        # Shared immutable snapshot codec binds this read to the original book.
        return self.book_digest

    def __repr__(self):
        return "BasketFundingIntent(<private>)"


@dataclass(frozen=True, repr=False)
class BasketRequestPlan:
    intent: BasketMarketIntent | BasketExitIntent | BasketFundingIntent
    operation: str
    start_ms: int | None = None
    end_ms: int | None = None
    cursor: str | None = None
    method: str = field(init=False)
    target: str = field(init=False)
    body: bytes = field(init=False)

    def __post_init__(self):
        if type(self.intent) not in (BasketMarketIntent, BasketExitIntent, BasketFundingIntent):
            raise DemoRejected("own_basket_intent_required")
        intent = self.intent
        if type(intent) is BasketFundingIntent and (
                self.operation not in ("wallet", "positions", "bills")
                or self.operation == "bills" and self.start_ms != intent.from_ms):
            raise DemoRejected("funding_scope_original_window_get_only")
        if self.operation != "bills" and any(v is not None for v in (self.start_ms, self.end_ms, self.cursor)):
            raise DemoRejected("unexpected_basket_window")
        if self.operation == "place":
            method, target = "POST", PLACE_PATH
            body = json.dumps(dict(symbol=intent.grid.symbol, productType="USDT-FUTURES",
                marginMode="isolated", marginCoin="USDT", size=text(intent.quantity),
                side="sell" if type(intent) is BasketExitIntent else "buy", orderType="market",
                reduceOnly="YES" if type(intent) is BasketExitIntent else "NO", clientOid=intent.client_oid),
                sort_keys=True, separators=(",", ":")).encode("ascii")
        elif self.operation == "detail":
            method, body = "GET", b""
            target = DETAIL_PATH + "?" + urlencode((
                ("symbol", intent.grid.symbol), ("productType", "USDT-FUTURES"),
                ("clientOid", intent.client_oid)))
        elif self.operation == "positions":
            method, body = "GET", b""
            target = POSITIONS_PATH + "?" + urlencode((
                ("productType", "USDT-FUTURES"), ("marginCoin", "USDT")))
        elif self.operation == "wallet":
            method, body = "GET", b""
            target = "/api/v2/mix/account/accounts?productType=USDT-FUTURES"
        elif self.operation == "bills":
            if (not clock(self.start_ms) < clock(self.end_ms)
                    or self.end_ms - self.start_ms > 30 * 86400000
                    or self.cursor is not None and native_id(self.cursor) != self.cursor):
                raise DemoRejected("bounded_original_basket_bill_window_required")
            method, body = "GET", b""
            query = [("productType", "USDT-FUTURES"), ("onlyFunding", "no"),
                     ("startTime", str(self.start_ms)), ("endTime", str(self.end_ms)), ("limit", "100")]
            if self.cursor is not None:
                query.append(("idLessThan", self.cursor))
            target = "/api/v2/mix/account/bill?" + urlencode(query)
        else:
            raise DemoRejected("unsupported_basket_operation")
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "body", body)

    @property
    def request_digest(self):
        return hashlib.sha256(self.method.encode() + b"\0" + self.target.encode()
                              + b"\0" + self.body).hexdigest()


def _frame(response, intent, context, now_ms):
    if type(intent) not in (BasketMarketIntent, BasketExitIntent, BasketFundingIntent):
        raise DemoRejected("own_basket_intent_required")
    intent.binding.check(context)
    clock(now_ms)
    raw, at = parse.envelope(response)
    elapsed = at - parse.EPOCH
    ms = elapsed.days * 86400000 + elapsed.seconds * 1000 + elapsed.microseconds // 1000
    if not 0 <= now_ms - ms <= 5000:
        raise DemoRejected("stale_basket_native_response")
    return raw, ms


def basket_ack(response, intent, *, context, now_ms):
    if type(intent) not in (BasketMarketIntent, BasketExitIntent):
        raise DemoRejected("funding_read_has_no_order_authority")
    raw, _ = _frame(response, intent, context, now_ms)
    if type(raw) is not dict or raw.get("clientOid") != intent.client_oid:
        raise DemoRejected("basket_ack_identity_mismatch")
    return native_id(raw.get("orderId"), optional=True)  # Never infer quantity/fill.


def basket_order_detail(response, intent, *, context, now_ms, attempted_ms):
    if type(intent) not in (BasketMarketIntent, BasketExitIntent):
        raise DemoRejected("funding_read_has_no_order_authority")
    raw, response_ms = _frame(response, intent, context, now_ms)
    clock(attempted_ms)
    if type(raw) is not dict:
        raise DemoRejected("invalid_basket_order_detail")
    expected = dict(symbol=intent.grid.symbol, clientOid=intent.client_oid, marginCoin="USDT",
                    marginMode="isolated", posMode="one_way_mode", orderType="market",
                    side="sell" if type(intent) is BasketExitIntent else "buy",
                    reduceOnly="YES" if type(intent) is BasketExitIntent else "NO")
    for key, value in expected.items():
        actual = raw.get(key)
        if key in ("symbol", "marginCoin", "reduceOnly") and type(actual) is str and actual.isascii():
            actual = actual.upper()
        if actual != value:
            raise DemoRejected("basket_order_identity_mismatch")
    if (raw.get("posSide") not in ("net", "long") or parse.amount(raw.get("leverage")) != Decimal(2)
            or parse.amount(raw.get("size")) != intent.quantity):
        raise DemoRejected("basket_order_terms_mismatch")
    state, quantity = raw.get("state"), parse.amount(raw.get("baseVolume"))
    average, fee = parse.amount(raw.get("priceAvg")), parse.amount(raw.get("fee"), signed=True)
    if (state not in ("live", "partially_filled", "filled", "canceled") or quantity is None
            or not 0 <= quantity <= intent.quantity
            or state == "live" and quantity != 0
            or state == "filled" and quantity != intent.quantity
            or state in ("partially_filled", "canceled") and quantity == intent.quantity
            or state == "partially_filled" and quantity <= 0):
        raise DemoRejected("invalid_basket_cumulative_fill")
    if not quantity:
        if average not in (None, Decimal(0)):
            raise DemoRejected("basket_average_without_fill")
        average = None
    elif average is None or average <= 0:
        raise DemoRejected("missing_basket_fill_average")
    created, updated = parse.timestamp_ms(raw.get("cTime")), parse.timestamp_ms(raw.get("uTime"))
    if not attempted_ms <= created <= updated <= response_ms:
        raise DemoRejected("invalid_basket_order_clock")
    return OrderObservation(intent.intent_digest, native_id(raw.get("orderId")),
                            state, quantity, average, fee, created, updated, response_ms)


def basket_position_match(response, intent, observation, *, context, now_ms, expected_positions):
    """Compare the complete product, including every other owned basket."""
    if type(intent) not in (BasketMarketIntent, BasketExitIntent):
        raise DemoRejected("funding_read_has_no_order_authority")
    raw, at_ms = _frame(response, intent, context, now_ms)
    if (type(observation) is not OrderObservation or observation.intent_digest != intent.intent_digest
            or type(expected_positions) is not tuple):
        raise DemoRejected("invalid_basket_position_evidence")
    if at_ms < observation.response_ms:
        raise DemoRejected("basket_position_precedes_order")
    quantities = position_quantities(raw)  # Same strict native Long/isolated/one-way/2x projection.
    expected = {symbol: (quantity, average) for symbol, quantity, average, tick in expected_positions}
    ticks = {symbol: tick for symbol, quantity, average, tick in expected_positions}
    for tick in ticks.values():
        number(tick)
    if len(expected) != len(expected_positions) or set(expected) - SYMBOLS or intent.grid.symbol not in expected:
        raise DemoRejected("invalid_basket_expected_positions")
    if expected[intent.grid.symbol] != (intent.before_quantity, intent.before_average):
        raise DemoRejected("basket_original_position_mismatch")
    with localcontext() as precision:
        precision.prec = 160
        if type(intent) is BasketExitIntent:
            total = intent.before_quantity - observation.quantity
            if total < 0:
                raise DemoRejected("exit_exceeds_original_long_position")
            average = intent.before_average if total else Decimal(0)
        else:
            total = intent.before_quantity + observation.quantity
            average = ((intent.before_quantity * intent.before_average
                        + observation.quantity * observation.average_price) / total
                       if observation.quantity else intent.before_average)
        expected[intent.grid.symbol] = total, average
        if {symbol: q for symbol, (q, _) in expected.items() if q} != {
                symbol: q for symbol, q in quantities.items() if q}:
            raise DemoRejected("basket_product_quantity_mismatch")
        for row in raw:
            symbol = row["symbol"].upper()
            if symbol not in expected:
                if quantities[symbol]:
                    raise DemoRejected("unowned_basket_product_position")
                continue
            quantity, average = expected[symbol]
            if quantity:
                reported = parse.amount(row.get("openPriceAvg"))
                if reported is None or reported <= 0:
                    raise DemoRejected("basket_product_average_mismatch")
                # Broker VWAP is a rounded decimal. Require overlap with one
                # unit of the native reported precision, not a price-percent tolerance.
                unit = min(Decimal(1).scaleb(reported.as_tuple().exponent), ticks[symbol])
                if abs(reported - average) > unit:
                    raise DemoRejected("basket_product_average_mismatch")
    return True
