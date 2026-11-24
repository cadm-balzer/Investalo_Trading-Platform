"""Fixed native read producer; original before-image lives in the attempt journal."""
import os
import threading
import time

from investalo_bitget import parse
from investalo_bitget.models import BitgetRejected
from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.futures_demo_margin import (
    MAX_PAGES, capture_margin_baseline, parse_bill_page, reconcile_margin,
)
from .demo_basket_orders import SignedBasketRequest, BasketMarginEvidence
from .models import _PrivateImmutable


class BasketNativeMarginSource(_PrivateImmutable):
    __slots__ = ("transport", "now", "pid", "_last_start", "_pacing_lock")

    def __init__(self, *, transport, milliseconds=lambda: time.time_ns() // 1_000_000):
        if not callable(transport) or not callable(milliseconds):
            raise DemoRejected("invalid_native_margin_source")
        for name, value in dict(transport=transport, now=milliseconds, pid=os.getpid(),
                                _last_start=None, _pacing_lock=threading.Lock()).items():
            object.__setattr__(self, name, value)

    def _get(self, lease, intent, operation, guard, **window):
        if self.pid != os.getpid():
            raise DemoRejected("fork_inherited_margin_source")
        with self._pacing_lock:
            if self._last_start is not None:
                time.sleep(max(0, .11 - (time.monotonic() - self._last_start)))
            guard()
            object.__setattr__(self, "_last_start", time.monotonic())
            packet = SignedBasketRequest(lease, intent, operation, timestamp_ms=self.now(), **window)
        result = self.transport(packet)
        guard()
        return result

    def capture(self, lease, intent, *, context, expected_positions, guard):
        wallet = self._get(lease, intent, "wallet", guard)
        positions = self._get(lease, intent, "positions", guard)
        return capture_margin_baseline(wallet, positions, intent, context=context,
            now_ms=self.now(), expected_positions=expected_positions)

    def resolve(self, lease, intent, observation, positions, *, baseline,
                context, expected_positions, attempted_ms, guard):
        if baseline is None or observation.state not in ("filled", "canceled"):
            return None
        try:
            wallet = self._get(lease, intent, "wallet", guard)
            # Fresh response clock bounds a fixed complete bill window, not "latest".
            _, wallet_at = parse.envelope(wallet)
            _, positions_at = parse.envelope(positions)
            from .demo_basket_orders import milliseconds
            end_ms = max(milliseconds(wallet_at), milliseconds(positions_at), observation.response_ms)
            pages, cursor = [], None
            for _ in range(MAX_PAGES):
                page = self._get(lease, intent, "bills", guard, start_ms=baseline.start_ms,
                                 end_ms=end_ms, cursor=cursor)
                pages.append(page)
                _, cursor, _ = parse_bill_page(page, intent, context=context, now_ms=self.now(),
                    start_ms=baseline.start_ms, end_ms=end_ms, cursor=cursor)
                if cursor is None:
                    break
            result = reconcile_margin(baseline, wallet, positions, tuple(pages), intent, observation,
                context=context, now_ms=self.now(), expected_positions=expected_positions,
                attempted_ms=attempted_ms)
        except (ValueError, BitgetRejected, OSError):
            # The order fill remains observable with unknown margin. A separate
            # final dispatcher lease/actor guard still prevents revoked publication.
            return None
        if result is None:
            return None
        margin, source, at = result
        return BasketMarginEvidence(intent.order_digest, source, observation.quantity, margin, at)
