"""H1 entry coordination and actual-fill accounting; no network or order authority.

This reducer is separate from Paper simulation and the tiny BTC technical test.
Production must durably store each transition and bind its own strategy consent,
native order identity, credential and account checks before any submission.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal

from .allocation import identifier, revision
from .capital_digest import CapitalCanonical, digest
from .futures_capital_signals import (
    CapitalH1SignalProfile, CapitalSignalAssessment, CapitalSignalState,
    assess_capital_signal, declare_signal_leverage, observe_capital_prices,
    record_signal_broker_entry, replay_capital_hour,
)
from .futures_ledger import EntryFill, number, timestamp
from .identity_history import IdentityHistory
from .models import floor_step, precise

D = Decimal
VERSION = "h1-basket-broker-entry/1"
TERMINAL = ("filled", "canceled")


@dataclass(frozen=True)
class BrokerEntryOrder(CapitalCanonical):
    command_id: str
    assessment: CapitalSignalAssessment
    cycle: int
    before_quantity: Decimal
    before_average: Decimal
    prepared_at: datetime

    def __post_init__(self):
        identifier(self.command_id)
        revision(self.cycle)
        timestamp(self.prepared_at)
        number(self.before_quantity, nonnegative=True)
        number(self.before_average, nonnegative=True)
        if (type(self.assessment) is not CapitalSignalAssessment or not self.assessment.capital.allowed
                or not self.cycle or self.assessment.capital.request.requested_leverage != 2
                or not timedelta(0) <= self.prepared_at - self.assessment.signal_time <= timedelta(seconds=30)):
            raise ValueError("admitted fixed2x H1 order required")

    @property
    def request(self):
        return self.assessment.capital.request

    @property
    def order_digest(self):
        return digest((VERSION, self))


@dataclass(frozen=True)
class BrokerEntryObservation(CapitalCanonical):
    """Trusted cumulative evidence, after native identity/profile validation.

    posted_margin is a confirmed entry-specific capital debit, not the current
    position's total margin or a calculated cash attestation. Signed native fees
    are negative for charges. A positive rebate needs its own accounting policy.
    """
    order_digest: str
    state: str
    quantity: Decimal
    average_price: Decimal | None
    signed_fee: Decimal | None
    posted_margin: Decimal | None
    position_matches: bool
    observed_at: datetime
    evidence_digest: str

    def __post_init__(self):
        for value in (self.order_digest, self.evidence_digest):
            identifier(value)
        timestamp(self.observed_at)
        number(self.quantity, nonnegative=True)
        if self.average_price is not None:
            number(self.average_price, positive=True)
        if self.signed_fee is not None:
            number(self.signed_fee)
        if self.posted_margin is not None:
            number(self.posted_margin, nonnegative=True)
        if (self.state not in ("live", "partially_filled", *TERMINAL)
                or type(self.position_matches) is not bool
                or (self.quantity > 0) != (self.average_price is not None)
                or self.state == "live" and self.quantity != 0
                or self.state in ("partially_filled", "filled") and self.quantity <= 0):
            raise ValueError("consistent cumulative broker observation required")

    @property
    def reconcilable(self):
        return (self.state in TERMINAL and self.position_matches
                and self.signed_fee is not None and self.signed_fee <= 0
                and self.posted_margin is not None)


@dataclass(frozen=True)
class BrokerEntryBook(CapitalCanonical):
    signal: CapitalSignalState
    revision: int
    as_of: datetime
    commands: IdentityHistory
    pending: BrokerEntryOrder | None
    observation: BrokerEntryObservation | None
    notices: tuple[str, ...]
    audit_head: str

    def __post_init__(self):
        revision(self.revision)
        timestamp(self.as_of)
        identifier(self.audit_head)
        if (type(self.signal) is not CapitalSignalState
                or type(self.signal.profile) is not CapitalH1SignalProfile
                or self.as_of < self.signal.as_of
                or type(self.commands) is not IdentityHistory or self.commands.namespace != "order"
                or type(self.notices) is not tuple or any(type(n) is not str for n in self.notices)):
            raise ValueError("own H1 broker entry book required")
        if self.pending is not None:
            if (type(self.pending) is not BrokerEntryOrder or self.pending.command_id not in self.commands
                    or self.pending.assessment.profile_digest != self.signal.profile.profile_digest):
                raise ValueError("foreign or unregistered pending entry")
        if self.observation is not None and (
                self.pending is None or type(self.observation) is not BrokerEntryObservation
                or self.observation.order_digest != self.pending.order_digest
                or self.observation.observed_at > self.as_of):
            raise ValueError("observation needs its original pending entry")

    @property
    def state_digest(self):
        return digest((VERSION, self))

    @property
    def execution_enabled(self):
        return False


def start_broker_entries(signal):
    """Warm indicators may be retained; Paper fills/profits cannot be adopted."""
    if (type(signal) is not CapitalSignalState or type(signal.profile) is not CapitalH1SignalProfile
            or signal.economic.stages or signal.economic.stopped
            or signal.economic.ledger.closed_baskets
            or getattr(signal.profile.plan, "epochs", ())
            or any(b.quantity or b.margin_committed for b in signal.economic.ledger.baskets)):
        raise ValueError("flat own H1 genesis without simulated entries required")
    return BrokerEntryBook(signal, 0, signal.as_of, IdentityHistory("order"),
                           None, None, (), digest((VERSION, signal.state_digest)))


def _check(book, expected_revision, at):
    if type(book) is not BrokerEntryBook:
        raise ValueError("typed broker entry book required")
    revision(expected_revision)
    at = timestamp(at)
    if expected_revision != book.revision or at < book.as_of:
        raise ValueError("stale revision or backdated broker entry")
    return at


def _finish(book, at, body, **changes):
    candidate = replace(book, revision=book.revision + 1, as_of=at, **changes)
    return replace(candidate, audit_head=digest((VERSION, book.audit_head, body, candidate.state_digest)))


@precise
def prepare_broker_entry(book, symbol, planning_price, command_id, expected_revision, at):
    at = _check(book, expected_revision, at)
    identifier(command_id)
    if book.pending is not None:
        raise ValueError("reconcile the outstanding broker order before another entry")
    if command_id in book.commands:
        raise ValueError("broker command cannot be reused")
    signal = book.signal
    index = signal.profile.plan.symbols.index(symbol)
    basket = signal.economic.ledger.baskets[index]
    cycle = basket.cycle if basket.quantity else basket.cycle + 1
    decisions = tuple(d for d in signal.economic.decisions if (d.symbol, d.cycle) == (symbol, cycle))
    if not decisions:
        signal = declare_signal_leverage(
            signal, symbol, D(2), "fixed2x-demo-profile", "leverage-" + command_id,
            signal.revision, at)
    elif len(decisions) != 1 or decisions[0].leverage != 2:
        raise ValueError("basket leverage must remain fixed2x")
    assessment = assess_capital_signal(signal, symbol, planning_price, at)
    if not assessment.capital.allowed:
        raise ValueError("capital admission: " + ",".join(assessment.capital.reasons))
    request = assessment.capital.request
    contract = signal.profile.plan.contracts[index]
    full_quantity = floor_step(request.posted_margin * D(2) / planning_price, contract.quantity_step)
    if request.quantity != full_quantity:
        raise ValueError("native maximum requires separate order splitting; do not shrink a stage")
    order = BrokerEntryOrder(command_id, assessment, cycle, basket.quantity,
                             basket.average_entry, at)
    return _finish(book, at, ("prepare", order), signal=signal, pending=order,
                   observation=None, commands=book.commands.append(command_id))


@precise
def observe_broker_entry(book, observation, expected_revision, at):
    at = _check(book, expected_revision, at)
    order = book.pending
    if (order is None or type(observation) is not BrokerEntryObservation
            or observation.order_digest != order.order_digest
            or not order.prepared_at <= observation.observed_at <= at
            or at - observation.observed_at > timedelta(seconds=5)):
        raise ValueError("fresh observation of original pending order required")
    if (observation.quantity > order.request.quantity
            or observation.state == "filled" and observation.quantity != order.request.quantity
            or observation.state in ("partially_filled", "canceled")
            and observation.quantity >= order.request.quantity):
        raise ValueError("broker order size mismatch")
    previous = book.observation
    if previous is not None:
        if (observation.observed_at < previous.observed_at or observation.quantity < previous.quantity
                or previous.state in TERMINAL and observation.state != previous.state
                or observation.quantity == previous.quantity
                and observation.average_price != previous.average_price):
            raise ValueError("regressing or revised cumulative broker observation")
        if observation == previous:
            return book
    if not observation.reconcilable:
        return _finish(book, at, ("pending", observation), observation=observation)
    if observation.quantity == 0:
        if observation.signed_fee != 0 or observation.posted_margin != 0:
            raise ValueError("unfilled cancellation needs confirmed zero debit")
        return _finish(book, at, ("canceled-unfilled", order, observation),
                       pending=None, observation=None)
    signal = book.signal
    index = signal.profile.plan.symbols.index(order.request.symbol)
    basket = signal.economic.ledger.baskets[index]
    if (basket.quantity != order.before_quantity or basket.average_entry != order.before_average
            or signal.signals[index].cycle != order.cycle):
        raise ValueError("original basket changed while broker order was outstanding")
    fill = EntryFill(order.request.symbol, observation.quantity, observation.average_price,
                     observation.posted_margin, -observation.signed_fee, D(2))
    signal = record_signal_broker_entry(
        signal, order.assessment, fill, order.command_id, signal.revision, at)
    notices = []
    if observation.quantity < order.request.quantity:
        notices.append("terminal_partial_entry")
    if observation.average_price > order.request.maximum_fill_price:
        notices.append("market_fill_above_planning_price")
    if observation.posted_margin > order.request.posted_margin:
        notices.append("actual_stage_margin_overrun")
    return _finish(book, at, ("settled", order, observation), signal=signal,
                   pending=None, observation=None,
                   notices=tuple(dict.fromkeys((*book.notices, *notices))))


def replay_broker_hour(book, frame, expected_revision, at):
    at = _check(book, expected_revision, at)
    if book.pending is not None:
        raise ValueError("settle outstanding exposure before replaying H1 strategy")
    signal = replay_capital_hour(book.signal, frame, book.signal.revision, at)
    return _finish(book, at, ("hour", frame), signal=signal)


def cancel_broker_preparation(book, order_digest, expected_revision, at):
    """Discard an unsent preparation. The owning journal must exclude attempts."""
    at = _check(book, expected_revision, at)
    if (book.pending is None or book.pending.order_digest != order_digest
            or book.observation is not None):
        raise ValueError("original unobserved preparation required")
    return _finish(book, at, ("cancel-preparation", order_digest), pending=None)


def observe_broker_prices(book, trade, marks, event_id, expected_revision, at):
    """Fresh complete valuation may precede a delayed terminal reconciliation."""
    at = _check(book, expected_revision, at)
    signal = observe_capital_prices(book.signal, trade, marks, event_id, book.signal.revision, at)
    return _finish(book, at, ("prices", event_id, trade, marks), signal=signal)
