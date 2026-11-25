"""Native allocated-margin delta corroborated by full wallet/positions/bills.

An isolated position's aggregate margin alone is not a stage debit. This
adapter requires the original before-image, all other positions unchanged,
wallet occupied margin agreement and known cash fees in a complete time window.
Funding/adjustments/foreign activity remain unresolved, never entry principal.
"""
from decimal import Decimal, localcontext
import hashlib

from . import parse
from .futures_demo import DemoRejected, SYMBOLS, clock, number
from .futures_demo_basket import _frame, basket_position_match, BasketMarketIntent, BasketExitIntent
from .futures_demo_reconcile import OrderObservation, native_id, position_quantities
from investalo_trading.futures_broker_margin import BrokerMarginBaseline, BrokerMarginPosition
from investalo_trading.capital_digest import digest
from investalo_trading.models import precise
from .futures_demo_policy import ApprovedDemoStrategyPolicy

Q = Decimal(".00000001")
MONEY_TOLERANCE = 4 * Q
MAX_PAGES = 8


def _amount(raw, name, *, signed=False):
    value = parse.amount(raw.get(name), signed=signed)
    if value is None:
        raise DemoRejected("native_margin_field_unconfirmed")
    return value


@precise
def margin_snapshot(wallet_response, positions_response, intent, *, context, now_ms, policy=None):
    if policy is not None:
        if type(policy) is not ApprovedDemoStrategyPolicy:
            raise DemoRejected("own_approved_demo_strategy_policy_required")
        policy.check(intent.binding)
    wallet, wallet_ms = _frame(wallet_response, intent, context, now_ms)
    raw, positions_ms = _frame(positions_response, intent, context, now_ms)
    if (type(wallet) is not list or len(wallet) != 1 or type(wallet[0]) is not dict
            or wallet[0].get("marginCoin") != "USDT" or wallet[0].get("assetMode") != "single"):
        raise DemoRejected("single_usdt_margin_wallet_required")
    wallet = wallet[0]
    # Known zero collateral extras are required; no absence-as-zero defaults.
    for key in ("locked", "crossedMargin", "coupon", "grant"):
        if key == "grant" and policy is not None and parse.amount(wallet.get(key)) is None:
            continue
        if _amount(wallet, key) != 0:
            raise DemoRejected("native_margin_wallet_not_isolated_own_capital")
    equity = _amount(wallet, "accountEquity", signed=True)
    upl = _amount(wallet, "unrealizedPL", signed=True)
    occupied = _amount(wallet, "isolatedMargin")
    quantities = position_quantities(raw)
    positions = []
    for row in raw:
        symbol = row["symbol"].upper()
        margin = _amount(row, "marginSize")
        if not quantities[symbol]:
            if margin:
                raise DemoRejected("native_flat_position_still_has_margin")
            continue
        if row.get("assetMode") != "single" or row.get("autoMargin") != "off":
            raise DemoRejected("native_margin_position_profile_unconfirmed")
        if _amount(row, "openDelegateSize") != 0:
            raise DemoRejected("native_margin_position_has_pending_quantity")
        # Bitget explicitly documents empty totalFee as no funding charged yet.
        total_fee = Decimal(0) if row.get("totalFee") == "" else _amount(row, "totalFee", signed=True)
        positions.append(BrokerMarginPosition(symbol, quantities[symbol],
            _amount(row, "openPriceAvg"), margin, total_fee,
            _amount(row, "deductedFee"), _amount(row, "achievedProfits", signed=True)))
    positions = tuple(sorted(positions, key=lambda p: p.symbol))
    with localcontext() as precision:
        precision.prec = 36
        if abs(sum((p.allocated_margin for p in positions), Decimal(0)) - occupied) > MONEY_TOLERANCE:
            raise DemoRejected("native_wallet_and_position_margin_disagree")
    source = digest((intent.intent_digest, hashlib.sha256(wallet_response.body).hexdigest(),
                     hashlib.sha256(positions_response.body).hexdigest(), wallet_ms, positions_ms))
    return BrokerMarginBaseline(intent.order_digest, intent.intent_digest, source,
                               wallet_ms, positions_ms, equity, upl, occupied, positions)


