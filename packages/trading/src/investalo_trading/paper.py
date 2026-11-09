"""Incremental simulated execution; the caller commits state and journal atomically."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .models import Candle, DomainEvent, EngineState, Fill, Quote, TradingRejected, precise, utc
from .simulator import PaperSimulator
from .snapshot import _decode, digest, primitive

MAX_CHECKPOINT_BYTES = 16 * 1024 * 1024
SCHEMA = "paper-checkpoint/1"
DAY_POLICY = "paper-h4-close/1"


@dataclass(frozen=True)
class PaperJournalEntry:
    revision: int
    at: datetime
    input_kind: str
    input_digest: str
    fills: tuple[Fill, ...]
    events: tuple[DomainEvent, ...]


@dataclass(frozen=True)
class PaperCheckpoint:
    state: EngineState
    cost_digest: str
    revision: int
    observed_at: datetime
    last_entry: PaperJournalEntry | None = None


@dataclass(frozen=True)
class PaperUpdate:
    checkpoint: PaperCheckpoint
    entry: PaperJournalEntry | None = None


@dataclass(frozen=True)
class PaperRunner:
    """One trusted tenant/account; no automatic resume or manual approvals.

    Every update is immutable. A persistence adapter must CAS the old revision
    and commit the new checkpoint plus entry in ONE transaction before ACK.
    This domain class neither authenticates callers nor provides a DB writer.
    """
    tenant_id: str
    account_id: str
    simulator: PaperSimulator = PaperSimulator()

    def __post_init__(self):
        if not self.tenant_id or not self.account_id:
            raise ValueError("tenant and account required")

    def start(self, at: datetime) -> PaperCheckpoint:
        state = self.simulator.engine.start(self.tenant_id, self.account_id, at)
        return PaperCheckpoint(state, digest(self.simulator.costs), 0, utc(at))

    def validate(self, checkpoint: PaperCheckpoint) -> None:
        self.simulator.engine._validate(checkpoint.state)
        account = checkpoint.state.account
        if (account.tenant_id != self.tenant_id or account.account_id != self.account_id
                or checkpoint.cost_digest != digest(self.simulator.costs)
                or type(checkpoint.revision) is not int or checkpoint.revision < 0):
            raise ValueError("paper checkpoint binding differs")
        utc(checkpoint.observed_at)
        entry = checkpoint.last_entry
        if checkpoint.revision == 0:
            if entry is not None:
                raise ValueError("unexpected initial journal")
        elif (entry is None or entry.revision != checkpoint.revision
              or entry.at != checkpoint.observed_at
              or entry.input_kind not in ("quote", "bar", "day")
              or len(entry.input_digest) != 64
              or any(c not in "0123456789abcdef" for c in entry.input_digest)):
            raise ValueError("paper journal binding differs")
        if entry is not None and entry.input_kind == "day":
            if (entry.fills or len(entry.events) != 1
                    or entry.events[0].kind != "daily_baseline_model"
                    or entry.events[0].symbol != ""
                    or entry.events[0].reference != str(account.trading_day)):
                raise ValueError("paper day binding differs")
            evidence = json.loads(entry.events[0].reason)
            if (evidence.get("policy") != DAY_POLICY or digest(evidence) != entry.input_digest
                    or evidence.get("cash") != str(account.cash)
                    or evidence.get("quantities") != [str(b.quantity) for b in checkpoint.state.baskets]
                    or evidence.get("equity") != str(account.day_start_equity)):
                raise ValueError("paper day evidence differs")

    def _clock(self, checkpoint: PaperCheckpoint, now: datetime) -> datetime:
        now = utc(now)
        if now < checkpoint.observed_at:
            raise TradingRejected("paper_clock_regressed")
        return now

    def _update(self, old: PaperCheckpoint, state: EngineState, now: datetime,
                kind: str, value: object, fills=(), events=()) -> PaperUpdate:
        entry = PaperJournalEntry(old.revision + 1, now, kind, digest(value), fills, events)
        return PaperUpdate(PaperCheckpoint(state, old.cost_digest, entry.revision, now, entry), entry)

    @precise
    def day(self, checkpoint: PaperCheckpoint, bars: tuple[Candle, ...], *,
            now: datetime) -> PaperUpdate:
        """Freeze the current UTC day's modeled basis before post-midnight inputs.

        No quote, indicator, signal, fill or halt changes. Old inventory is usable
        only when the last saved input predates midnight; no hindsight repair.
        """
        self.validate(checkpoint)
        now = self._clock(checkpoint, now)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if checkpoint.state.account.trading_day == now.date():
            return PaperUpdate(checkpoint)
        if checkpoint.state.account.trading_day > now.date():
            raise TradingRejected("paper_day_regressed")
        if checkpoint.observed_at >= midnight:
            raise TradingRejected("paper_midnight_inventory_unavailable")
        if (tuple(b.symbol for b in bars) != self.simulator.engine.config.symbols
                or any(b.close_time != midnight or b.open_time != midnight-timedelta(hours=4)
                       for b in bars)):
            raise TradingRejected("paper_midnight_bars_required")
        # A previously committed boundary bar must still have identical bytes.
        for bar in bars:
            key = f"{bar.symbol}:{bar.open_time.isoformat()}"
            prior = next((value for name, value in checkpoint.state.processed_bars
                          if name == key), None)
            if prior is not None and prior != digest(bar):
                raise TradingRejected("out_of_order_or_revised_candle")
        state = checkpoint.state
        baseline = state.account.cash + sum(
            (state.basket(b.symbol).quantity*b.close for b in bars), Decimal(0))
        evidence = {
            "policy": DAY_POLICY, "cash": str(state.account.cash),
            "quantities": [str(state.basket(b.symbol).quantity) for b in bars],
            "bars": primitive(bars), "bar_digests": {b.symbol: digest(b) for b in bars},
            "equity": str(baseline),
        }
        state = replace(state, account=replace(state.account, trading_day=now.date(),
                                              day_start_equity=baseline))
        event = DomainEvent("daily_baseline_model", "", str(now.date()),
                            json.dumps(evidence, sort_keys=True, separators=(",", ":")))
        return self._update(checkpoint, state, now, "day", evidence, events=(event,))

    def quote(self, checkpoint: PaperCheckpoint, quote: Quote, *, now: datetime) -> PaperUpdate:
        self.validate(checkpoint)
        old = checkpoint.state.quote(quote.symbol)
        if old == quote:
            return PaperUpdate(checkpoint)
        if old is not None and quote.observed_at == old.observed_at:
            raise TradingRejected("paper_quote_revised")
        now = self._clock(checkpoint, now)
        age = (now - quote.observed_at).total_seconds()
        if age < 0 or age > self.simulator.engine.config.quote_max_age_seconds:
            raise TradingRejected("paper_quote_not_fresh")
        transition = self.simulator.engine.on_quote(checkpoint.state, quote, now=now)
        state = transition.state
        # Daily model valuation is a separate committed input, never a quote.
        state, fills, events = self.simulator.settle(
            state, now, symbols=(quote.symbol,), require_later_buy_quote=True,
        )
        return self._update(checkpoint, state, now, "quote", quote,
                            fills, transition.events + events)

    def bar(self, checkpoint: PaperCheckpoint, bar: Candle, *, now: datetime) -> PaperUpdate:
        self.validate(checkpoint)
        key = f"{bar.symbol}:{bar.open_time.isoformat()}"
        previous = next((value for name, value in checkpoint.state.processed_bars if name == key), None)
        if previous is not None:
            if previous != digest(bar):
                raise TradingRejected("out_of_order_or_revised_candle")
            return PaperUpdate(checkpoint)
        now = self._clock(checkpoint, now)
        transition = self.simulator.engine.on_bar(checkpoint.state, bar, observed_at=now)
        if any(event.kind == "data_rejected" for event in transition.events):
            raise TradingRejected("paper_candle_gap")
        # Signals are intents. No synthetic price, OHLC traversal or immediate buy.
        return self._update(checkpoint, transition.state, now, "bar", bar, events=transition.events)

    def dump(self, checkpoint: PaperCheckpoint) -> str:
        self.validate(checkpoint)
        payload = json.dumps({"schema_version": SCHEMA, "mode": "paper",
                              "checkpoint": primitive(checkpoint)},
                             sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(payload.encode()) > MAX_CHECKPOINT_BYTES:
            raise ValueError("paper checkpoint exceeds bound")
        return payload

    def restore(self, payload: str | bytes) -> PaperCheckpoint:
        if not isinstance(payload, (str, bytes)) or len(payload if isinstance(payload, bytes)
                                                       else payload.encode()) > MAX_CHECKPOINT_BYTES:
            raise ValueError("paper checkpoint exceeds bound")

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate checkpoint field")
                result[key] = value
            return result

        document = json.loads(payload, object_pairs_hook=unique)
        if (set(document) != {"schema_version", "mode", "checkpoint"}
                or document["schema_version"] != SCHEMA or document["mode"] != "paper"):
            raise ValueError("unsupported paper checkpoint")
        checkpoint = _decode(PaperCheckpoint, document["checkpoint"])
        self.validate(checkpoint)
        return checkpoint
