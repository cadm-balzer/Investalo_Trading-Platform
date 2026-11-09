#!/usr/bin/env python3
"""Read-only real public SPOT feed check; no database or private credentials."""
from datetime import datetime, timezone
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root/"packages/trading/src"), str(root/"packages/marketdata/src")]
from investalo_marketdata.paper_feed import BitgetPaperFeed, H4, SYMBOLS, boundary


def main():
    feed = BitgetPaperFeed()
    now = datetime.now(timezone.utc)
    end = boundary(now)
    for symbol in SYMBOLS:
        bars = feed.closed_bars(symbol, start=end-40*H4, end=end, now=now)
        quote = feed.quote(symbol)
        age = (datetime.now(timezone.utc)-quote.observed_at).total_seconds()
        print(f"{symbol}: closed_h4={len(bars)} last_close={bars[-1].close_time.isoformat()} "
              f"bid={quote.bid} ask={quote.ask} quote_age_seconds={age:.3f}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        raise SystemExit(f"Public Paper feed rejected: {error}") from None
    except Exception:
        raise SystemExit("Public Paper feed unavailable or rejected") from None