@precise
def capture_margin_baseline(wallet_response, positions_response, intent, *,
                            context, now_ms, expected_positions, policy=None):
    baseline = margin_snapshot(wallet_response, positions_response, intent, context=context, now_ms=now_ms, policy=policy)
    if (type(expected_positions) is not tuple or not 3 <= len(expected_positions) <= 7
            or len({row[0] for row in expected_positions}) != len(expected_positions)):
        raise DemoRejected("own_complete_margin_position_baseline_required")
    expected = {}
    for symbol, quantity, average, tick in expected_positions:
        if symbol not in SYMBOLS:
            raise DemoRejected("foreign_margin_baseline_symbol")
        number(quantity, zero=True); number(average, zero=True); number(tick)
        expected[symbol] = quantity, average, tick
    if expected.get(intent.grid.symbol, ())[:2] != (intent.before_quantity, intent.before_average):
        raise DemoRejected("original_margin_position_mismatch")
    actual = {p.symbol: p for p in baseline.positions}
    if {s: row[0] for s, row in expected.items() if row[0]} != {s: p.quantity for s, p in actual.items()}:
        raise DemoRejected("foreign_margin_baseline_quantity")
    for symbol, p in actual.items():
        _, average, tick = expected[symbol]
        if abs(p.average_entry - average) > min(Decimal(1).scaleb(p.average_entry.as_tuple().exponent), tick):
            raise DemoRejected("foreign_margin_baseline_average")
    return baseline


def parse_bill_page(response, intent, *, context, now_ms, start_ms, end_ms, cursor=None):
    clock(start_ms); clock(end_ms)
    if not start_ms < end_ms or end_ms - start_ms > 30 * 86400000:
        raise DemoRejected("bounded_margin_bill_window_required")
    raw, at_ms = _frame(response, intent, context, now_ms)
    if (at_ms < end_ms or type(raw) is not dict or set(raw) != {"bills", "endId"}
            or type(raw["bills"]) is not list or len(raw["bills"]) > 100):
        raise DemoRejected("native_margin_bills_unconfirmed")
    rows, ids = [], set()
    for row in raw["bills"]:
        if type(row) is not dict:
            raise DemoRejected("native_margin_bill_required")
        key = native_id(row.get("billId"))
        if key in ids or cursor is not None and int(key) >= int(cursor):
            raise DemoRejected("native_margin_bill_cursor_not_monotonic")
        ids.add(key)
        created = parse.timestamp_ms(row.get("cTime"))
        if not start_ms <= created <= end_ms or row.get("coin") != "USDT":
            raise DemoRejected("native_margin_bill_outside_original_window")
        # No undocumented orderId is invented. Whole-product position and fee/
        # cash reconciliation below links this sole expected buy economically.
        rows.append(dict(id=key, symbol=row.get("symbol"), kind=row.get("businessType"),
                         amount=_amount(row, "amount", signed=True), fee=_amount(row, "fee", signed=True),
                         coupon_fee=parse.amount(row.get("feeByCoupon")), created_ms=created))
    end = raw["endId"]
    if not rows:
        if end not in (None, ""):
            raise DemoRejected("native_empty_bill_page_has_cursor")
        return tuple(rows), None, at_ms
    end = native_id(end)
    if int(end) != min(map(int, ids)):
        raise DemoRejected("native_margin_bill_cursor_mismatch")
    return tuple(rows), end, at_ms  # Even a short nonempty page must continue.


