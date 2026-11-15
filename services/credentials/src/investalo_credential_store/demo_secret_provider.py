"""Separate purpose-bound Demo AEAD/provider primitives; no onboarding or DB writes."""
from __future__ import annotations

import json
import re
import secrets
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from investalo_bitget.futures_demo import DemoBinding, clock, digest
from investalo_bitget.futures_demo_read import DemoReadCredential
from investalo_bitget.models import AccountBinding, OwnerContext
from investalo_credentials import Envelope, KEKRing, SecretPayload, dump_envelope
from investalo_credentials.core import KEY_BYTES, NONCE_BYTES, SCHEMA_VERSION

from .bitget_payload import decode_credentials, encode_credentials
from .models import _PrivateImmutable

PROFILE = "bitget-classic-demo-read-secret/1"


class DemoSecretRejected(ValueError):
    def __init__(self):
        super().__init__("demo_secret_rejected")


class DemoSecretSpec(_PrivateImmutable):
    __slots__ = ("binding", "parent_uid", "egress_ip", "provisioning_digest", "credential_revision")

    def __init__(self, *, binding, parent_uid, egress_ip, provisioning_digest, credential_revision):
        try:
            if (type(binding) is not DemoBinding or type(parent_uid) is not str
                    or type(provisioning_digest) is not str
                    or re.fullmatch("[0-9a-f]{64}", provisioning_digest) is None
                    or type(credential_revision) is not int or not 1 <= credential_revision <= 10**15):
                raise ValueError()
            checked = AccountBinding(binding.owner, binding.broker_uid, parent_uid,
                                     expected_egress_ip=egress_ip)
            if checked.expected_egress_ip is None or checked.expected_egress_ip != egress_ip:
                raise ValueError()
            for name, value in (("binding", binding), ("parent_uid", parent_uid), ("egress_ip", egress_ip),
                                ("provisioning_digest", provisioning_digest),
                                ("credential_revision", credential_revision)):
                object.__setattr__(self, name, value)
        except Exception:
            raise DemoSecretRejected() from None

    def record(self):
        return {"profile": PROFILE, "connection_mode": "demo_read_only", "binding": self.binding.record(),
                "parent_uid": self.parent_uid, "egress_ip": self.egress_ip,
                "provisioning_digest": self.provisioning_digest,
                "credential_revision": self.credential_revision}


def _aad(spec, *, kek_id=None):
    record = {"schema_version": SCHEMA_VERSION, "binding": spec.record(),
              "domain": "investalo.demo.credentials.payload" if kek_id is None else
                        "investalo.demo.credentials.dek-wrap"}
    if kek_id is not None:
        record["kek_id"] = kek_id
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _arguments(spec, keyring, envelope=None):
    if (type(spec) is not DemoSecretSpec or type(keyring) is not KEKRing
            or envelope is not None and type(envelope) is not Envelope):
        raise DemoSecretRejected()


def seal_demo_secret(credentials, spec, keyring):
    """Trusted plaintext boundary; fixed Demo purpose and all original metadata."""
    try:
        _arguments(spec, keyring)
        payload = encode_credentials(credentials)
        dek = secrets.token_bytes(KEY_BYTES)
        payload_nonce, wrap_nonce = secrets.token_bytes(NONCE_BYTES), secrets.token_bytes(NONCE_BYTES)
        ciphertext = AESGCM(dek).encrypt(payload_nonce, payload.reveal(), _aad(spec))
        wrapped = AESGCM(keyring._key(keyring.active_version)).encrypt(
            wrap_nonce, dek, _aad(spec, kek_id=keyring.active_version))
        return Envelope(kek_id=keyring.active_version, payload_nonce=payload_nonce,
                        wrap_nonce=wrap_nonce, wrapped_dek=wrapped, ciphertext=ciphertext)
    except Exception:
        raise DemoSecretRejected() from None


