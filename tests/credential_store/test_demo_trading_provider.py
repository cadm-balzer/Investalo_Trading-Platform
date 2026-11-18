"""Real AEAD/fork and synthetic reader changes; no database or broker."""
import os
import pickle
from uuid import UUID

import pytest
from investalo_bitget import Credentials, OwnerContext
from investalo_bitget.futures_demo import DemoBinding
from investalo_credentials import KEKRing
from investalo_credential_store.demo_secret_provider import DemoSecretSpec, DemoSecretSnapshot, seal_demo_secret
from investalo_credential_store.demo_trading_provider import (
    DemoTradingCredentialLease, DemoTradingSecretSnapshot, SealedDemoTradingProvider,
)
from investalo_credential_store.demo_trading_secret import (
    DemoTradingSecretSpec, DemoTradingSecretRejected, seal_demo_trading_secret,
)

AT = 1_800_000_000_000
OWNER = OwnerContext(UUID(int=1), UUID(int=2))
BINDING = DemoBinding(OWNER, UUID(int=3), UUID(int=4), "123456")
SPEC = DemoTradingSecretSpec(binding=BINDING, parent_uid="0", egress_ip="192.0.2.8",
    authorities=("coow","cpow","stow"), provisioning_digest="d"*64, credential_revision=1)
TRIPLE = Credentials("synthetic-trading-api", "synthetic-trading-secret", "synthetic-trading-pass")
RING = KEKRing((("synthetic", b"K"*32),), active_version="synthetic")


class Harness:
    def __init__(self):
        self.now, self.calls = AT, 0
        self.current = DemoTradingSecretSnapshot(SPEC, seal_demo_trading_secret(TRIPLE, SPEC, RING),
                                                storage_version=1)
        self.on_key = lambda: None
        self.provider = SealedDemoTradingProvider(SPEC, expected_storage=1, read_snapshot=self.read,
            load_keyring=self.key, expires_ms=AT+30_000, milliseconds=lambda: self.now)

    def read(self, binding, context):
        self.calls += 1
        assert binding == BINDING and context == OWNER
        return self.current

    def key(self):
        self.on_key()
        return RING

    def run(self):
        return self.provider(BINDING, OWNER)


def test_fresh_result_has_own_type_and_no_plaintext_cache_or_serialization():
    f = Harness()
    first = f.run()
    second = f.run()
    assert type(first) is DemoTradingCredentialLease and first is not second
    assert f.calls == 4 and first.credentials._api_key == TRIPLE._api_key
    for value in (f.provider, f.current, first):
        assert "synthetic-trading" not in repr(value)
        with pytest.raises(TypeError):
            pickle.dumps(value)
    with pytest.raises(AttributeError):
        first.expires_ms = AT+60_000


@pytest.mark.parametrize("drift", ["spec", "storage", "envelope", "read-profile"])
def test_change_during_decryption_never_returns_the_original_secret(drift):
    f = Harness()
    def change():
        if drift == "spec":
            other = DemoTradingSecretSpec(binding=BINDING, parent_uid="0", egress_ip="192.0.2.9",
                authorities=SPEC.authorities, provisioning_digest="d"*64, credential_revision=1)
            f.current = DemoTradingSecretSnapshot(other, f.current.envelope, storage_version=1)
        elif drift == "storage":
            f.current = DemoTradingSecretSnapshot(SPEC, f.current.envelope, storage_version=2)
        elif drift == "envelope":
            f.current = DemoTradingSecretSnapshot(SPEC, seal_demo_trading_secret(TRIPLE, SPEC, RING),
                                                  storage_version=1)
        else:
            old = DemoSecretSpec(binding=BINDING, parent_uid="0", egress_ip="192.0.2.8",
                                provisioning_digest="d"*64, credential_revision=1)
            f.current = DemoSecretSnapshot(old, seal_demo_secret(TRIPLE, old, RING), storage_version=1)
    f.on_key = change
    with pytest.raises(DemoTradingSecretRejected):
        f.run()
    assert f.calls == 2


@pytest.mark.parametrize("time", [AT-1, AT+30_000, AT+30_001])
def test_expired_or_backward_clock_after_decryption_does_not_publish(time):
    f = Harness()
    f.on_key = lambda: setattr(f, "now", time)
    with pytest.raises(DemoTradingSecretRejected):
        f.run()
    assert f.calls == 2


def test_foreign_binding_and_context_reject_before_reader_or_keys():
    f = Harness()
    for binding, context in ((DemoBinding(OWNER, UUID(int=9), UUID(int=4), "123456"), OWNER),
                             (BINDING, OwnerContext(UUID(int=1), UUID(int=99)))):
        with pytest.raises(DemoTradingSecretRejected):
            f.provider(binding, context)
    assert f.calls == 0


@pytest.mark.skipif(not hasattr(os, "fork"), reason="Linux fork required")
def test_actual_child_cannot_use_inherited_provider_before_any_reader_call():
    f = Harness()
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        ok = False
        try:
            f.run()
        except DemoTradingSecretRejected:
            ok = f.calls == 0
        finally:
            os.write(write_fd, b"1" if ok else b"0")
            os.close(write_fd)
            os._exit(0)
    os.close(write_fd)
    try:
        assert os.read(read_fd, 1) == b"1"
    finally:
        os.close(read_fd)
        _, status = os.waitpid(pid, 0)
    assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
