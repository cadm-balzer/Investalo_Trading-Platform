"""Current public Classic metadata and offline grid arithmetic, never execution."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR, localcontext
import hashlib
from pathlib import Path
import re
from urllib.request import Request, build_opener

from .bitget import _NoRedirect
from .snapshot import canonical, decode_json, decimal_string, iso, price

VERSION = "bitget-classic-contract-calibration/1"
URL = "https://api.bitget.com/api/v2/mix/market/contracts?productType=USDT-FUTURES"
SYMBOLS = ("BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")
MAX_BYTES = 2 * 1024 * 1024


def places(value):
    if (not isinstance(value, str) or not value.isascii() or not value.isdigit()
            or len(value) > 2 or not 0 <= int(value) <= 12):
        raise ValueError("bounded decimal-place string required")
    return int(value)


def money(value, *, zero=False):
    if not isinstance(value, Decimal):
        raise ValueError("Decimal required")
    return price(str(value), zero=zero)


def floor_grid(value, step):
    """Exact multiples, independent of the caller's Decimal context."""
    money(value, zero=True)
    money(step)
    with localcontext() as context:
        context.prec = 160
        return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step


@dataclass(frozen=True)
class ContractRules:
    symbol: str
    status: str
    price_tick: Decimal
    quantity_step: Decimal
    min_quantity: Decimal
    min_notional: Decimal
    max_market_quantity: Decimal
    max_limit_quantity: Decimal
    maker_fee_rate: Decimal
    taker_fee_rate: Decimal
    opening_cost_up_ratio: Decimal
    fee_rate_up_ratio: Decimal
    min_leverage: Decimal
    max_leverage: Decimal

    def record(self):
        return {name: decimal_string(value) if isinstance(value, Decimal) else value
                for name, value in vars(self).items()}


def parse_contracts(payload):
    """Select all five research symbols; no defaults for missing broker fields."""
    response = decode_json(payload, max_bytes=MAX_BYTES)
    if (not isinstance(response, dict) or response.get("code") != "00000"
            or not isinstance(response.get("data"), list)
            or not 1 <= len(response["data"]) <= 2000):
        raise ValueError("successful bounded Classic contract response required")
    selected = {}
    for row in response["data"]:
        if not isinstance(row, dict):
            raise ValueError("contract object required")
        symbol = row.get("symbol")
        if not isinstance(symbol, str):
            raise ValueError("contract symbol required")
        if symbol not in SYMBOLS:
            continue
        if symbol in selected:
            raise ValueError("duplicate selected contract")
        selected[symbol] = row
    if set(selected) != set(SYMBOLS):
        raise ValueError("complete five-symbol cohort required")
    rules = []
    for symbol in SYMBOLS:
        row = selected[symbol]
        if (row.get("baseCoin") != symbol[:-4] or row.get("quoteCoin") != "USDT"
                or row.get("symbolType") != "perpetual"
                or row.get("supportMarginCoins") != ["USDT"]
                or not isinstance(row.get("symbolStatus"), str)
                or row["symbolStatus"] not in {
                    "listed", "normal", "maintain", "limit_open", "restrictedAPI", "off"}):
            raise ValueError("explicit Classic USDT perpetual identity/status required")
        try:
            with localcontext() as context:
                context.prec = 160
                quantity_unit = Decimal(1).scaleb(-places(row["volumePlace"]))
                price_unit = Decimal(1).scaleb(-places(row["pricePlace"]))
                end_step = price(row["priceEndStep"])
                step = price(row["sizeMultiplier"])
                minimum = price(row["minTradeNum"])
                if (end_step != end_step.to_integral_value() or end_step > 100
                        or step != floor_grid(step, quantity_unit)
                        or minimum != floor_grid(minimum, step)):
                    raise ValueError("inconsistent quantity/price grid")
                contract = ContractRules(
                    symbol, row["symbolStatus"], end_step * price_unit, step, minimum,
                    price(row["minTradeUSDT"]), price(row["maxMarketOrderQty"]),
                    price(row["maxOrderQty"]), price(row["makerFeeRate"], zero=True),
                    price(row["takerFeeRate"], zero=True),
                    price(row["openCostUpRatio"], zero=True),
                    price(row["feeRateUpRatio"], zero=True),
                    price(row["minLever"]), price(row["maxLever"]))
            if (contract.max_market_quantity < minimum or contract.max_limit_quantity < minimum
                    or max(contract.maker_fee_rate, contract.taker_fee_rate) > 1
                    or max(contract.opening_cost_up_ratio, contract.fee_rate_up_ratio) > 10
                    or not 1 <= contract.min_leverage <= contract.max_leverage <= 1000
                    or any(v != v.to_integral_value()
                           for v in (contract.min_leverage, contract.max_leverage))):
                raise ValueError("inconsistent contract bounds")
        except KeyError:
            raise ValueError("missing public contract field") from None
        rules.append(contract)
    return tuple(rules)


