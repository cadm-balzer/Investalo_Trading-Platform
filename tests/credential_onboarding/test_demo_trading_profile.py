"""Actual private files/AEAD, synthetic trading-key identity responses only."""
import hashlib
import json
import os
import pickle
from uuid import UUID

import pytest
from investalo_bitget import BitgetRejected, Credentials, OwnerContext, ReadResponse, parse
from investalo_bitget.demo_trading_identity import trading_identity
from investalo_bitget.futures_demo import DemoBinding
from investalo_bitget.signing import INFO_PATH, hmac_sha256_base64
from investalo_credentials import KEKRing
from investalo_credential_store import demo_trading_provisioning as own
from investalo_credential_store.demo_native_provisioning import (
    DemoNativeProvisioner, DemoOriginApproval, DemoProvisioningRejected,
    PrivateDemoOriginReader, make_demo_origin_record,
)
from investalo_credential_store.demo_secret_provider import (
    DemoSecretRejected, DemoSecretSpec, open_demo_secret, seal_demo_secret,
)
from investalo_credential_store.demo_trading_secret import (
    DemoTradingSecretRejected, DemoTradingSecretSpec, open_demo_trading_secret,
    rewrap_demo_trading_secret, seal_demo_trading_secret,
)

AT = 1_800_000_000_000
OWNER = OwnerContext(UUID(int=1), UUID(int=2))
ACCOUNT, CONNECTION = UUID(int=3), UUID(int=4)
KEY = b"T"*32
RIGHTS = ["coow", "cpow", "stow"]
TRIPLE = Credentials("synthetic-demo-trading-api", "synthetic-demo-trading-secret-ß",
                     "synthetic-demo-trading-pass")


def record(**changes):
    args = dict(credentials=TRIPLE, provenance_key=KEY, owner=OWNER, account_id=ACCOUNT,
        broker_uid="123456", parent_uid="0", egress_ip="192.0.2.18", authorities=RIGHTS,
        attestation_id=UUID(int=5), approved_ms=AT, expires_ms=AT+30_000,
        created_in_bitget_demo_mode=True)
    return own.make_demo_trading_origin_record(**{**args, **changes})


def reply(**changes):
    value = dict(userId="123456", parentId=0, ips="192.0.2.18", authorities=RIGHTS)
    return ReadResponse(200, json.dumps(dict(code="00000", requestTime=AT+100,
                                          data={**value, **changes})).encode())


class Harness:
    def __init__(self, tmp_path):
        self.root = tmp_path/"private"
        self.root.mkdir(mode=0o700)
        self.path = self.root/"approval.json"
        self.path.write_bytes(record())
        self.path.chmod(0o400)
        self.reader = own.PrivateDemoTradingOriginReader(str(self.path), owner_uid=os.getuid(),
            expected_sha256=hashlib.sha256(record()).hexdigest())
        self.key, self.now, self.response = KEY, AT+100, reply()
        self.requests = []
        self.after_send = lambda: None
        self.provider = own.DemoTradingNativeProvisioner(read_approval=self.reader,
            load_provenance_key=lambda: self.key, transport=self.transport,
            milliseconds=lambda: self.now)

    def transport(self, request):
        request.validate()
        self.requests.append(request)
        self.after_send()
        return self.response

    def run(self, **changes):
        return self.provider(**{**dict(credentials=TRIPLE, owner=OWNER, account_id=ACCOUNT,
            connection_id=CONNECTION, expires_ms=AT+30_000), **changes})


@pytest.fixture
def harness(tmp_path):
    return Harness(tmp_path)


def test_native_policy_accepts_write_codes_without_loosening_old_parser():
    info = trading_identity(reply())
    assert info.authorities == tuple(RIGHTS) and info.parent_id == "0"
    with pytest.raises(BitgetRejected):
        parse.identity(reply())
    assert trading_identity(reply(authorities=RIGHTS+["coor", "cpor", "wtor"])).authorities == (
        "coor", "coow", "cpor", "cpow", "stow", "wtor")


