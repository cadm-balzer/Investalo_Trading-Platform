"""One unsigned current Classic contracts GET for advisory capacity only."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

from investalo_marketdata.futures_broker_calibration import fetch_contracts, parse_contracts
from investalo_trading.futures_paper_capacity import PaperInstrumentEvidence, PaperInstrumentMinimum


@dataclass(frozen=True)
class FuturesPaperCapacitySource:
    journal: object
    archive: object
    clock: object = lambda: datetime.now(timezone.utc)
    fetch: object = fetch_contracts

    def __call__(self, state):
        actual, _, cursor = self.journal.source_checkpoint()
        if actual != state:
            raise ValueError("capacity checkpoint changed")
        if cursor.market is None or cursor.pending is not None:
            return None
        market = self.archive.load(cursor.market)  # Fully reparse acknowledged native originals.
        if (market.collected_at != state.signal.trade_at or any(
                q.quote.mark != row.mark for q, row in zip(market.quotes,
                    state.signal.economic.ledger.baskets, strict=True))):
            return None  # Funding-only state cannot masquerade as new current quotes.
        began = self.clock()
        raw = self.fetch()  # Fixed URL, bounded bytes/timeout, no redirects, credentials or retry.
        rules = parse_contracts(raw)
        now = self.clock()
        if not 0 <= (now - began).total_seconds() <= 20:
            raise ValueError("current contract calibration clock rejected")
        return PaperInstrumentEvidence(now, hashlib.sha256(raw).hexdigest(), tuple(
            PaperInstrumentMinimum("BITGET:" + r.symbol, r.quantity_step, r.min_quantity,
                r.min_notional, r.price_tick, r.max_market_quantity,
                r.status == "normal", r.min_leverage <= 2 <= r.max_leverage)
            for r in rules), tuple(q.quote for q in market.quotes), market.collected_at)
