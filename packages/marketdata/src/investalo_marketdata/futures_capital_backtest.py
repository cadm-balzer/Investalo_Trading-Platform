"""Declared native-history market replay; no broker, AI or holdout access."""
from collections import Counter
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from investalo_trading.futures_capital_journal import CapitalReplayJournal
from investalo_trading.futures_capital_research import CapitalCashPlan, CapitalRealizedCashPlan, CapitalReservedCashPlan
from investalo_trading.futures_capital_grid import CapitalGridPlan
from investalo_trading.futures_capital_signals import CapitalHour, assess_capital_signal, _entry_signal
from investalo_trading.futures_ledger import LedgerMark, LiquidationSettlement, MarginPosting, MarkBatch
from investalo_trading.models import floor_step, precise
from investalo_trading.snapshot import digest, primitive

from .futures_research_profile import boundary_valuation, declared_exit, funding_batch, funding_reference
from .snapshot import canonical, iso

VERSION = "futures-capital-market-backtest/1"
D = Decimal
ZERO = D(0)


def validate_cohort(streams):
    """Complete native research axis before any economic output is created."""
    symbols = tuple(sorted(s for s, kind in streams if kind == "trade"))
    if (len(symbols) != 5 or set(streams) != {(s, k) for s in symbols for k in ("trade", "mark", "funding")}):
        raise ValueError("five complete native streams required")
    anchor = streams[symbols[0], "trade"]
    axis = tuple(r.open_time for r in anchor.rows)
    for (symbol, kind), stream in streams.items():
        if (stream.symbol != symbol or stream.kind != kind
                or stream.start != anchor.start or stream.end != anchor.end):
            raise ValueError("different source cohort window")
        if kind != "funding" and tuple(r.open_time for r in stream.rows) != axis:
            raise ValueError("different native price axis")
        if kind == "funding" and any(r.timestamp.minute or r.timestamp.second
                                   or r.timestamp.microsecond >= 1_000_000 for r in stream.rows):
            raise ValueError("unsupported native funding placement")
    return symbols, anchor