@pytest.mark.parametrize("extra", ["wwow", "wtow", "smow", "ttow", "chow", "taxw", "p2p", "pllw", "pllr", "unknown"])
def test_overscoped_keys_are_not_accepted(extra):
    with pytest.raises(BitgetRejected):
        trading_identity(reply(authorities=RIGHTS+[extra]))
    with pytest.raises(DemoProvisioningRejected):
        record(authorities=sorted(RIGHTS+[extra]))


@pytest.mark.parametrize("rights", [[], ["coor", "cpor", "stor"], ["coow", "cpow"], ["coow", "stow"],
                                   ["cpow", "stow"], RIGHTS+["stow"]])
def test_missing_or_duplicate_native_rights_fail(rights):
    with pytest.raises(BitgetRejected):
        trading_identity(reply(authorities=rights))


@pytest.mark.parametrize("change", [{"permissions": RIGHTS}, {"permType": "read-and-write"},
    {"uid": "123456"}, {"accountMode": "classic"}, {"accountType": "classic"},
    {"userId": "01"}, {"parentId": "00"}, {"ips": "192.0.2.18,192.0.2.18"}])
def test_uta_or_malformed_identity_never_becomes_classic(change):
    with pytest.raises(BitgetRejected):
        trading_identity(reply(**change))


def test_exact_fixed_get_and_separate_scope_bound_envelope(harness):
    spec = harness.run()
    assert type(spec) is DemoTradingSecretSpec
    request, = harness.requests
    assert (request.url, request.target, request.method, request.body) == (
        "https://api.bitget.com"+INFO_PATH, INFO_PATH, "GET", b"")
    assert request.headers["paptrading"] == "1"
    assert request.headers["ACCESS-SIGN"] == hmac_sha256_base64(
        TRIPLE._secret_key, (str(harness.now)+"GET"+INFO_PATH).encode())
    assert spec.authorities == tuple(RIGHTS)
    assert spec.record()["purpose"] == "demo_futures_spot_trading"
    assert spec.record()["order_execution_enabled"] is False
    ring = KEKRing((("demo", b"K"*32),), active_version="demo")
    envelope = seal_demo_trading_secret(TRIPLE, spec, ring)
    assert open_demo_trading_secret(envelope, spec, ring)._secret_key == TRIPLE._secret_key
    rotated = KEKRing((("demo", b"K"*32), ("next", b"N"*32)), active_version="next")
    rewrapped = rewrap_demo_trading_secret(envelope, spec, rotated)
    assert rewrapped.ciphertext == envelope.ciphertext and rewrapped.payload_nonce == envelope.payload_nonce
    assert open_demo_trading_secret(rewrapped, spec, rotated)._api_key == TRIPLE._api_key
    for private in (spec, harness.reader(), request):
        assert "synthetic-demo" not in str(private)
        with pytest.raises(TypeError):
            pickle.dumps(private)


def test_origins_and_ciphertexts_are_not_convertible_to_read_only(harness):
    with pytest.raises(DemoProvisioningRejected):
        DemoOriginApproval(record())
    with pytest.raises(DemoProvisioningRejected):
        PrivateDemoOriginReader(str(harness.path), owner_uid=os.getuid(),
            expected_sha256=hashlib.sha256(record()).hexdigest())
    old_wire = make_demo_origin_record(credentials=TRIPLE, provenance_key=KEY, owner=OWNER,
        account_id=ACCOUNT, broker_uid="123456", parent_uid="0", egress_ip="192.0.2.18",
        authorities=["coor", "cpor"], attestation_id=UUID(int=5), approved_ms=AT,
        expires_ms=AT+30_000, created_in_bitget_demo_mode=True)
    with pytest.raises(DemoProvisioningRejected):
        own.DemoTradingOriginApproval(old_wire)
    old = DemoNativeProvisioner(read_approval=harness.reader, load_provenance_key=lambda: KEY,
        transport=harness.transport, milliseconds=lambda: harness.now)
    with pytest.raises(DemoProvisioningRejected):
        old(TRIPLE, owner=OWNER, account_id=ACCOUNT, connection_id=CONNECTION, expires_ms=AT+30_000)
    assert harness.requests == []
    spec = harness.run()
    read_spec = DemoSecretSpec(binding=spec.binding, parent_uid=spec.parent_uid, egress_ip=spec.egress_ip,
        provisioning_digest=spec.provisioning_digest, credential_revision=spec.credential_revision)
    ring = KEKRing((("demo", b"K"*32),), active_version="demo")
    with pytest.raises(DemoSecretRejected):
        open_demo_secret(seal_demo_trading_secret(TRIPLE, spec, ring), read_spec, ring)
    with pytest.raises(DemoTradingSecretRejected):
        open_demo_trading_secret(seal_demo_secret(TRIPLE, read_spec, ring), spec, ring)
    with pytest.raises(DemoSecretRejected):
        seal_demo_secret(TRIPLE, spec, ring)
    with pytest.raises(DemoTradingSecretRejected):
        seal_demo_trading_secret(TRIPLE, read_spec, ring)


