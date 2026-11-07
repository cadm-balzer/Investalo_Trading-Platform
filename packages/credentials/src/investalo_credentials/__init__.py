"""Isolated credential AEAD envelopes; no SDK, storage, API or transport."""
from .core import (
    AADBinding, Envelope, EnvelopeRejected, ErrorCode, KEKRing, SecretPayload,
    SCHEMA_VERSION, MAX_PAYLOAD_BYTES, MAX_DOCUMENT_BYTES, MAX_KEY_SLOTS,
    seal, open_envelope, rewrap, dump_envelope, load_envelope,
)

__all__ = [
    "AADBinding", "Envelope", "EnvelopeRejected", "ErrorCode", "KEKRing", "SecretPayload",
    "SCHEMA_VERSION", "MAX_PAYLOAD_BYTES", "MAX_DOCUMENT_BYTES", "MAX_KEY_SLOTS",
    "seal", "open_envelope", "rewrap", "dump_envelope", "load_envelope",
]
