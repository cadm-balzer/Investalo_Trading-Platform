"""Private immutable Classic V2 read models; no combined equity or trading budget."""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class ErrorCode(StrEnum):
    INVALID_CREDENTIALS = "invalid_credentials"
    INVALID_REQUEST = "invalid_request"
    MODE_UNSUPPORTED = "mode_unsupported"
    CONTEXT_MISMATCH = "context_mismatch"
    UID_MISMATCH = "uid_mismatch"
    PARENT_MISMATCH = "parent_mismatch"
    IP_MISMATCH = "ip_mismatch"
    IP_GATE_REQUIRED = "ip_gate_required"
    ACCOUNT_ALREADY_BOUND = "account_already_bound"
    LOCAL_RATE_LIMIT = "local_rate_limit"
    TRANSPORT_FAILURE = "transport_failure"
    REDIRECT_DENIED = "redirect_denied"
    HTTP_FAILURE = "http_failure"
    RESPONSE_TOO_LARGE = "response_too_large"
    INVALID_RESPONSE = "invalid_response"
    PROVIDER_REJECTED = "provider_rejected"
    PERMISSION_REJECTED = "permission_rejected"
    INVALID_BALANCE = "invalid_balance"


class BitgetRejected(ValueError):
    """Static safe code only; never include broker message, URL, headers or body."""
    def __init__(self, code: ErrorCode):
        if not isinstance(code, ErrorCode):
            code = ErrorCode.INVALID_RESPONSE
        self.code = code
        super().__init__(code.value)


class AccountMode(StrEnum):
    CLASSIC = "classic"
    UTA = "uta"


class ProductType(StrEnum):
    USDT = "USDT-FUTURES"
    USDC = "USDC-FUTURES"
    COIN = "COIN-FUTURES"


READ_AUTHORITIES = frozenset(("stor", "coor", "cpor", "smor", "ttor", "wtor",
                              "taxr", "chor", "p2pr"))


def uid(value: object, *, parent: bool = False) -> str:
    if parent and type(value) is int and 0 <= value < 10**20:
        return str(value)
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", value):
        raise BitgetRejected(ErrorCode.INVALID_RESPONSE)
    return value


def address(value: object) -> str:
    if not isinstance(value, str) or len(value) > 45:
        raise BitgetRejected(ErrorCode.IP_MISMATCH)
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        raise BitgetRejected(ErrorCode.IP_MISMATCH) from None


@dataclass(frozen=True, repr=False)
class OwnerContext:
    tenant_id: UUID
    user_id: UUID

    def __post_init__(self):
        if not isinstance(self.tenant_id, UUID) or not isinstance(self.user_id, UUID):
            raise BitgetRejected(ErrorCode.CONTEXT_MISMATCH)

    def __repr__(self):
        return "OwnerContext(<private>)"


@dataclass(frozen=True, repr=False)
class ClassicIdentity:
    user_id: str
    parent_id: str | None
    authorities: tuple[str, ...]
    ip_whitelist: tuple[str, ...] | None
    server_time: datetime
    mode_evidence: str = field(default="declared_classic_and_v2_schema", init=False)

    def __repr__(self):
        return "ClassicIdentity(<private>)"