def _open(envelope, spec, keyring):
    _arguments(spec, keyring, envelope)
    try:
        dek = AESGCM(keyring._key(envelope.kek_id)).decrypt(
            envelope.wrap_nonce, envelope.wrapped_dek, _aad(spec, kek_id=envelope.kek_id))
        if len(dek) != KEY_BYTES:
            raise ValueError()
        payload = AESGCM(dek).decrypt(envelope.payload_nonce, envelope.ciphertext, _aad(spec))
        return dek, decode_credentials(SecretPayload(payload))
    except Exception:
        raise DemoSecretRejected() from None


def open_demo_secret(envelope, expected_spec, keyring):
    """Expected purpose/scope comes from trusted state, never from ciphertext."""
    return _open(envelope, expected_spec, keyring)[1]


def rewrap_demo_secret(envelope, expected_spec, keyring):
    """Authenticate both AEADs; only rewrap the existing DEK with active KEK."""
    try:
        dek, _ = _open(envelope, expected_spec, keyring)
        nonce = secrets.token_bytes(NONCE_BYTES)
        wrapped = AESGCM(keyring._key(keyring.active_version)).encrypt(
            nonce, dek, _aad(expected_spec, kek_id=keyring.active_version))
        return Envelope(kek_id=keyring.active_version, payload_nonce=envelope.payload_nonce,
                        wrap_nonce=nonce, wrapped_dek=wrapped, ciphertext=envelope.ciphertext)
    except Exception:
        raise DemoSecretRejected() from None


class DemoSecretSnapshot(_PrivateImmutable):
    __slots__ = ("spec", "envelope", "storage_version")

    def __init__(self, spec, envelope, *, storage_version):
        if (type(spec) is not DemoSecretSpec or type(envelope) is not Envelope
                or type(storage_version) is not int or not 1 <= storage_version <= 2**63 - 1):
            raise DemoSecretRejected()
        object.__setattr__(self, "spec", spec)
        object.__setattr__(self, "envelope", envelope)
        object.__setattr__(self, "storage_version", storage_version)


class SealedDemoReadProvider(_PrivateImmutable):
    """Trusted reader must prove current actor/account/active-purpose permission."""
    __slots__ = ("_spec", "_storage", "_read", "_keyring", "_expires", "_milliseconds")

    def __init__(self, expected_spec, *, expected_storage, read_snapshot, load_keyring, expires_ms,
                 milliseconds=lambda: time.time_ns() // 1_000_000):
        try:
            if (type(expected_spec) is not DemoSecretSpec or type(expected_storage) is not int
                    or not 1 <= expected_storage <= 2**63 - 1 or not callable(read_snapshot)
                    or not callable(load_keyring) or not callable(milliseconds)):
                raise ValueError()
            clock(expires_ms)
            for name, value in (("_spec", expected_spec), ("_storage", expected_storage),
                                ("_read", read_snapshot), ("_keyring", load_keyring),
                                ("_expires", expires_ms), ("_milliseconds", milliseconds)):
                object.__setattr__(self, name, value)
        except Exception:
            raise DemoSecretRejected() from None

    def _time(self):
        now = clock(self._milliseconds())
        if not now < self._expires <= now + 60_000:
            raise DemoSecretRejected()
        return now

    def __call__(self, binding, context):
        try:
            if (type(binding) is not DemoBinding or type(context) is not OwnerContext
                    or binding != self._spec.binding or context != binding.owner):
                raise ValueError()
            before = self._time()
            # No decrypted cache. A revoked/paused/stale reader result cannot reuse a key.
            current = self._read(binding, context)
            if (type(current) is not DemoSecretSnapshot or current.spec.record() != self._spec.record()
                    or current.storage_version != self._storage):
                raise ValueError()
            ring = self._keyring()
            credentials = open_demo_secret(current.envelope, self._spec, ring)
            latest = self._read(binding, context)
            if (type(latest) is not DemoSecretSnapshot or latest.spec.record() != self._spec.record()
                    or latest.storage_version != self._storage
                    or dump_envelope(latest.envelope) != dump_envelope(current.envelope)):
                raise ValueError()
            if self._time() < before:
                raise ValueError()
            return DemoReadCredential(binding, credentials, self._spec.parent_uid, self._spec.egress_ip,
                self._spec.provisioning_digest, self._spec.credential_revision, self._expires)
        except Exception:
            raise DemoSecretRejected() from None
