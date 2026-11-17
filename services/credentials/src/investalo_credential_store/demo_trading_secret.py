"""Separate Demo trading-key envelope. No SQL, browser intake or order authority."""
import json
import re
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from investalo_bitget.demo_trading_identity import authorities as check_authorities
from investalo_bitget.futures_demo import DemoBinding
from investalo_bitget.models import AccountBinding
from investalo_credentials import Envelope, KEKRing, SecretPayload
from investalo_credentials.core import KEY_BYTES, NONCE_BYTES, SCHEMA_VERSION

from .bitget_payload import decode_credentials, encode_credentials
from .models import _PrivateImmutable

PROFILE = "bitget-classic-demo-trading-secret/1"
PURPOSE = "demo_futures_spot_trading"


class DemoTradingSecretRejected(ValueError):
    def __init__(self):
        super().__init__("demo_trading_secret_rejected")


class DemoTradingSecretSpec(_PrivateImmutable):
    __slots__ = ("binding", "parent_uid", "egress_ip", "authorities",
                 "provisioning_digest", "credential_revision")

    def __init__(self, *, binding, parent_uid, egress_ip, authorities,
                 provisioning_digest, credential_revision):
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
            rights = check_authorities(authorities, canonical=True)
            for name, value in (("binding", binding), ("parent_uid", parent_uid),
                ("egress_ip", egress_ip), ("authorities", rights),
                ("provisioning_digest", provisioning_digest), ("credential_revision", credential_revision)):
                object.__setattr__(self, name, value)
        except Exception:
            raise DemoTradingSecretRejected() from None

    def record(self):
        return {"profile": PROFILE, "purpose": PURPOSE, "environment": "demo",
                "binding": self.binding.record(), "parent_uid": self.parent_uid,
                "egress_ip": self.egress_ip, "authorities": list(self.authorities),
                "provisioning_digest": self.provisioning_digest,
                "credential_revision": self.credential_revision, "order_execution_enabled": False}


def _aad(spec, kek_id=None):
    value = {"schema_version": SCHEMA_VERSION, "binding": spec.record(),
             "domain": "investalo.demo.trading.credentials.payload" if kek_id is None else
                       "investalo.demo.trading.credentials.dek-wrap"}
    if kek_id is not None:
        value["kek_id"] = kek_id
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _arguments(spec, keyring, envelope=None):
    if (type(spec) is not DemoTradingSecretSpec or type(keyring) is not KEKRing
            or envelope is not None and type(envelope) is not Envelope):
        raise DemoTradingSecretRejected()


def seal_demo_trading_secret(credentials, spec, keyring):
    try:
        _arguments(spec, keyring)
        payload = encode_credentials(credentials)
        dek = secrets.token_bytes(KEY_BYTES)
        pn, wn = secrets.token_bytes(NONCE_BYTES), secrets.token_bytes(NONCE_BYTES)
        return Envelope(kek_id=keyring.active_version, payload_nonce=pn, wrap_nonce=wn,
            wrapped_dek=AESGCM(keyring._key(keyring.active_version)).encrypt(
                wn, dek, _aad(spec, keyring.active_version)),
            ciphertext=AESGCM(dek).encrypt(pn, payload.reveal(), _aad(spec)))
    except Exception:
        raise DemoTradingSecretRejected() from None


def _open(envelope, spec, keyring):
    try:
        _arguments(spec, keyring, envelope)
        dek = AESGCM(keyring._key(envelope.kek_id)).decrypt(
            envelope.wrap_nonce, envelope.wrapped_dek, _aad(spec, envelope.kek_id))
        if len(dek) != KEY_BYTES:
            raise ValueError()
        credentials = decode_credentials(SecretPayload(
            AESGCM(dek).decrypt(envelope.payload_nonce, envelope.ciphertext, _aad(spec))))
        return dek, credentials
    except Exception:
        raise DemoTradingSecretRejected() from None


def open_demo_trading_secret(envelope, expected_spec, keyring):
    return _open(envelope, expected_spec, keyring)[1]


def rewrap_demo_trading_secret(envelope, expected_spec, keyring):
    try:
        dek, _ = _open(envelope, expected_spec, keyring)
        nonce = secrets.token_bytes(NONCE_BYTES)
        return Envelope(kek_id=keyring.active_version, payload_nonce=envelope.payload_nonce,
            wrap_nonce=nonce, ciphertext=envelope.ciphertext,
            wrapped_dek=AESGCM(keyring._key(keyring.active_version)).encrypt(
                nonce, dek, _aad(expected_spec, keyring.active_version)))
    except Exception:
        raise DemoTradingSecretRejected() from None
