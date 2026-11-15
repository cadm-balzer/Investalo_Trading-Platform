"""Offline Classic Demo request contracts; no signing, dispatch or authority."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, localcontext
import hashlib
import json
from urllib.parse import urlencode
from uuid import UUID

from .models import OwnerContext, uid

SYMBOLS = frozenset(("AVAXUSDT", "BNBUSDT", "BTCUSDT", "ETHUSDT",
                     "LINKUSDT", "SOLUSDT", "XRPUSDT"))
PLACE_PATH = "/api/v2/mix/order/place-order"
DETAIL_PATH = "/api/v2/mix/order/detail"
POSITIONS_PATH = "/api/v2/mix/position/all-position"
VERSION = "bitget-classic-futures-demo/1"


class DemoRejected(ValueError):
    """Static local errors only; no native message, credentials or raw body."""


def number(value, *, zero=False):
    if (not isinstance(value, Decimal) or not value.is_finite()
            or len(value.as_tuple().digits) > 48
            or abs(value.as_tuple().exponent) > 30
            or value > Decimal("1e30") or value < 0 or not zero and value == 0):
        raise DemoRejected("invalid_decimal")
    return value


def text(value):
    number(value, zero=True)
    if value == 0:
        return "0"
    raw = format(value, "f")
    return raw.rstrip("0").rstrip(".") if "." in raw else raw


def digest(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("ascii")).hexdigest()


def clock(value):
    if type(value) is not int or not 0 <= value < 10**15:
        raise DemoRejected("invalid_clock")
    return value


@dataclass(frozen=True, repr=False)
class DemoBinding:
    """Trusted executor declaration, NOT a verified credential/onboarding proof."""
    owner: OwnerContext
    account_id: UUID
    credential_ref: UUID
    broker_uid: str
    environment: str = "demo"
    api_family: str = "classic"
    position_mode: str = "one_way_mode"
    leverage: int = 2

    def __post_init__(self):
        if (not isinstance(self.owner, OwnerContext)
                or not isinstance(self.account_id, UUID)
                or not isinstance(self.credential_ref, UUID)):
            raise DemoRejected("invalid_binding")
        uid(self.broker_uid)
        if (self.environment != "demo" or self.api_family != "classic"
                or self.position_mode != "one_way_mode"
                or type(self.leverage) is not int or self.leverage != 2):
            raise DemoRejected("unsupported_profile")

    def check(self, context):
        if not isinstance(context, OwnerContext) or context != self.owner:
            raise DemoRejected("context_mismatch")

    def record(self):
        return {"tenant": str(self.owner.tenant_id), "user": str(self.owner.user_id),
                "account": str(self.account_id), "credential_ref": str(self.credential_ref),
                "broker_uid": self.broker_uid, "environment": self.environment,
                "api_family": self.api_family, "position_mode": self.position_mode,
                "leverage": self.leverage}

    def __repr__(self):
        return "DemoBinding(<private declaration>)"


@dataclass(frozen=True)
class DemoGrid:
    """Explicit current native contract projection, not broker acceptance proof."""
    symbol: str
    quantity_step: Decimal
    price_tick: Decimal
    min_quantity: Decimal
    min_notional: Decimal
    max_limit_quantity: Decimal

    def __post_init__(self):
        if not isinstance(self.symbol, str) or self.symbol not in SYMBOLS:
            raise DemoRejected("unsupported_symbol")
        for name in ("quantity_step", "price_tick", "min_quantity",
                     "min_notional", "max_limit_quantity"):
            number(getattr(self, name))
        if self.max_limit_quantity < self.min_quantity:
            raise DemoRejected("invalid_grid")

    def check(self, quantity, price):
        number(quantity)
        number(price)
        # Bounded exact arithmetic regardless of the caller's Decimal context.
        with localcontext() as ctx:
            ctx.prec = 160
            if (quantity % self.quantity_step or price % self.price_tick
                    or not self.min_quantity <= quantity <= self.max_limit_quantity
                    or quantity * price < self.min_notional):
                raise DemoRejected("order_outside_grid")

    def record(self):
        return {key: text(value) if isinstance(value, Decimal) else value
                for key, value in vars(self).items()}


@dataclass(frozen=True, repr=False)
class DemoIntent:
    """Exact base-coin size, fixed 2x account prerequisite; never USDT size."""
    binding: DemoBinding
    command_id: UUID
    grid: DemoGrid
    action: str
    quantity: Decimal
    limit_price: Decimal
    before_quantity: Decimal
    client_oid: str = field(init=False)
    intent_digest: str = field(init=False)

    def __post_init__(self):
        if (not isinstance(self.binding, DemoBinding)
                or not isinstance(self.command_id, UUID) or not isinstance(self.grid, DemoGrid)
                or self.action not in ("open_long", "reduce_long")):
            raise DemoRejected("invalid_intent")
        self.grid.check(self.quantity, self.limit_price)
        number(self.before_quantity, zero=True)
        if self.action == "reduce_long" and self.quantity > self.before_quantity:
            raise DemoRejected("close_exceeds_position")
        # Stable command key: changed payload MUST conflict in the future outbox.
        key = {"version": VERSION, "owner": str(self.binding.owner.tenant_id),
               "account": str(self.binding.account_id), "command": str(self.command_id)}
        object.__setattr__(self, "client_oid", "ivd" + digest(key)[:29])
        record = {"version": VERSION, "binding": self.binding.record(),
                  "command": str(self.command_id), "grid": self.grid.record(),
                  "action": self.action, "quantity": text(self.quantity),
                  "price": text(self.limit_price), "before": text(self.before_quantity)}
        object.__setattr__(self, "intent_digest", digest(record))

    def __repr__(self):
        return "DemoIntent(<private>)"


@dataclass(frozen=True, repr=False)
class DemoRequestPlan:
    """Unsigned exact bytes for review/persistence; intentionally no URL/transport."""
    intent: DemoIntent
    operation: str
    method: str = field(init=False)
    target: str = field(init=False)
    body: bytes = field(init=False)
    headers: tuple[tuple[str, str], ...] = field(init=False)

    def __post_init__(self):
        if not isinstance(self.intent, DemoIntent):
            raise DemoRejected("invalid_intent")
        intent = self.intent
        common = (("productType", "USDT-FUTURES"),)
        if self.operation == "place":
            method, target = "POST", PLACE_PATH
            body = json.dumps({
                "symbol": intent.grid.symbol, "productType": "USDT-FUTURES",
                "marginMode": "isolated", "marginCoin": "USDT",
                "size": text(intent.quantity), "price": text(intent.limit_price),
                "side": "buy" if intent.action == "open_long" else "sell",
                "orderType": "limit", "force": "ioc", "clientOid": intent.client_oid,
                "reduceOnly": "NO" if intent.action == "open_long" else "YES",
            }, sort_keys=True, separators=(",", ":")).encode("ascii")
        elif self.operation == "detail":
            method = "GET"
            target = DETAIL_PATH + "?" + urlencode(
                (("symbol", intent.grid.symbol),) + common + (("clientOid", intent.client_oid),))
            body = b""
        elif self.operation == "positions":
            method, body = "GET", b""
            target = POSITIONS_PATH + "?" + urlencode(common + (("marginCoin", "USDT"),))
        else:
            raise DemoRejected("unsupported_operation")
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "body", body)
        object.__setattr__(self, "headers", (("paptrading", "1"),
                                           ("Content-Type", "application/json")))

    def __repr__(self):
        return "DemoRequestPlan(<unsigned private>)"


def request_plan(intent, operation, *, context):
    if not isinstance(intent, DemoIntent):
        raise DemoRejected("invalid_intent")
    intent.binding.check(context)
    return DemoRequestPlan(intent, operation)
