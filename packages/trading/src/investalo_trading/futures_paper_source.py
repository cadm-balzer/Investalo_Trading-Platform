"""Source archive references bound atomically to own Paper journal commands."""
from dataclasses import dataclass
from datetime import datetime, timedelta
import re

from .futures_ledger import timestamp
from .futures_paper_minute import PaperMinuteSettlement
from .futures_replay_journal import _sha
from .snapshot import _decode


@dataclass(frozen=True)
class PaperSourceRef:
    kind: str
    key: str
    data_digest: str
    receipt_digest: str
    collected_at: datetime

    def __post_init__(self):
        if (self.kind not in ("market", "minute") or type(self.key) is not str
                or re.fullmatch("[0-9a-f]{32}", self.key) is None):
            raise ValueError("own bounded source archive reference required")
        _sha(self.data_digest)
        _sha(self.receipt_digest)
        timestamp(self.collected_at)


@dataclass(frozen=True)
class PaperFundingCursor:
    prior: PaperSourceRef
    market: PaperSourceRef
    minute: PaperSourceRef
    settlement: PaperMinuteSettlement


@dataclass(frozen=True)
class PaperSourceCursor:
    warmup: PaperSourceRef | None = None
    market: PaperSourceRef | None = None
    pending: PaperFundingCursor | None = None


def advance_source(cursor, command, state):
    """Validate before financial reduction/write; old unbound journals stay old."""
    kind, raw = command["kind"], command["arguments"]
    if kind in ("warmup", "batch", "settlement", "minute_settlement"):
        if cursor != PaperSourceCursor():
            raise ValueError("source-managed Paper journal requires bound source commands")
        return cursor
    if not kind.startswith("source_"):
        return cursor
    at = _decode(datetime, command["at"])
    for key in ("source", "market", "minute"):
        if key in raw and _decode(PaperSourceRef, raw[key]).collected_at > at:
            raise ValueError("source not yet archived at command knowledge time")
    if kind == "source_warmup":
        source = _decode(PaperSourceRef, raw["source"])
        if source.kind != "market" or cursor != PaperSourceCursor() or state.revision:
            raise ValueError("once-only source-managed genesis warmup required")
        return PaperSourceCursor(warmup=source)
    prior = _decode(PaperSourceRef | None, raw["prior"])
    if cursor.warmup is None or prior != cursor.market:
        raise ValueError("acknowledged own source cursor predecessor required")
    if kind == "source_batch":
        source = _decode(PaperSourceRef, raw["source"])
        if (source.kind != "market" or raw["batch"]["input_id"] != "bitget-" + source.data_digest
                or _decode(datetime, raw["batch"]["quoted_at"]) != source.collected_at
                or source.collected_at < state.observed_at):
            raise ValueError("source batch digest and native quote clock mismatch")
        return PaperSourceCursor(cursor.warmup, source)
    if kind == "source_minute_settlement":
        market = _decode(PaperSourceRef, raw["market"])
        minute = _decode(PaperSourceRef, raw["minute"])
        settlement = _decode(PaperMinuteSettlement, raw["settlement"])
        if (prior is None or cursor.pending is not None
                or market.kind != "market" or minute.kind != "minute"
                or settlement.valuation_digest != minute.data_digest
                or settlement.source_collected_at != minute.collected_at
                or market.collected_at < settlement.settled_at
                or prior.collected_at >= settlement.settled_at
                or minute.collected_at < settlement.settled_at + timedelta(minutes=1)):
            raise ValueError("own once-only archived funding source pair required")
        return PaperSourceCursor(cursor.warmup, cursor.market,
                                 PaperFundingCursor(prior, market, minute, settlement))
    raise ValueError("unknown source-managed Paper command")
