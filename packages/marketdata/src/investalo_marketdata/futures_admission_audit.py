"""Read-only reconstruction of the frozen native market entry pass.

No new entries, changed prices, rescue margin or counterfactual performance.
Only actual journal transitions advance state; rejected assessments are pure.
"""
from collections import Counter
from datetime import timedelta
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import stat

from investalo_trading.capital_digest import digest
from investalo_trading.futures_capital_journal import (
    MAX_FILE_BYTES, MAX_LINE_BYTES, _apply, _genesis,
)
from investalo_trading.futures_capital_research import CapitalReservedCashPlan
from investalo_trading.futures_ledger import LedgerMark
from investalo_trading.futures_capital_signals import (
    CapitalH1SignalProfile, _entry_signal, assess_capital_signal,
)
from investalo_trading.futures_replay_journal import _fields, _json, _sha
from investalo_trading.models import floor_step, precise
from investalo_trading.snapshot import primitive

D = Decimal
ZERO = D(0)
VERSION = "futures-capital-admission-audit/1"
MAX_REJECTIONS = 10_000


def audit_json(value):
    """Explicit UTF-8 bytes for create-only binary output; no implicit coercion."""
    return (json.dumps(value, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _read(path):
    fd = os.open(Path(path), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                or info.st_size > MAX_FILE_BYTES):
            raise ValueError("bounded owned private regular journal required")
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


@precise
def rejection_evidence(state, symbol, assessment, at, sequence, head):
    """Every value describes this actual attempt, never an authorized top-up."""
    plan = state.profile.plan
    i = plan.symbols.index(symbol)
    basket, request, budget = state.economic.ledger.baskets[i], assessment.request, plan.budgets[i]
    basis_margin = (basket.quantity * basket.average_entry
                    + request.quantity * request.maximum_fill_price) / request.requested_leverage
    mark_margin = (basket.quantity + request.quantity) * basket.mark / request.requested_leverage
    available = basket.isolated_balance + request.posted_margin
    regular = sum(plan.stage_capital(symbol)[:5], ZERO)
    return {key: primitive(value) for key, value in {
        "at": at, "after_sequence": sequence, "prior_head": head,
        "state_digest": state.state_digest, "symbol": symbol,
        "cycle": basket.cycle if basket.quantity else basket.cycle + 1,
        "stage": assessment.stage, "reasons": assessment.reasons,
        "trade_price": state.trade_prices[i].price, "mark_price": basket.mark,
        "maximum_fill_price": request.maximum_fill_price,
        "mark_above_bound": max(ZERO, basket.mark - request.maximum_fill_price),
        "mark_above_bound_bps": max(ZERO, basket.mark / request.maximum_fill_price - 1) * 10_000,
        "quantity": request.quantity, "own_entry_capital": request.posted_margin,
        "frozen_leverage": request.requested_leverage,
        "basis_initial_margin": basis_margin, "mark_initial_margin": mark_margin,
        "declared_initial_margin": assessment.required_initial_margin,
        "isolated_balance": basket.isolated_balance, "margin_committed": basket.margin_committed,
        "available_isolated_after_entry": available,
        "declared_margin_shortfall": (max(ZERO, assessment.required_initial_margin - available)
                                     if assessment.required_initial_margin is not None else None),
        "existing_unrealized_pnl": basket.quantity * (basket.mark - basket.average_entry),
        "funding_net": basket.funding_net, "cost_restored": basket.cost_restored,
        "wallet_cost_usage": plan.basket_cost_usage(basket), "wallet_cost_reserve": budget.cost_reserve,
        "restoration_capacity": plan.cost_restoration_capacity(basket),
        "unused_regular_capital": max(ZERO, regular - basket.margin_committed),
        "manual_capital": plan.stage_capital(symbol)[5],
        "account_unposted_cash": state.economic.ledger.unposted_cash,
        "account_cash_after_entry": (assessment.legacy_stress.unposted_cash_after
                                    if assessment.legacy_stress is not None else None),
        "execution_enabled": False,
    }.items()}


class EntryPass:
    """Follow the unchanged MarketReplay.enter order between actual commands."""
    def __init__(self):
        self.at = None
        self.index = 0
        self.restores = []
        self.rows = []
        self.accepted = 0
        self.passes = 0

    @precise
    def begin(self, state):
        if self.at is not None:
            raise ValueError("unfinished market entry pass")
        self.at, self.index = state.as_of, 0
        self.passes += 1
        self.restores = []
        for basket in state.economic.ledger.baskets:
            amount = floor_step(min(
                max(ZERO, basket.margin_committed - basket.isolated_balance),
                state.profile.plan.cost_restoration_capacity(basket)), state.profile.plan.quantum)
            if basket.quantity and amount > 0:
                self.restores.append((basket.symbol, str(amount)))

    @precise
    def before(self, state, command, sequence, head):
        args = command["arguments"] if command else {}
        kind = command["kind"] if command else None
        if self.at is None:
            if kind in ("entry", "leverage"):
                raise ValueError("market entry outside explicit execution pass")
            return
        if self.restores:
            symbol, amount = self.restores[0]
            expected = {
                "kind": "MarginPosting", "value": {
                    "symbol": symbol, "amount": amount, "cost_restoration": True}}
            if (kind != "economic" or args.get("payload") != expected
                    or command["at"] != self.at.isoformat()
                    or args.get("event_id") != f"market-restore-{state.revision}"):
                raise ValueError("missing or foreign own-cost restoration")
            self.restores.pop(0)
            return
        while self.index < len(state.profile.plan.symbols):
            symbol = state.profile.plan.symbols[self.index]
            maximum = state.trade_prices[self.index].price * (1 + state.profile.slippage)
            try:
                _entry_signal(state, symbol, maximum, self.at)
            except ValueError:
                self.index += 1
                continue
            basket = state.economic.ledger.baskets[self.index]
            cycle = basket.cycle if basket.quantity else basket.cycle + 1
            if not any((d.symbol, d.cycle) == (symbol, cycle) for d in state.economic.decisions):
                if (kind != "leverage" or args.get("symbol") != symbol
                        or command["at"] != self.at.isoformat()
                        or args.get("event_id") != f"market-leverage-{state.revision}"):
                    raise ValueError("missing frozen market leverage declaration")
                return
            assessment = assess_capital_signal(state, symbol, maximum, self.at).capital
            if not assessment.allowed:
                if len(self.rows) >= MAX_REJECTIONS:
                    raise ValueError("admission audit exceeds rejection bound")
                self.rows.append(rejection_evidence(state, symbol, assessment, self.at, sequence, head))
                self.index += 1
                continue
            if (kind != "entry" or args.get("assessment", {}).get("capital", {}).get(
                    "request", {}).get("symbol") != symbol
                    or command["at"] != self.at.isoformat()
                    or args.get("event_id") != f"market-entry-{state.revision}"):
                raise ValueError("missing allowed market entry; no hypothetical fill")
            self.accepted += 1
            self.index += 1
            return
        self.at = None
        if kind in ("entry", "leverage"):
            raise ValueError("extra market entry after completed pass")


def audit_admissions(path, *, profile_digest, protocol_digest, dataset_digests,
                     receipt, expected_rejections, progress=None):
    """Fold every actual input and verify the exact final acknowledged receipt."""
    _fields(receipt, ("schema_version", "context_digest", "sequence", "head",
                     "state_digest", "execution_enabled"))
    for name in ("head", "state_digest", "context_digest"):
        _sha(receipt[name])
    if (type(receipt["sequence"]) is not int or receipt["sequence"] < 0
            or receipt["execution_enabled"] is not False
            or type(expected_rejections) is not dict
            or any(type(k) is not str or type(v) is not int or v < 0
                   for k, v in expected_rejections.items())):
        raise ValueError("explicit nonexecuting receipt and counters required")
    entry_pass = EntryPass()
    with _read(path) as handle:
        header = _json(handle.readline(MAX_LINE_BYTES + 1))
        state = _genesis(header)
        if (type(state.profile) is not CapitalH1SignalProfile
                or type(state.profile.plan) is not CapitalReservedCashPlan
                or state.profile.profile_digest != profile_digest
                or header["protocol_digest"] != protocol_digest
                or header["dataset_digests"] != list(dataset_digests)):
            raise ValueError("frozen reserved-cash H1 journal required")
        head, sequence = digest((header["schema_version"], header)), 0
        last_open = None
        while line := handle.readline(MAX_LINE_BYTES + 1):
            record = _fields(_json(line), ("sequence", "prior_head", "prior_state_digest",
                                          "command", "state_digest", "head"))
            if (type(record["sequence"]) is not int or record["sequence"] != sequence + 1
                    or record["prior_head"] != head or record["prior_state_digest"] != state.state_digest
                    or sequence >= header["command_capacity"]):
                raise ValueError("admission audit journal prior binding mismatch")
            command = record["command"]
            _fields(command, ("kind", "revision", "at", "arguments"))
            entry_pass.before(state, command, sequence, head)
            candidate = _apply(state, command)
            expected = digest((header["schema_version"], head, command,
                               candidate.state_digest, sequence + 1))
            if record["state_digest"] != candidate.state_digest or record["head"] != expected:
                raise ValueError("admission audit replay or chain mismatch")
            args = command["arguments"]
            if command["kind"] == "prices":
                last_open = (candidate.as_of if args["event_id"] ==
                             f"market-open-{state.revision}" else None)
            if (command["kind"] == "economic"
                    and args["event_id"] == f"market-execution-mark-{state.revision}"):
                if (last_open is None or candidate.as_of != last_open + timedelta(seconds=1)
                        or args["payload"] != {"kind": "MarkBatch", "value": {"marks": primitive(tuple(
                            # Use the frozen same-price state, never substitute a new mark.
                            LedgerMark(b.symbol, b.mark)
                            for b in state.economic.ledger.baskets))}}):
                    raise ValueError("foreign market execution instant or marks")
                entry_pass.begin(candidate)
            state, head, sequence = candidate, expected, sequence + 1
            if progress and sequence % 10_000 == 0:
                progress(sequence, len(entry_pass.rows))
        entry_pass.before(state, None, sequence, head)
        final = {"schema_version": header["schema_version"], "context_digest": digest(header),
                 "sequence": sequence, "head": head, "state_digest": state.state_digest,
                 "execution_enabled": False}
        if final != receipt:
            raise ValueError("admission audit final receipt mismatch")
    counts = Counter(reason for row in entry_pass.rows for reason in row["reasons"])
    if dict(counts) != expected_rejections:
        raise ValueError("reconstructed admission counters differ from frozen market report")
    return {
        "schema_version": VERSION, "journal_receipt": final,
        "full_journal_restore_verified": True, "entry_passes": entry_pass.passes,
        "accepted_entries": entry_pass.accepted, "rejected_attempts": len(entry_pass.rows),
        "reason_counts": dict(sorted(counts.items())),
        "rejected_cycle_stages": len({(r["symbol"], r["cycle"], r["stage"]) for r in entry_pass.rows}),
        "rejections": entry_pass.rows, "execution_enabled": False,
        "counterfactual_performance_evaluated": False,
    }