@precise
def _settlement_sources(baseline, wallet_response, positions_response, bill_pages, intent, observation, *,
                        context, now_ms, expected_positions, attempted_ms, policy=None):
    if (type(baseline) is not BrokerMarginBaseline
            or baseline.order_digest != intent.order_digest or baseline.intent_digest != intent.intent_digest
            or type(observation) is not OrderObservation or observation.intent_digest != intent.intent_digest
            or observation.quantity > intent.quantity
            or observation.state == "filled" and observation.quantity != intent.quantity
            or observation.state == "canceled" and observation.quantity == intent.quantity
            or not baseline.observed_ms <= clock(attempted_ms) <= observation.created_ms):
        raise DemoRejected("original_durable_margin_baseline_required")
    if observation.state not in ("filled", "canceled") or observation.reported_fee is None:
        return None
    if observation.reported_fee > 0:
        return None
    basket_position_match(positions_response, intent, observation, context=context,
                          now_ms=now_ms, expected_positions=expected_positions)
    after = margin_snapshot(wallet_response, positions_response, intent, context=context, now_ms=now_ms, policy=policy)
    if min(after.wallet_ms, after.positions_ms) < observation.response_ms:
        raise DemoRejected("margin_sources_precede_terminal_order")
    end_ms = after.observed_ms
    if type(bill_pages) is not tuple or not 1 <= len(bill_pages) <= MAX_PAGES:
        raise DemoRejected("complete_bounded_margin_bill_pages_required")
    bills, ids, cursor, hashes, last_at = [], set(), None, [], end_ms
    for index, response in enumerate(bill_pages):
        if index and cursor is None:
            raise DemoRejected("extra_margin_bill_page")
        rows, cursor, at_ms = parse_bill_page(response, intent, context=context, now_ms=now_ms,
            start_ms=baseline.start_ms, end_ms=end_ms, cursor=cursor)
        if at_ms < last_at:
            raise DemoRejected("native_margin_bill_clock_reversed")
        last_at = at_ms
        for row in rows:
            if row["id"] in ids:
                raise DemoRejected("duplicate_margin_bill_across_pages")
            ids.add(row["id"])
        bills.extend(rows)
        hashes.append(hashlib.sha256(response.body).hexdigest())
    if cursor is not None:
        return None  # Page count is not proof of completion.
    return after, bills, hashes, last_at


@precise
def reconcile_margin(baseline, wallet_response, positions_response, bill_pages, intent, observation, *,
                     context, now_ms, expected_positions, attempted_ms, policy=None):
    """Return (allocated margin, source digest, evidence time), or unknown."""
    if type(intent) is not BasketMarketIntent:
        raise DemoRejected("entry_margin_requires_own_buy_intent")
    sources = _settlement_sources(baseline, wallet_response, positions_response, bill_pages, intent, observation,
        context=context, now_ms=now_ms, expected_positions=expected_positions, attempted_ms=attempted_ms, policy=policy)
    if sources is None:
        return None
    after, bills, hashes, last_at = sources
    before_positions = {p.symbol: p for p in baseline.positions}
    after_positions = {p.symbol: p for p in after.positions}
    target = intent.grid.symbol
    if ({s: p for s, p in before_positions.items() if s != target} !=
            {s: p for s, p in after_positions.items() if s != target}):
        return None
    old, new = before_positions.get(target), after_positions.get(target)
    if observation.quantity == 0:
        if observation.reported_fee != 0 or bills or old != new:
            return None
        if (abs(after.collateral_without_upl - baseline.collateral_without_upl) > MONEY_TOLERANCE
                or abs(after.isolated_margin - baseline.isolated_margin) > MONEY_TOLERANCE):
            return None
        return Decimal(0), digest((baseline, after, hashes, observation)), last_at
    if new is None or not bills:
        return None
    old_funding = Decimal(0) if old is None else old.funding_total
    old_fees = Decimal(0) if old is None else old.deducted_fees
    old_realized = Decimal(0) if old is None else old.realized_pnl
    if new.funding_total != old_funding or new.realized_pnl != old_realized:
        return None
    if any(row["kind"] != "buy" or row["symbol"] != target or row["amount"] != 0
           or row["fee"] > 0 or row["coupon_fee"] not in (None, Decimal(0))
           or row["created_ms"] < observation.created_ms for row in bills):
        return None  # Includes funding, manual/auto margin, transfers and foreign activity.
    with localcontext() as precision:
        precision.prec = 36
        bill_fee = sum((row["fee"] for row in bills), Decimal(0))
        delta = new.allocated_margin - (Decimal(0) if old is None else old.allocated_margin)
        if (delta <= 0 or abs(bill_fee - observation.reported_fee) > Q
                or abs(new.deducted_fees - old_fees + bill_fee) > Q
                or abs(after.collateral_without_upl - baseline.collateral_without_upl - bill_fee) > MONEY_TOLERANCE
                or abs(after.isolated_margin - baseline.isolated_margin - delta) > MONEY_TOLERANCE):
            return None
        # Sanity only: the return value remains the native corroborated delta,
        # not this computed initial-margin estimate. Detect unaccounted top-ups.
        if abs(delta - observation.quantity * observation.average_price / 2) > MONEY_TOLERANCE:
            return None
    return delta, digest((baseline, after, hashes, observation)), last_at


