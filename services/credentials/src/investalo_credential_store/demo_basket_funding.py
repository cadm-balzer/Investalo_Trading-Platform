"""Read-only actual funding source over existing guarded Trading AEAD packets."""
from investalo_bitget import parse
from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.futures_demo_basket import BasketFundingIntent
from investalo_bitget.futures_demo_funding import funding_batch
from investalo_bitget.futures_demo_margin import MAX_PAGES, parse_bill_page
from investalo_bitget.models import BitgetRejected
from .demo_basket_margin import BasketNativeMarginSource
from .demo_basket_orders import milliseconds
from .models import _PrivateImmutable


class BasketNativeFundingSource(_PrivateImmutable):
    __slots__ = ("reader",)

    def __init__(self, reader):
        if type(reader) is not BasketNativeMarginSource:
            raise DemoRejected("guarded_native_funding_reader_required")
        object.__setattr__(self, "reader", reader)

    def read(self, lease, intent, *, context, book, guard):
        if type(intent) is not BasketFundingIntent:
            raise DemoRejected("own_funding_read_scope_required")
        try:
            wallet = self.reader._get(lease, intent, "wallet", guard)
            positions = self.reader._get(lease, intent, "positions", guard)
            _, wallet_at = parse.envelope(wallet)
            _, positions_at = parse.envelope(positions)
            end = max(milliseconds(wallet_at), milliseconds(positions_at))
            if end <= intent.from_ms:
                return None
            pages, cursor = [], None
            for _ in range(MAX_PAGES):
                page = self.reader._get(lease, intent, "bills", guard,
                    start_ms=intent.from_ms, end_ms=end, cursor=cursor)
                pages.append(page)
                _, cursor, _ = parse_bill_page(page, intent, context=context, now_ms=self.reader.now(),
                    start_ms=intent.from_ms, end_ms=end, cursor=cursor)
                if cursor is None:
                    break
            return funding_batch(wallet, positions, tuple(pages), intent, book,
                                 context=context, now_ms=self.reader.now(), policy=self.reader.policy)
        except (ValueError, BitgetRejected, OSError):
            return None  # Missing sources never advance the original durable cursor.
