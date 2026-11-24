"""Classic Demo native funding bills, original complete window and account source."""
from datetime import timedelta
import hashlib

from . import parse
from .futures_demo import DemoRejected
from .futures_demo_basket import BasketFundingIntent
from .futures_demo_margin import MAX_PAGES, margin_snapshot, parse_bill_page
from investalo_trading.capital_digest import digest
from investalo_trading.futures_broker_funding import BrokerFundingBill, BrokerFundingBatch, milliseconds


def funding_batch(wallet, positions, pages, intent, book, *, context, now_ms):
    if type(intent) is not BasketFundingIntent or intent.book_digest != book.state_digest or book.pending is not None:
        raise DemoRejected("original_idle_funding_scope_required")
    snapshot = margin_snapshot(wallet, positions, intent, context=context, now_ms=now_ms)
    end = snapshot.observed_ms
    if end <= intent.from_ms:
        return None
    if type(pages) is not tuple or not 1 <= len(pages) <= MAX_PAGES:
        raise DemoRejected("complete_bounded_funding_pages_required")
    owned = {b.symbol: b for b in book.signal.economic.ledger.baskets if b.quantity}
    bills, ids, hashes, cursor, observed = [], set(), [], None, end
    for index, response in enumerate(pages):
        if index and cursor is None:
            raise DemoRejected("extra_funding_bill_page")
        rows, cursor, at = parse_bill_page(response, intent, context=context, now_ms=now_ms,
            start_ms=intent.from_ms, end_ms=end, cursor=cursor)
        if at < observed:
            raise DemoRejected("funding_source_clock_regressed")
        observed = at
        hashes.append(hashlib.sha256(response.body).hexdigest())
        for row in rows:
            if row["id"] in ids:
                raise DemoRejected("duplicate_native_funding_bill")
            ids.add(row["id"])
            if row["created_ms"] == intent.from_ms:
                continue  # Inclusive API boundary already covered by the durable cursor.
            basket = owned.get(row["symbol"])
            if (basket is None or row["kind"] != "contract_settle_fee" or row["fee"] != 0
                    or row["coupon_fee"] not in (None, 0)):
                raise DemoRejected("foreign_or_non_funding_activity_in_original_window")
            bills.append(BrokerFundingBill(digest(("bitget-demo-funding-bill/1", intent.binding.record(), row["id"])),
                basket.symbol, basket.cycle, basket.quantity, row["amount"],
                parse.EPOCH + timedelta(milliseconds=row["created_ms"])))
    if cursor is not None:
        return None
    bills = tuple(sorted(bills, key=lambda b: (b.settled_at, b.symbol, b.id_digest)))
    return BrokerFundingBatch(book.state_digest, intent.from_ms, end,
        parse.EPOCH + timedelta(milliseconds=observed), snapshot, bills,
        digest(("bitget-demo-funding-batch/1", intent.intent_digest, snapshot, hashes, bills)))