def bounded_limit_quantity(rules, *, notional_cap, limit_price):
    """Offline maximum grid quantity under a caller-supplied notional cap.

    This does not size margin, account for funding, or prove broker acceptance.
    Limits below the minimum return zero, without rounding budget/price upward.
    """
    if not isinstance(rules, ContractRules) or rules.status != "normal":
        raise ValueError("normally tradable calibrated contract required")
    money(notional_cap, zero=True)
    money(limit_price)
    if floor_grid(limit_price, rules.price_tick) != limit_price:
        raise ValueError("explicit on-grid limit price required")
    with localcontext() as context:
        context.prec = 160
        upper = min(notional_cap / limit_price, rules.max_limit_quantity)
        quantity = (upper / rules.quantity_step).to_integral_value(
            rounding=ROUND_FLOOR) * rules.quantity_step
        if quantity < rules.min_quantity or quantity * limit_price < rules.min_notional:
            return Decimal(0)
        return quantity


def classic_long_opening_loss(*, quantity, order_price, mark_price, margin_coin_index):
    """Documented Classic opening-loss component only; no full margin verdict."""
    for value in (order_price, mark_price, margin_coin_index):
        money(value)
    money(quantity, zero=True)
    with localcontext() as context:
        context.prec = 160
        return quantity * max(Decimal(0), order_price - mark_price) / margin_coin_index


def quantity_grid_probe(row, rules):
    """Static IP-083 quantity-only probe; never a replacement admission or fill.

    Keep old basis/mark/price assumptions and reduce ONLY the proposed quantity.
    Current metadata cannot prove historical order acceptance or changed profit.
    """
    if (not isinstance(row, dict) or not isinstance(rules, ContractRules)
            or row.get("symbol") != f"BINANCE:{rules.symbol}"
            or row.get("execution_enabled") is not False):
        raise ValueError("matching read-only native audit row required")
    def audited_amount(value):
        # Reducer-derived margins retain more decimal places than API prices.
        if (not isinstance(value, str) or len(value) > 96
                or not re.fullmatch(r"\d+(?:\.\d+)?(?:[eE][+-]?\d{1,2})?", value)):
            raise ValueError("bounded audit Decimal string required")
        result = Decimal(value)
        if (not 0 <= result <= Decimal("1e24")
                or len(result.as_tuple().digits) > 60
                or abs(result.as_tuple().exponent) > 60):
            raise ValueError("audit arithmetic outside supported bounds")
        return result
    try:
        quantity = price(row["quantity"])
        leverage = price(row["frozen_leverage"])
        basis = audited_amount(row["basis_initial_margin"])
        mark_margin = audited_amount(row["mark_initial_margin"])
        maximum = price(row["maximum_fill_price"])
        mark = price(row["mark_price"])
        available = audited_amount(row["available_isolated_after_entry"])
    except KeyError:
        raise ValueError("complete audit arithmetic required") from None
    rounded = floor_grid(quantity, rules.quantity_step)
    with localcontext() as context:
        context.prec = 160
        reduction = quantity - rounded
        adjusted_basis = basis - reduction * maximum / leverage
        adjusted_mark = mark_margin - reduction * mark / leverage
        if min(adjusted_basis, adjusted_mark) < 0:
            raise ValueError("audit margins inconsistent with proposed quantity")
        requirement = max(adjusted_basis, adjusted_mark)
        below_minimum = (rounded < rules.min_quantity or rounded * maximum < rules.min_notional)
        return {
            "symbol": row["symbol"], "source_quantity": decimal_string(quantity),
            "current_quantity_step": decimal_string(rules.quantity_step),
            "grid_quantity": decimal_string(rounded),
            "quantity_reduction": decimal_string(reduction),
            # Derived values can have more digits than the input price codec.
            "old_model_margin_after_quantity_floor": format(requirement, "f"),
            "old_model_margin_headroom_after_quantity_floor": format(available - requirement, "f"),
            "old_model_margin_covered": available >= requirement,
            "below_current_minimum": below_minimum,
            "price_grid_applied": False, "broker_admission_verified": False,
            "historical_rules_verified": False, "performance_evaluated": False,
            "execution_enabled": False,
        }


