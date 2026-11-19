"""Fresh own trading-purpose snapshots; no cached plaintext or dispatch."""
import os
import time

from investalo_bitget import Credentials, OwnerContext
from investalo_bitget.futures_demo import DemoBinding, clock
from investalo_credentials import Envelope, dump_envelope

from .demo_trading_secret import DemoTradingSecretSpec, DemoTradingSecretRejected, open_demo_trading_secret
from .models import _PrivateImmutable


class DemoTradingSecretSnapshot(_PrivateImmutable):
    __slots__ = ("spec", "envelope", "storage_version")

    def __init__(self, spec, envelope, *, storage_version):
        if (type(spec) is not DemoTradingSecretSpec or type(envelope) is not Envelope
                or type(storage_version) is not int or not 1 <= storage_version < 2**63):
            raise DemoTradingSecretRejected()
        for name, value in (("spec", spec), ("envelope", envelope), ("storage_version", storage_version)):
            object.__setattr__(self, name, value)


class DemoTradingCredentialLease(_PrivateImmutable):
    """Trusted service result, deliberately distinct from DemoReadCredential."""
    __slots__ = ("spec", "credentials", "expires_ms")

    def __init__(self, spec, credentials, expires_ms):
        if type(spec) is not DemoTradingSecretSpec or type(credentials) is not Credentials:
            raise DemoTradingSecretRejected()
        clock(expires_ms)
        for name, value in (("spec", spec), ("credentials", credentials), ("expires_ms", expires_ms)):
            object.__setattr__(self, name, value)


class SealedDemoTradingProvider(_PrivateImmutable):
    """Reader must prove actual current actor/epoch/ready/purpose each time."""
    __slots__ = ("_spec", "_storage", "_read", "_keyring", "_expires", "_clock", "_pid")

    def __init__(self, expected_spec, *, expected_storage, read_snapshot, load_keyring, expires_ms,
                 milliseconds=lambda: time.time_ns() // 1_000_000):
        try:
            if (type(expected_spec) is not DemoTradingSecretSpec
                    or type(expected_storage) is not int or not 1 <= expected_storage < 2**63
                    or not all(callable(value) for value in (read_snapshot, load_keyring, milliseconds))):
                raise ValueError()
            clock(expires_ms)
            for name, value in (("_spec", expected_spec), ("_storage", expected_storage),
                ("_read", read_snapshot), ("_keyring", load_keyring), ("_expires", expires_ms),
                ("_clock", milliseconds), ("_pid", os.getpid())):
                object.__setattr__(self, name, value)
        except Exception:
            raise DemoTradingSecretRejected() from None

    def _time(self):
        now = clock(self._clock())
        if os.getpid() != self._pid or not now < self._expires <= now + 60_000:
            raise DemoTradingSecretRejected()
        return now

    def _snapshot(self, binding, context):
        current = self._read(binding, context)
        if (type(current) is not DemoTradingSecretSnapshot
                or current.spec.record() != self._spec.record()
                or current.storage_version != self._storage):
            raise DemoTradingSecretRejected()
        return current

    def __call__(self, binding, context):
        try:
            if (type(binding) is not DemoBinding or type(context) is not OwnerContext
                    or binding != self._spec.binding or context != binding.owner):
                raise ValueError()
            before = self._time()
            current = self._snapshot(binding, context)
            credentials = open_demo_trading_secret(current.envelope, self._spec, self._keyring())
            latest = self._snapshot(binding, context)
            if dump_envelope(latest.envelope) != dump_envelope(current.envelope) or self._time() < before:
                raise ValueError()
            return DemoTradingCredentialLease(self._spec, credentials, self._expires)
        except Exception:
            raise DemoTradingSecretRejected() from None
