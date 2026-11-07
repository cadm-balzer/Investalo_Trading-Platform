"""Owner-scoped read adapter. No persistence, orders, transfers or hidden retries."""
from __future__ import annotations

import math
import threading
import time
from typing import Callable

from . import parse
from .models import (
    AccountBinding, AccountMode, BitgetRejected, ClassicIdentity, ErrorCode,
    FuturesWallet, OwnerContext, ProductType, SpotWallet,
    address,
)
from .signing import Credentials, FUTURES_PATH, INFO_PATH, SPOT_PATH, SignedReadRequest
from .transport import HTTPSReadTransport, Transport


class ClassicReadClient:
    def __init__(self, credentials: Credentials, owner: OwnerContext, *, transport: Transport,
                 declared_mode: AccountMode = AccountMode.CLASSIC,
                 require_ip_gate: bool = True,
                 milliseconds: Callable[[], int] = lambda: time.time_ns() // 1_000_000,
                 monotonic: Callable[[], float] = time.monotonic):
        if not isinstance(credentials, Credentials):
            raise BitgetRejected(ErrorCode.INVALID_CREDENTIALS)
        if not isinstance(owner, OwnerContext):
            raise BitgetRejected(ErrorCode.CONTEXT_MISMATCH)
        if declared_mode is not AccountMode.CLASSIC:
            raise BitgetRejected(ErrorCode.MODE_UNSUPPORTED)
        if not callable(transport) or not callable(milliseconds) or not callable(monotonic):
            raise BitgetRejected(ErrorCode.INVALID_REQUEST)
        if type(require_ip_gate) is not bool or isinstance(transport, HTTPSReadTransport) and not require_ip_gate:
            raise BitgetRejected(ErrorCode.IP_GATE_REQUIRED)
        self._credentials = credentials
        self._owner = owner
        self._transport = transport
        self._milliseconds = milliseconds
        self._monotonic = monotonic
        self._require_ip_gate = require_ip_gate
        self._last_info_started: float | None = None
        self._lock = threading.Lock()

    def __repr__(self):
        return "ClassicReadClient(<private>)"

    def _context(self, context: OwnerContext, binding: AccountBinding | None = None):
        if (not isinstance(context, OwnerContext) or context != self._owner
                or binding is not None and (not isinstance(binding, AccountBinding) or binding.owner != self._owner)):
            raise BitgetRejected(ErrorCode.CONTEXT_MISMATCH)
        if binding is not None and binding.declared_mode is not AccountMode.CLASSIC:
            raise BitgetRejected(ErrorCode.MODE_UNSUPPORTED)

    def _get(self, path: str, parameters: tuple[tuple[str, str], ...] = ()):
        try:
            request = SignedReadRequest(self._credentials, path, parameters, self._milliseconds())
            return self._transport(request)
        except BitgetRejected:
            raise
        except Exception:
            raise BitgetRejected(ErrorCode.TRANSPORT_FAILURE) from None

    def probe_identity(self, context: OwnerContext, *, expected_egress_ip: str) -> ClassicIdentity:
        """Only accountinfo: learn UID before binding, with explicit IP gate."""
        self._context(context)
        expected = address(expected_egress_ip)
        return self._identity(context, expected_ip=expected, require_ip=True)

    def read_identity(self, context: OwnerContext, *, binding: AccountBinding | None = None) -> ClassicIdentity:
        self._context(context, binding)
        if self._require_ip_gate and (binding is None or binding.expected_egress_ip is None):
            # Never send real credentials before an explicit expected-egress gate.
            raise BitgetRejected(ErrorCode.IP_GATE_REQUIRED)
        info = self._identity(context, expected_ip=binding.expected_egress_ip if binding else None,
                              require_ip=self._require_ip_gate)
        if binding is not None:
            binding.validate(context, info, require_ip=self._require_ip_gate)
        return info

    def _identity(self, context: OwnerContext, *, expected_ip: str | None, require_ip: bool):
        with self._lock:
            current = self._monotonic()
            if (type(current) not in (int, float) or not math.isfinite(current)
                    or self._last_info_started is not None and current - self._last_info_started < 1):
                raise BitgetRejected(ErrorCode.LOCAL_RATE_LIMIT)
            self._last_info_started = current
            info = parse.identity(self._get(INFO_PATH))
        if require_ip and (expected_ip is None or not info.ip_whitelist):
            raise BitgetRejected(ErrorCode.IP_GATE_REQUIRED)
        if expected_ip is not None and (not info.ip_whitelist or expected_ip not in info.ip_whitelist):
            raise BitgetRejected(ErrorCode.IP_MISMATCH)
        return info

    def read_spot(self, context: OwnerContext, binding: AccountBinding) -> SpotWallet:
        if not isinstance(binding, AccountBinding):
            raise BitgetRejected(ErrorCode.CONTEXT_MISMATCH)
        info = self.read_identity(context, binding=binding)
        assets, at = parse.spot_assets(self._get(SPOT_PATH, (("assetType", "all"),)))
        return SpotWallet(binding, info, assets, at)

    def read_futures(self, context: OwnerContext, binding: AccountBinding,
                     product_type: ProductType) -> FuturesWallet:
        if not isinstance(binding, AccountBinding):
            raise BitgetRejected(ErrorCode.CONTEXT_MISMATCH)
        if not isinstance(product_type, ProductType):
            raise BitgetRejected(ErrorCode.INVALID_REQUEST)
        info = self.read_identity(context, binding=binding)
        accounts, at = parse.futures_accounts(
            self._get(FUTURES_PATH, (("productType", product_type.value),)), product_type)
        return FuturesWallet(binding, info, product_type, accounts, at)