class MarketReplay:
    """One scenario, full acknowledged journal and event-level economic metrics."""
    def __init__(self, journal, scenario, curve):
        self.journal, self.scenario, self.curve = journal, scenario, curve
        self.closed = []
        self.blocked = Counter()
        self.signal_filters = Counter()
        self.entry_candidates = 0
        self.stage_counts = Counter()
        self.warning_hours = Counter()
        self.fees = ZERO
        self.funding = ZERO
        self.insurance = ZERO
        self.restored = ZERO
        self.peak = journal.state.economic.ledger.equity
        self.maximum_drawdown = ZERO
        self.maximum_margin = ZERO
        self.maximum_active = 0
        self.margin_seconds = ZERO
        self.last_at = journal.state.as_of
        self.last_margin = ZERO
        self.event_minimum = self.peak
        self.event_maximum = self.peak
        self.sample()

    @property
    def state(self):
        return self.journal.state

    def append(self, kind, at, **arguments):
        self.journal.append(kind, expected_revision=self.state.revision, at=at, **arguments)
        self.sample()

    @precise
    def sample(self):
        ledger = self.state.economic.ledger
        equity = ledger.equity
        self.peak = max(self.peak, equity)
        self.maximum_drawdown = max(self.maximum_drawdown, (self.peak - equity) / self.peak)
        self.event_minimum = min(self.event_minimum, equity)
        self.event_maximum = max(self.event_maximum, equity)
        margin = sum((b.margin_committed for b in ledger.baskets), ZERO)
        self.margin_seconds += self.last_margin * D(str((self.state.as_of - self.last_at).total_seconds()))
        self.last_at, self.last_margin = self.state.as_of, margin
        self.maximum_margin = max(self.maximum_margin, margin)
        self.maximum_active = max(self.maximum_active, sum(bool(b.quantity) for b in ledger.baskets))

    def event_id(self, kind):
        return f"market-{kind}-{self.state.revision}"

    @precise
    def settle(self, at, unsafe=None):
        # Liquidations first: no new price, restoration or buy can cure an obligation.
        ordered = sorted(self.state.profile.plan.symbols, key=lambda s: (
            "liquidation_settlement_required" not in
            self.state.signals[self.state.profile.plan.symbols.index(s)].exit_reasons, s))
        for symbol in ordered:
            index = self.state.profile.plan.symbols.index(symbol)
            b, signal = self.state.economic.ledger.baskets[index], self.state.signals[index]
            if not b.quantity or not signal.exit_reasons:
                continue
            original = unsafe if unsafe is not None and symbol in unsafe.economic.liquidation_required else None
            payload = declared_exit(self.state, symbol, self.scenario, unsafe_state=original)
            credit = payload.insurance_credit if type(payload) is LiquidationSettlement else ZERO
            pnl = b.realized_price_pnl + b.quantity * (payload.price - b.average_entry)
            net = pnl - b.entry_fees - b.exit_fees - payload.fee + b.funding_net + credit
            stages = sum(r.symbol == symbol and r.cycle == b.cycle for r in self.state.economic.stages)
            self.closed.append({
                "symbol": symbol, "cycle": b.cycle, "opened_at": iso(b.opened_at),
                "closed_at": iso(at), "stages": stages, "leverage": str(b.broker_leverage),
                "reasons": list(signal.exit_reasons), "liquidated": type(payload) is LiquidationSettlement,
                "price_pnl": str(pnl), "fees": str(b.entry_fees + b.exit_fees + payload.fee),
                "funding_net": str(b.funding_net), "insurance_credit": str(credit), "net_pnl": str(net),
                "closing_cost_usage": str(self.state.profile.plan.basket_cost_usage(
                    replace(b, exit_fees=b.exit_fees + payload.fee,
                            charges_in_budget_epoch=b.charges_in_budget_epoch + payload.fee))),
                "cost_reserve": str(self.state.profile.plan.budgets[index].cost_reserve),
            })
            self.append("economic", at, payload=payload, event_id=self.event_id("exit"))
            self.fees += payload.fee
            self.insurance += credit

    @precise
    def restoration_amount(self, b, budget):
        plan = self.state.profile.plan
        if isinstance(plan, CapitalReservedCashPlan):
            capacity = plan.cost_restoration_capacity(b)
        else:
            usage = plan.basket_cost_usage(b)
            if type(plan) in (CapitalCashPlan, CapitalRealizedCashPlan):
                usage = b.entry_fees + b.exit_fees + b.cost_restored
            capacity = max(ZERO, budget.cost_reserve - usage)
        return floor_step(min(max(ZERO, b.margin_committed - b.isolated_balance), capacity),
                          plan.quantum)

    @precise
    def restore_costs(self, at):
        for b, budget in zip(self.state.economic.ledger.baskets, self.state.profile.plan.budgets, strict=True):
            if not b.quantity:
                continue
            amount = self.restoration_amount(b, budget)
            if amount > 0:
                self.append("economic", at, payload=MarginPosting(b.symbol, amount, True),
                            event_id=self.event_id("restore"))
                self.restored += amount

    @precise
    def enter(self, at):
        for i, symbol in enumerate(self.state.profile.plan.symbols):
            maximum = self.state.trade_prices[i].price * (1 + self.scenario.costs.slippage)
            if type(self.state.profile.plan) is CapitalGridPlan:
                maximum = self.state.profile.plan.adverse_price(symbol, maximum, buy=True)
            try:
                _entry_signal(self.state, symbol, maximum, at)
            except ValueError:
                continue  # No strategy signal is not a capital rejection.
            b = self.state.economic.ledger.baskets[i]
            cycle = b.cycle if b.quantity else b.cycle + 1
            if not any(d.symbol == symbol and d.cycle == cycle for d in self.state.economic.decisions):
                self.append("leverage", at, symbol=symbol, leverage=self.scenario.leverage,
                            evidence_digest=self.scenario.assumptions_digest,
                            event_id=self.event_id("leverage"))
            assessment = assess_capital_signal(self.state, symbol, maximum, at)
            if not assessment.capital.allowed:
                self.blocked.update(assessment.capital.reasons)
                continue
            self.append("entry", at, assessment=assessment, price=maximum, event_id=self.event_id("entry"))
            self.stage_counts[str(assessment.capital.stage)] += 1
            contract = self.state.profile.plan.contracts[i]
            self.fees += assessment.capital.request.quantity * maximum * contract.entry_fee_rate

    @precise
    def funding_group(self, references, at, *, already_valued=False, unsafe=None):
        if not already_valued:
            prices = {r.symbol: r.mark for r in references}
            marks = tuple(LedgerMark(b.symbol, prices.get(b.symbol, b.mark))
                          for b in self.state.economic.ledger.baskets)
            self.append("economic", at, payload=MarkBatch(marks), event_id=self.event_id("fund-mark"))
            unsafe = self.state
        batch = funding_batch(references, self.state.profile, at)
        payment = sum((-self.state.economic.ledger.baskets[
            self.state.profile.plan.symbols.index(r.symbol)].quantity * r.mark * r.applied_rate
                       for r in references), ZERO)
        self.append("funding_batch", at, batch=batch, event_id=self.event_id("funding"))
        self.funding += payment
        self.settle(at, unsafe)

    def prices(self, bars, field, at, *, entries=False):
        trade, mark = bars
        symbols = self.state.profile.plan.symbols
        self.append("prices", at, trade=tuple(LedgerMark(s, getattr(b, field)) for s, b in zip(symbols, trade)),
                    mark=tuple(LedgerMark(s, getattr(b, field)) for s, b in zip(symbols, mark)),
                    event_id=self.event_id(field))
        self.settle(at)
        if entries:
            # Separate execution instant, using the same still-fresh observed open.
            # This permits exits5 before another basket's restoration3 / entry4.
            execution_at = at + timedelta(seconds=1)
            eligible = False
            for i, symbol in enumerate(symbols):
                try:
                    _entry_signal(self.state, symbol,
                                  self.state.trade_prices[i].price * (1 + self.scenario.costs.slippage),
                                  execution_at)
                    eligible = True
                except ValueError:
                    pass
            if isinstance(self.state.profile.plan, CapitalReservedCashPlan):
                restoration = any(b.quantity and self.restoration_amount(b, budget) > 0
                    for b, budget in zip(self.state.economic.ledger.baskets, self.state.profile.plan.budgets))
            else:
                # Frozen historical trigger retained in the earlier variants.
                restoration = any(b.quantity and floor_step(
                    min(max(ZERO, b.margin_committed - b.isolated_balance),
                        max(ZERO, budget.cost_reserve - b.charges_in_budget_epoch)),
                    self.state.profile.plan.quantum) > 0
                    for b, budget in zip(self.state.economic.ledger.baskets, self.state.profile.plan.budgets))
            if not eligible and not restoration:
                return
            # All fills share a complete same-time valuation, including later symbols.
            self.append("economic", execution_at, payload=MarkBatch(tuple(
                LedgerMark(b.symbol, b.mark) for b in self.state.economic.ledger.baskets)),
                        event_id=self.event_id("execution-mark"))
            self.restore_costs(execution_at)
            self.enter(execution_at)
            self.settle(execution_at)

    def curve_point(self):
        ledger = self.state.economic.ledger
        self.curve.write(canonical({
            "at": iso(self.state.as_of), "equity": str(ledger.equity),
            "event_minimum_equity": str(self.event_minimum), "event_maximum_equity": str(self.event_maximum),
            "unposted_cash": str(ledger.unposted_cash), "realized_net_pnl": str(ledger.realized_net_pnl),
            "posted_margin": str(self.last_margin),
            "active_baskets": sum(bool(b.quantity) for b in ledger.baskets),
        }) + "\n")
        self.event_minimum = self.event_maximum = ledger.equity
        self.warning_hours.update(self.state.economic.warnings)

    @precise
    def report(self, start, end):
        ledger = self.state.economic.ledger
        initial = ledger.plan.initial_equity
        winners = sum((D(r["net_pnl"]) for r in self.closed if D(r["net_pnl"]) > 0), ZERO)
        losses = -sum((D(r["net_pnl"]) for r in self.closed if D(r["net_pnl"]) < 0), ZERO)
        closed_net = sum((D(r["net_pnl"]) for r in self.closed), ZERO)
        if abs(closed_net - ledger.realized_net_pnl) > ledger.plan.quantum:
            raise ValueError("closed receipt net does not reconcile with ledger")
        open_net = sum((b.quantity * (b.mark - b.average_entry) - b.entry_fees - b.exit_fees
                        + b.funding_net + b.realized_price_pnl for b in ledger.baskets), ZERO)
        net = ledger.equity - initial
        residual = net - closed_net - open_net
        if abs(residual) > ledger.plan.quantum:
            raise ValueError("end MTM and realized net do not reconcile")
        seconds = D(str((end - start).total_seconds()))
        return {
            "scenario_id": self.scenario.scenario_id, "assumptions_digest": self.scenario.assumptions_digest,
            "profile_digest": self.state.profile.profile_digest, "initial_equity": str(initial),
            "final_equity": str(ledger.equity), "net_pnl": str(net),
            "net_return_pct": str(net / initial * 100), "maximum_event_drawdown_pct": str(self.maximum_drawdown * 100),
            "closed_baskets": len(self.closed), "winning_baskets": sum(D(r["net_pnl"]) > 0 for r in self.closed),
            "losing_baskets": sum(D(r["net_pnl"]) < 0 for r in self.closed),
            "profit_factor": str(winners / losses) if losses else None,
            "profit_factor_no_losses": not bool(losses), "realized_net_pnl": str(closed_net),
            "open_net_pnl": str(open_net), "fees": str(self.fees), "funding_net": str(self.funding),
            "decimal_reconciliation_residual": str(residual),
            "declared_insurance_credit": str(self.insurance), "cost_restoration": str(self.restored),
            "stage_fill_counts": dict(sorted(self.stage_counts.items())), "capital_rejections": dict(self.blocked),
            "eligible_closed_h4_candidates": self.entry_candidates,
            "closed_h4_signal_filters": dict(self.signal_filters),
            "closed_exit_reasons": dict(Counter(r for b in self.closed for r in b["reasons"])),
            "account_warning_hours": dict(self.warning_hours), "maximum_posted_margin": str(self.maximum_margin),
            "time_weighted_posted_margin": str(self.margin_seconds / seconds),
            "maximum_active_baskets": self.maximum_active,
            "liquidations": sum(r["liquidated"] for r in self.closed),
            "unused_liquidated_stage_capital": str(sum(
                (r.unposted_stage_capital for r in self.state.economic.stopped), ZERO)),
            "end_open_baskets": [primitive(b) for b in ledger.baskets if b.quantity],
            "final_halt_reasons": list(ledger.halt_reasons), "journal_receipt": self.journal.receipt,
            "retained_event_ids": len(self.state.economic.event_ids), "execution_enabled": False,
        }


