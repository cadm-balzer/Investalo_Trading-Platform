"""Own current-price capacity projection; never an entry gate or allocation."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_CEILING

from .allocation import identifier, revision
from .futures_capacity import CapacityEvidence, recommend_capacity
from .futures_ledger import number, timestamp
from .futures_paper import FuturesPaperState, PaperQuote
from .futures_replay_journal import _sha
from .models import precise

D = Decimal
ZERO = D(0)


@dataclass(frozen=True)
class PaperInstrumentMinimum:
    symbol: str
    quantity_step: Decimal
    minimum_quantity: Decimal
    minimum_notional: Decimal
    price_tick: Decimal
    maximum_market_quantity: Decimal
    normal: bool
    supports_2x: bool

    def __post_init__(self):
        identifier(self.symbol)
        for value in (self.quantity_step, self.minimum_quantity, self.minimum_notional,
                      self.price_tick, self.maximum_market_quantity):
            number(value, positive=True)
        if type(self.normal) is not bool or type(self.supports_2x) is not bool:
            raise ValueError("explicit native instrument eligibility required")


@dataclass(frozen=True)
class PaperInstrumentEvidence:
    observed_at: datetime
    source_digest: str
    instruments: tuple[PaperInstrumentMinimum, ...]
    quotes: tuple[PaperQuote, ...]
    quoted_at: datetime

    def __post_init__(self):
        timestamp(self.observed_at)
        _sha(self.source_digest)
        if timestamp(self.quoted_at) > self.observed_at:
            raise ValueError("quotes must be known before native calibration")
        if (type(self.instruments) is not tuple or not 3 <= len(self.instruments) <= 7
                or any(type(r) is not PaperInstrumentMinimum for r in self.instruments)
                or tuple(r.symbol for r in self.instruments) != tuple(sorted(set(
                    r.symbol for r in self.instruments)))):
            raise ValueError("complete canonical native instrument evidence required")
        if (type(self.quotes) is not tuple
                or tuple(q.symbol for q in self.quotes if type(q) is PaperQuote) !=
                   tuple(r.symbol for r in self.instruments)):
            raise ValueError("complete own acknowledged quote cohort required")


@dataclass(frozen=True)
class PaperCapacityState:
    tenant_id: str
    account_id: str
    revision: int
    known_at: datetime
    indicator_at: datetime | None
    settings_revision: int
    configured_limit: int
    instrument_at: datetime | None
    instrument_digest: str | None
    evidence: CapacityEvidence | None
    blocked: bool

    def __post_init__(self):
        identifier(self.tenant_id)
        identifier(self.account_id)
        revision(self.revision)
        revision(self.settings_revision)
        timestamp(self.known_at)
        if self.indicator_at is not None:
            at = timestamp(self.indicator_at)
            if at > self.known_at or at.minute or at.second or at.microsecond:
                raise ValueError("own closed H1 capacity clock required")
        if type(self.configured_limit) is not int or not 3 <= self.configured_limit <= 7:
            raise ValueError("own configured capacity required")
        if type(self.blocked) is not bool:
            raise ValueError("explicit Paper blocker required")
        if self.evidence is None:
            if self.instrument_at is not None or self.instrument_digest is not None:
                raise ValueError("unverified capacity cannot advertise native evidence")
        elif (type(self.evidence) is not CapacityEvidence or self.instrument_at is None
              or timestamp(self.instrument_at) > self.known_at
              or self.evidence.observed_at > self.known_at):
            raise ValueError("acknowledged current capacity evidence required")
        else:
            _sha(self.instrument_digest)


@precise
def capacity_state(state: FuturesPaperState, instruments: PaperInstrumentEvidence | None):
    if type(state) is not FuturesPaperState:
        raise ValueError("own acknowledged Paper state required")
    plan, signal = state.config.profile.plan, state.signal
    ledger = signal.economic.ledger
    evidence = None
    if instruments is not None:
        if (type(instruments) is not PaperInstrumentEvidence
                or tuple(r.symbol for r in instruments.instruments) != plan.symbols
                or instruments.quoted_at != signal.trade_at
                or any(q.bid != price.price or q.mark != row.mark for q, price, row in zip(
                    instruments.quotes, signal.trade_prices, ledger.baskets, strict=True))):
            raise ValueError("native capacity evidence must match own complete candidate pool")
        stopped = {s.symbol: s for s in signal.economic.stopped}
        reserved, active = plan.remainder, 0
        for row, budget in zip(ledger.baskets, plan.budgets, strict=True):
            if row.symbol in stopped:
                reserved += stopped[row.symbol].unposted_stage_capital
            elif row.quantity:
                active += 1
                reserved += max(ZERO, budget.margin_capital - row.margin_committed)
            else:
                continue  # Empty candidates are not allocated ranges.
            reserved += max(ZERO, budget.cost_reserve - plan.basket_cost_usage(row))
            # Advisory conservative backing; never a new purchase admission gate.
            reserved += max(ZERO, row.margin_committed - row.isolated_balance)
        minima = []
        weights = sum((D("1.25") ** i for i in range(6)), ZERO)
        for i, native in enumerate(instruments.instruments):
            contract, grid, budget = plan.contracts[i], plan.grid_rules[i], plan.budgets[i]
            if (native.symbol in stopped or not native.normal or not native.supports_2x
                    or (native.quantity_step, native.minimum_quantity, native.minimum_notional,
                        native.price_tick, native.maximum_market_quantity) != (
                        contract.quantity_step, contract.minimum_quantity, contract.minimum_notional,
                        grid.price_tick, grid.maximum_market_quantity)):
                continue  # Changed grids cannot silently change the frozen execution profile.
            quote = instruments.quotes[i]
            maximum = plan.adverse_price(native.symbol, quote.ask * (1 + state.config.profile.slippage), buy=True)
            quantity = ((max(native.minimum_quantity, native.minimum_notional / maximum)
                         / native.quantity_step).to_integral_value(rounding=ROUND_CEILING)
                        * native.quantity_step)
            if quantity > native.maximum_market_quantity:
                continue
            quantum = plan.quantum
            first = ((quantity * max(maximum, quote.mark) / 2 / quantum)
                     .to_integral_value(rounding=ROUND_CEILING) * quantum)
            # Cover both principal and stage floor rounding at the current quote.
            minimum = (((first + quantum) * weights * budget.capital / budget.margin_capital
                        / quantum).to_integral_value(rounding=ROUND_CEILING) + 1) * quantum
            if budget.capital >= minimum:
                minima.append(minimum)
        evidence = CapacityEvidence(
            signal.trade_at, max(ZERO, ledger.unposted_cash), reserved, active,
            plan.initial_slots, max(minima, default=plan.budgets[0].capital),
            plan.budgets[0].capital, len(minima), plan.quantum,
        )
    return PaperCapacityState(
        plan.tenant_id, plan.account_id, state.revision,
        max(state.observed_at, instruments.observed_at) if instruments else state.observed_at,
        signal.last_hour.close_time if signal.last_hour else None,
        state.settings_revision, plan.configured_limit,
        instruments.observed_at if instruments else None,
        instruments.source_digest if instruments else None, evidence,
        bool(ledger.halted or signal.economic.liquidation_required or ledger.unposted_cash < 0),
    )


def capacity_snapshot(state, *, tenant_id, account_id, settings_revision, configured_limit,
                      now, account_ready=True):
    timestamp(now)
    if (type(state) is not PaperCapacityState
            or (state.tenant_id, state.account_id) != (tenant_id, account_id)
            or state.known_at > now):
        raise ValueError("own acknowledged capacity publication required")
    reason = None
    if not account_ready:
        reason = "account_unavailable"
    elif state.blocked:
        reason = "paper_runtime_blocked"
    elif (state.settings_revision, state.configured_limit) != (settings_revision, configured_limit):
        reason = "paper_settings_pending"
    elif state.evidence is None:
        reason = "instrument_data_unavailable"
    elif not 0 <= (now - state.instrument_at).total_seconds() <= 30:
        reason = "stale_instrument_data"
    elif state.indicator_at != now.replace(minute=0, second=0, microsecond=0):
        reason = "stale_futures_cash"
    result = recommend_capacity(state.evidence, configured_limit, now=now) if reason is None else None
    reason = reason or result.reason
    recommendation = result.recommended_limit if result else None
    evidence = state.evidence
    detail = None if evidence is None else {
        "observed_at": evidence.observed_at.isoformat(), "instrument_at": state.instrument_at.isoformat(),
        "unposted_cash": str(evidence.unposted_cash), "reserved_cash": str(evidence.reserved_unposted_cash),
        "free_cash": str(max(ZERO, evidence.unposted_cash - evidence.reserved_unposted_cash)),
        "range_budget": str(evidence.funded_range_budget), "minimum_range": str(evidence.minimum_full_range),
        "active_baskets": evidence.active_baskets, "funded_capacity": evidence.funded_capacity,
        "eligible_assets": evidence.eligible_assets,
        "additional_baskets": result.additional_baskets if result else 0,
    }
    return {"runtime_ready": recommendation is not None, "recommendation": recommendation,
            "recommendation_reason": reason, "capacity": detail}