@dataclass(frozen=True, repr=False)
class AccountBinding:
    owner: OwnerContext
    expected_uid: str
    expected_parent_id: str | None
    declared_mode: AccountMode = AccountMode.CLASSIC
    expected_egress_ip: str | None = None

    def __post_init__(self):
        if not isinstance(self.owner, OwnerContext):
            raise BitgetRejected(ErrorCode.CONTEXT_MISMATCH)
        uid(self.expected_uid)
        if self.expected_parent_id is not None:
            if self.expected_parent_id != "0":
                uid(self.expected_parent_id)
        if self.declared_mode is not AccountMode.CLASSIC:
            raise BitgetRejected(ErrorCode.MODE_UNSUPPORTED)
        if self.expected_egress_ip is not None:
            object.__setattr__(self, "expected_egress_ip", address(self.expected_egress_ip))

    def __repr__(self):
        return "AccountBinding(<private>)"

    def validate(self, context: OwnerContext, identity: ClassicIdentity, *, require_ip: bool = False):
        if not isinstance(context, OwnerContext) or context != self.owner:
            raise BitgetRejected(ErrorCode.CONTEXT_MISMATCH)
        if not isinstance(identity, ClassicIdentity):
            raise BitgetRejected(ErrorCode.INVALID_RESPONSE)
        if identity.user_id != self.expected_uid:
            raise BitgetRejected(ErrorCode.UID_MISMATCH)
        if identity.parent_id != self.expected_parent_id:
            raise BitgetRejected(ErrorCode.PARENT_MISMATCH)
        if require_ip and (self.expected_egress_ip is None or not identity.ip_whitelist):
            raise BitgetRejected(ErrorCode.IP_GATE_REQUIRED)
        if self.expected_egress_ip is not None and (
            identity.ip_whitelist is None or self.expected_egress_ip not in identity.ip_whitelist
        ):
            raise BitgetRejected(ErrorCode.IP_MISMATCH)


def validate_unique_binding(candidate: AccountBinding, existing: tuple[AccountBinding, ...]):
    """Pure precondition, not an atomic persistence or uniqueness guarantee."""
    if not isinstance(candidate, AccountBinding) or not isinstance(existing, tuple) or len(existing) > 10_000:
        raise BitgetRejected(ErrorCode.CONTEXT_MISMATCH)
    for binding in existing:
        if not isinstance(binding, AccountBinding):
            raise BitgetRejected(ErrorCode.CONTEXT_MISMATCH)
        if binding.expected_uid == candidate.expected_uid and binding.owner != candidate.owner:
            raise BitgetRejected(ErrorCode.ACCOUNT_ALREADY_BOUND)


@dataclass(frozen=True, repr=False)
class SpotAsset:
    coin: str
    available: Decimal | None
    frozen: Decimal | None
    locked: Decimal | None
    limit_available: Decimal | None
    updated_at_ms: int | None


@dataclass(frozen=True, repr=False)
class FuturesAsset:
    coin: str
    balance: Decimal | None
    available: Decimal | None


@dataclass(frozen=True, repr=False)
class FuturesAccount:
    product_type: ProductType
    margin_coin: str
    available: Decimal | None
    locked: Decimal | None
    account_equity: Decimal | None
    usdt_equity: Decimal | None
    btc_equity: Decimal | None
    unrealized_pnl: Decimal | None
    crossed_unrealized_pnl: Decimal | None
    isolated_unrealized_pnl: Decimal | None
    crossed_max_available: Decimal | None
    isolated_max_available: Decimal | None
    max_transfer_out: Decimal | None
    crossed_risk_rate: Decimal | None
    isolated_margin: Decimal | None
    crossed_margin: Decimal | None
    coupon: Decimal | None
    grant: Decimal | None
    asset_mode: str | None
    union_total_margin: Decimal | None
    union_available: Decimal | None
    union_maintenance_margin: Decimal | None
    assets: tuple[FuturesAsset, ...] | None


@dataclass(frozen=True, repr=False)
class SpotWallet:
    binding: AccountBinding
    identity: ClassicIdentity
    assets: tuple[SpotAsset, ...]
    server_time: datetime
    wallet_type: str = field(default="spot", init=False)
    source_url: str = field(default="https://api.bitget.com/api/v2/spot/account/assets", init=False)


@dataclass(frozen=True, repr=False)
class FuturesWallet:
    binding: AccountBinding
    identity: ClassicIdentity
    product_type: ProductType
    accounts: tuple[FuturesAccount, ...]
    server_time: datetime
    wallet_type: str = field(default="futures", init=False)
    source_url: str = field(default="https://api.bitget.com/api/v2/mix/account/accounts", init=False)