def fetch_contracts():
    """One unsigned fixed public GET, no redirects or automatic retry."""
    request = Request(URL, headers={"Accept": "application/json",
                                   "User-Agent": "Investalo-Research/1"}, method="GET")
    with build_opener(_NoRedirect()).open(request, timeout=20) as response:
        payload = response.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("public contract response too large")
    return payload


def capture_contracts(output: Path, *, fetch=fetch_contracts):
    """Create-only artifacts; failures keep their directory without success receipt."""
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    started = iso(datetime.now(timezone.utc))
    payload = fetch()
    if not isinstance(payload, bytes) or len(payload) > MAX_BYTES:
        raise ValueError("bounded raw response bytes required")
    raw_path = output / "contracts.raw.json"
    with raw_path.open("xb") as handle:
        handle.write(payload)
    saved = raw_path.read_bytes()
    if saved != payload:
        raise ValueError("public metadata write/readback mismatch")
    rules = parse_contracts(saved)
    decoded = decode_json(saved, max_bytes=MAX_BYTES)
    # Keep the original response envelope and five unmodified source rows.
    selected = {key: value for key, value in decoded.items() if key != "data"}
    selected["data"] = [row for symbol in SYMBOLS for row in decoded["data"]
                        if row["symbol"] == symbol]
    selected_bytes = (canonical(selected) + "\n").encode()
    selected_path = output / "contracts.selected.json"
    with selected_path.open("xb") as handle:
        handle.write(selected_bytes)
    if selected_path.read_bytes() != selected_bytes or parse_contracts(selected_bytes) != rules:
        raise ValueError("selected metadata roundtrip mismatch")
    receipt = {
        "schema_version": VERSION, "venue": "bitget", "account_family": "classic",
        "product": "USDT-FUTURES", "source_url": URL, "get_count": 1,
        "started_at": started, "finished_at": iso(datetime.now(timezone.utc)),
        "raw_file": raw_path.name, "raw_sha256": hashlib.sha256(saved).hexdigest(),
        "raw_bytes": len(saved), "selected_file": selected_path.name,
        "selected_sha256": hashlib.sha256(selected_bytes).hexdigest(),
        "rules": [rule.record() for rule in rules],
        "money_quantum": None, "money_rounding_mode": None,
        "historical_rules_verified": False, "account_fee_rate_verified": False,
        "maintenance_tiers_verified": False, "broker_admission_verified": False,
        "performance_evaluated": False, "execution_enabled": False,
    }
    receipt_bytes = (canonical(receipt) + "\n").encode()
    receipt_path = output / "receipt.json"
    with receipt_path.open("xb") as handle:
        handle.write(receipt_bytes)
    if receipt_path.read_bytes() != receipt_bytes:
        raise ValueError("receipt write/readback mismatch")
    return receipt
