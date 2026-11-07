"""Persistent credential client: fixed SQL functions, injected connections/KEKs."""
from .models import ErrorCode, OpenedCredential, StoreContext, StoredSnapshot, StoreRejected
from .client import CredentialStore, ConnectFactory

__all__ = ["ErrorCode", "OpenedCredential", "StoreContext", "StoredSnapshot",
           "StoreRejected", "CredentialStore", "ConnectFactory"]
