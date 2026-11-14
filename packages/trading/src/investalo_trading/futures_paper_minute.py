"""Q49: explicit native minute-open Paper model, independent of exact marks."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from .capital_digest import digest
from .futures_capital_signals import CapitalHour
from .futures_ledger import LedgerMark, number, timestamp
from .futures_paper import PaperFunding
from .futures_paper_settlement import PaperSettlement, _settle_paper_funding

VERSION = "isolated-usdt-futures-paper-minute-settlement/1"
REFERENCE_POLICY = "native-minute-mark-open/1"
MINUTE = timedelta(minutes=1)


@dataclass(frozen=True)
class PaperMarkMinute:
    symbol: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    def __post_init__(self):
        timestamp(self.open_time)
        timestamp(self.close_time)
        if (self.open_time.second or self.open_time.microsecond
                or self.close_time != self.open_time + MINUTE):
            raise ValueError("exact native one-minute reference interval required")
        LedgerMark(self.symbol, self.open)
        for value in (self.open, self.high, self.low, self.close):
            number(value, positive=True)
        if self.high < max(self.open, self.low, self.close) or self.low > min(self.open, self.close):
            raise ValueError("inconsistent native mark minute OHLC")


@dataclass(frozen=True)
class PaperMinuteSettlement:
    input_id: str
    settled_at: datetime
    minutes: tuple[PaperMarkMinute, ...]
    valuation_digest: str
    source_collected_at: datetime
    funding: tuple[PaperFunding, ...]
    hours: tuple[CapitalHour, ...] = ()
    reference_policy: str = REFERENCE_POLICY

    def __post_init__(self):
        timestamp(self.source_collected_at)
        if (self.reference_policy != REFERENCE_POLICY or type(self.minutes) is not tuple
                or not 3 <= len(self.minutes) <= 7
                or any(type(m) is not PaperMarkMinute for m in self.minutes)
                or any(m.open_time != self.settled_at or m.close_time > self.source_collected_at
                       for m in self.minutes)):
            raise ValueError("declared complete closed native minute-open reference required")
        # Reuse validation only. This never constructs an exact journal receipt.
        PaperSettlement(self.input_id, self.settled_at, self.marks, self.valuation_digest,
                        self.funding, self.hours)

    @property
    def marks(self):
        return tuple(LedgerMark(m.symbol, m.open) for m in self.minutes)

    @property
    def receipt_id(self):
        return "paper-minute-settlement-" + digest((VERSION, self))


def settle_paper_minute(state, settlement, expected_revision, at):
    if type(settlement) is not PaperMinuteSettlement:
        raise ValueError("own declared minute-open Paper settlement required")
    if timestamp(at) < settlement.source_collected_at:
        raise ValueError("minute reference not yet known at Paper commit")
    return _settle_paper_funding(state, settlement, expected_revision, at, version=VERSION)
