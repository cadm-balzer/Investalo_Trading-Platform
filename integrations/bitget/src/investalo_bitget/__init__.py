"""Classic V2 read-only integration core; live dispatch is absent."""
from .models import (
    AccountBinding, AccountMode, BitgetRejected, ClassicIdentity, ErrorCode, FuturesAccount,
    FuturesAsset, FuturesWallet, OwnerContext, ProductType, READ_AUTHORITIES, SpotAsset,
    SpotWallet, validate_unique_binding,
)
from .signing import Credentials, SignedReadRequest
from .transport import HTTPSReadTransport, ReadResponse
from .client import ClassicReadClient

__all__ = [
    "AccountBinding", "AccountMode", "BitgetRejected", "ClassicIdentity", "ErrorCode",
    "FuturesAccount", "FuturesAsset", "FuturesWallet", "OwnerContext", "ProductType",
    "READ_AUTHORITIES", "SpotAsset", "SpotWallet", "validate_unique_binding",
    "Credentials", "SignedReadRequest", "HTTPSReadTransport", "ReadResponse",
    "ClassicReadClient",
]