@pytest.mark.parametrize("change", [{"userId": "999999"}, {"parentId": 42},
    {"ips": ""}, {"ips": "192.0.2.19"}, {"ips": "192.0.2.18,192.0.2.19"},
    {"authorities": RIGHTS+["stor"]}])
def test_native_identity_must_match_original_approval_exactly(harness, change):
    harness.response = reply(**change)
    with pytest.raises(DemoProvisioningRejected):
        harness.run()
    assert len(harness.requests) == 1


@pytest.mark.parametrize("change", [{"owner": OwnerContext(UUID(int=1), UUID(int=99))},
    {"account_id": UUID(int=99)}, {"credentials": Credentials("other-api", "other-secret", "other-pass")},
    {"expires_ms": AT+61_000}, {"expires_ms": AT+100}])
def test_foreign_or_expired_requests_never_send(harness, change):
    with pytest.raises(DemoProvisioningRejected):
        harness.run(**change)
    assert harness.requests == []


@pytest.mark.parametrize("failure", ["file", "key", "stale", "future", "clock"])
def test_original_binding_and_time_are_rechecked_after_send(harness, failure):
    def alter():
        if failure == "file":
            harness.path.chmod(0o600)
            harness.path.write_bytes(record(broker_uid="654321"))
            harness.path.chmod(0o400)
        elif failure == "key":
            harness.key = b"X"*32
        elif failure == "stale":
            harness.now += 5001
        elif failure == "clock":
            harness.now -= 1
    if failure == "future":
        harness.response = ReadResponse(200, json.dumps(dict(code="00000", requestTime=AT+101,
            data=dict(userId="123456", parentId=0, ips="192.0.2.18", authorities=RIGHTS))).encode())
    harness.after_send = alter
    with pytest.raises(DemoProvisioningRejected):
        harness.run()
    assert len(harness.requests) == 1


def test_failed_send_consumes_interval_without_retry(harness):
    def fail(request):
        harness.requests.append(request)
        raise RuntimeError("synthetic-private-response")
    object.__setattr__(harness.provider, "_transport", fail)
    for _ in range(2):
        with pytest.raises(DemoProvisioningRejected) as error:
            harness.run()
        assert str(error.value) == "demo_provisioning_rejected"
    assert len(harness.requests) == 1


@pytest.mark.parametrize("field", ["binding", "parent_uid", "egress_ip", "authorities",
                                 "provisioning_digest", "credential_revision"])
def test_every_original_envelope_binding_field_is_authenticated(harness, field):
    spec = harness.run()
    args = dict(binding=spec.binding, parent_uid=spec.parent_uid, egress_ip=spec.egress_ip,
        authorities=spec.authorities, provisioning_digest=spec.provisioning_digest,
        credential_revision=spec.credential_revision)
    alternatives = dict(binding=DemoBinding(OWNER, UUID(int=77), CONNECTION, "123456"),
        parent_uid="42", egress_ip="192.0.2.19", authorities=tuple(sorted(RIGHTS+["stor"])),
        provisioning_digest="f"*64, credential_revision=2)
    altered = DemoTradingSecretSpec(**{**args, field: alternatives[field]})
    ring = KEKRing((("demo", b"K"*32),), active_version="demo")
    sealed = seal_demo_trading_secret(TRIPLE, spec, ring)
    with pytest.raises(DemoTradingSecretRejected):
        open_demo_trading_secret(sealed, altered, ring)