@precise
def reconcile_exit(baseline, wallet_response, positions_response, bill_pages, intent, observation, *,
                   context, now_ms, expected_positions, attempted_ms, policy=None):
    """Corroborate released native margin AND native realized PnL, excluding UPL."""
    if type(intent) is not BasketExitIntent:
        raise DemoRejected("exit_settlement_requires_own_reduce_intent")
    sources = _settlement_sources(baseline, wallet_response, positions_response, bill_pages, intent, observation,
        context=context, now_ms=now_ms, expected_positions=expected_positions, attempted_ms=attempted_ms, policy=policy)
    if sources is None:
        return None
    after, bills, hashes, last_at = sources
    before_positions = {p.symbol: p for p in baseline.positions}
    after_positions = {p.symbol: p for p in after.positions}
    target = intent.grid.symbol
    if ({s: p for s, p in before_positions.items() if s != target} !=
            {s: p for s, p in after_positions.items() if s != target}):
        return None
    old, new = before_positions.get(target), after_positions.get(target)
    if old is None:
        return None
    if not observation.quantity:
        if (observation.reported_fee != 0 or bills or old != new
                or abs(after.collateral_without_upl - baseline.collateral_without_upl) > MONEY_TOLERANCE
                or abs(after.isolated_margin - baseline.isolated_margin) > MONEY_TOLERANCE):
            return None
        return Decimal(0), Decimal(0), digest((baseline, after, hashes, observation)), last_at
    if not bills or any(row["kind"] != "sell" or row["symbol"] != target or row["fee"] > 0
            or row["coupon_fee"] not in (None, Decimal(0))
            or row["created_ms"] < observation.created_ms for row in bills):
        return None
    bill_fee = sum((row["fee"] for row in bills), Decimal(0))
    pnl = sum((row["amount"] for row in bills), Decimal(0))
    remaining = Decimal(0) if new is None else new.allocated_margin
    released = old.allocated_margin - remaining
    if (released <= 0 or abs(bill_fee - observation.reported_fee) > Q
            or abs(after.collateral_without_upl - baseline.collateral_without_upl - pnl - bill_fee) > MONEY_TOLERANCE
            or abs(baseline.isolated_margin - after.isolated_margin - released) > MONEY_TOLERANCE
            or abs(pnl - observation.quantity * (observation.average_price - intent.before_average)) > MONEY_TOLERANCE
            or abs(released - old.allocated_margin * observation.quantity / old.quantity) > MONEY_TOLERANCE):
        return None
    if new is not None and (new.funding_total != old.funding_total
            or abs(new.deducted_fees - old.deducted_fees + bill_fee) > Q
            or abs(new.realized_pnl - old.realized_pnl - pnl) > MONEY_TOLERANCE):
        return None
    # Flat positions have no persistent per-position fee/PnL counters. The
    # complete sell bills plus whole-wallet cash and released-margin deltas
    # corroborate them instead; a computed PnL alone never confirms settlement.
    return released, pnl, digest((baseline, after, hashes, observation)), last_at