def run_scenario(streams, scenario, output, protocol_digest, dataset_digests, *,
                 progress=None, full_flat_quotes=False, cash_budget_protocol=None, entry_hours=4,
                 realized_exit_costs=False, reserved_cash=False, current_grids=False,
                 grid_leverage_comparison=False):
    symbols, anchor = validate_cohort(streams)
    output.mkdir(mode=0o700, exist_ok=False)
    if cash_budget_protocol is not None:
        if cash_budget_protocol != protocol_digest:
            raise ValueError("cash budget protocol must bind the journal")
    # Funding references bind unchanged economics; the plan discriminator and
    # journal protocol bind corrected cash semantics.
    profile = scenario.profile(cash_budgets=cash_budget_protocol is not None, entry_hours=entry_hours,
                               realized_exit_costs=realized_exit_costs, reserved_cash=reserved_cash,
                               current_grids=current_grids,
                               grid_leverage_comparison=grid_leverage_comparison)
    references = {}
    for symbol in symbols:
        stream = streams[symbol, "funding"]
        source_digest = stream.data_digest
        marks = streams[symbol, "mark"].rows
        for row in stream.rows:
            i = (row.timestamp - anchor.start) // timedelta(hours=1)
            ref = funding_reference(symbol, row, marks[i], source_digest, scenario)
            references.setdefault(ref.timestamp, []).append(ref)
    references = {at: tuple(sorted(rows, key=lambda r: r.symbol)) for at, rows in references.items()}
    opening_groups = {}
    for at in sorted(references):
        opened = at.replace(minute=0, second=0, microsecond=0)
        opening_groups.setdefault(opened, []).append(at)
    initial_trade = tuple(LedgerMark(f"BINANCE:{s}", streams[s, "trade"].rows[0].open) for s in symbols)
    initial_mark = tuple(LedgerMark(f"BINANCE:{s}", streams[s, "mark"].rows[0].open) for s in symbols)
    path = output / "journal.jsonl"
    with CapitalReplayJournal.create(
            path, profile, initial_trade, initial_mark, anchor.start, digest((VERSION, dataset_digests)),
            protocol_digest=protocol_digest, dataset_digests=dataset_digests) as journal, \
            (output / "equity.jsonl").open("x") as curve:
        replay = MarketReplay(journal, scenario, curve)
        replay.curve_point()
        for i in range(len(anchor.rows)):
            trade = tuple(streams[s, "trade"].rows[i] for s in symbols)
            mark = tuple(streams[s, "mark"].rows[i] for s in symbols)
            opened = trade[0].open_time
            for at in opening_groups.get(opened, ()):
                # Exact boundary group was processed by preceding hour; genesis is flat.
                if at == opened and i:
                    continue
                replay.funding_group(references[at], at)
            needs_open = full_flat_quotes or any(b.quantity for b in replay.state.economic.ledger.baskets)
            for j, symbol in enumerate(profile.plan.symbols):
                try:
                    _entry_signal(replay.state, symbol, trade[j].open * (1 + scenario.costs.slippage),
                                  opened + timedelta(seconds=2))
                    needs_open = True
                    if replay.state.last_entry_at == opened:
                        replay.entry_candidates += 1
                except ValueError as error:
                    if replay.state.last_entry_at == opened:
                        replay.signal_filters[str(error)] += 1
            # Flat, ineligible baskets have no intrabar economic exposure. Every
            # native close/funding remains consumed, including RSI warmup and halts.
            if needs_open:
                replay.prices((trade, mark), "open", opened + timedelta(seconds=1), entries=True)
            fields = ("low", "high") if scenario.path == "open-low-high-close" else ("high", "low")
            for field, minutes in zip(fields, (20, 40)):
                if full_flat_quotes or any(b.quantity for b in replay.state.economic.ledger.baskets):
                    replay.prices((trade, mark), field, opened + timedelta(minutes=minutes))
            frame = CapitalHour(trade, mark)
            exact = references.get(frame.close_time)
            if exact:
                marks, evidence = boundary_valuation(frame, exact, profile)
                replay.append("valued_hour", frame.close_time, frame=frame, marks=marks, evidence_digest=evidence)
                replay.funding_group(exact, frame.close_time, already_valued=True, unsafe=replay.state)
            else:
                replay.append("hour", frame.close_time, frame=frame)
                replay.settle(frame.close_time)
            replay.curve_point()
            if progress and (i + 1) % 2000 == 0:
                progress(scenario.scenario_id, i + 1, replay.state.economic.ledger.equity)
        report = replay.report(anchor.start, anchor.end)
        report["capital_policy"] = profile.plan.capital_policy
        if current_grids:
            report["grid_source_digest"] = profile.plan.grid_source_digest
            report["grid_price_rounding"] = "adverse entry ceiling / exit floor"
            report["broker_admission_verified"] = False
            if grid_leverage_comparison:
                report["grid_leverage_comparison"] = True
                report["fixed_cycle_leverage"] = str(scenario.leverage)
        report["entry_timeframe"] = f"H{profile.entry_hours}"
        if profile.entry_hours == 1:
            report["eligible_closed_h1_candidates"] = report.pop("eligible_closed_h4_candidates")
            report["closed_h1_signal_filters"] = report.pop("closed_h4_signal_filters")
        report["economically_empty_flat_quotes_omitted"] = not full_flat_quotes
        closed = replay.closed
        receipt = journal.receipt
    # Complete causal input fold, including every quote/funding/exit, from flat genesis.
    with CapitalReplayJournal.restore(
            path, profile_digest=profile.profile_digest, protocol_digest=protocol_digest,
            dataset_digests=dataset_digests, minimum_receipt=receipt) as restored:
        if restored.receipt != receipt:
            raise ValueError("full market journal restore differs")
    report["full_journal_restore_verified"] = True
    with (output / "closed-baskets.json").open("x") as handle:
        handle.write(canonical(closed) + "\n")
    with (output / "report.json").open("x") as handle:
        handle.write(canonical(report) + "\n")
    return report
