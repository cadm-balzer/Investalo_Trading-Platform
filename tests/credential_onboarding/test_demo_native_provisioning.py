"""Private actual files/crypto and signed synthetic replies; no broker requests."""
import hashlib
import json
import os
import pickle
from uuid import UUID, uuid4

import pytest
from investalo_bitget import Credentials, HTTPSReadTransport, OwnerContext, ReadResponse
from investalo_bitget.signing import INFO_PATH, hmac_sha256_base64
from investalo_credentials import KEKRing
from investalo_credential_store import demo_native_provisioning as own
from investalo_credential_store.demo_secret_provider import open_demo_secret, seal_demo_secret

AT = 1_700_000_000_000
OWNER = OwnerContext(UUID(int=1), UUID(int=2))
ACCOUNT = UUID(int=3)
CONNECTION = UUID(int=4)
KEY = b"synthetic-origin-key".ljust(32, b"0")
TRIPLE = Credentials("synthetic-demo-api", "synthetic-demo-secret-ß", "synthetic-demo-pass")


def wire(**changes):
    args = dict(credentials=TRIPLE, provenance_key=KEY, owner=OWNER, account_id=ACCOUNT,
        broker_uid="123456", parent_uid="0", egress_ip="192.0.2.18",
        authorities=["coor", "cpor"], attestation_id=UUID(int=5), approved_ms=AT,
        expires_ms=AT+30_000, created_in_bitget_demo_mode=True)
    return own.make_demo_origin_record(**{**args, **changes})


def reply(at=AT+100, **changes):
    info = dict(userId="123456", parentId=0, ips="192.0.2.18", authorities=["coor", "cpor"])
    return ReadResponse(200, json.dumps(dict(code="00000", requestTime=at,
                        data={**info, **changes})).encode())


class Harness:
    def __init__(self, tmp_path):
        self.root = tmp_path / "private"
        self.root.mkdir(mode=0o700)
        self.path = self.root / "origin.json"
        self.path.write_bytes(wire())
        self.path.chmod(0o400)
        self.reader = own.PrivateDemoOriginReader(str(self.path), owner_uid=os.getuid(),
            expected_sha256=hashlib.sha256(wire()).hexdigest())
        self.now = AT+100
        self.key = KEY
        self.requests = []
        self.response = reply()
        self.before_reply = lambda: None
        self.provider = own.DemoNativeProvisioner(read_approval=self.reader,
            load_provenance_key=lambda: self.key, transport=self.transport,
            milliseconds=lambda: self.now)

    def transport(self, request):
        request.validate()
        self.requests.append(request)
        self.before_reply()
        return self.response

    def run(self, **changes):
        return self.provider(**{**dict(credentials=TRIPLE, owner=OWNER, account_id=ACCOUNT,
            connection_id=CONNECTION, expires_ms=AT+30_000), **changes})

    def mutate(self, content):
        self.path.chmod(0o600)
        self.path.write_bytes(content)
        self.path.chmod(0o400)


@pytest.fixture
def harness(tmp_path):
    return Harness(tmp_path)


def test_exact_signed_probe_returns_scope_bound_spec_and_actual_aead(harness):
    spec = harness.run()
    request, = harness.requests
    assert (request.url, request.method, request.body, request.target, request.axis) == (
        "https://api.bitget.com"+INFO_PATH, "GET", b"", INFO_PATH, "identity")
    assert request.headers["paptrading"] == "1"
    assert request.headers["ACCESS-SIGN"] == hmac_sha256_base64(TRIPLE._secret_key,
        (str(harness.now)+"GET"+INFO_PATH).encode("ascii"))
    assert spec.binding.owner == OWNER and spec.binding.account_id == ACCOUNT
    assert spec.binding.credential_ref == CONNECTION and spec.binding.broker_uid == "123456"
    assert spec.parent_uid == "0" and spec.egress_ip == "192.0.2.18"
    assert spec.credential_revision == 1 and len(spec.provisioning_digest) == 64
    ring = KEKRing((("synthetic-demo", b"K"*32),), active_version="synthetic-demo")
    envelope = seal_demo_secret(TRIPLE, spec, ring)
    opened = open_demo_secret(envelope, spec, ring)
    assert (opened._api_key, opened._secret_key, opened._passphrase) == (
        TRIPLE._api_key, TRIPLE._secret_key, TRIPLE._passphrase)
    private_wire = harness.path.read_bytes()
    assert all(value not in private_wire for value in (
        TRIPLE._api_key.encode(), TRIPLE._secret_key, TRIPLE._passphrase.encode()))


@pytest.mark.parametrize("changes", [
    dict(created_in_bitget_demo_mode=False), dict(created_in_bitget_demo_mode=1),
    dict(provenance_key=b"short"), dict(parent_uid=None),
    dict(egress_ip="2001:0db8::1"), dict(authorities=["coor"]),
    dict(authorities=["coor", "cpor", "trade"]),
    dict(authorities=["cpor", "coor"]), dict(authorities=["coor", "coor", "cpor"]),
    dict(expires_ms=AT+own.APPROVAL_MS+1), dict(approved_ms=True),
])
def test_invalid_or_unattested_setup_rejects(changes):
    with pytest.raises(own.DemoProvisioningRejected, match="^demo_provisioning_rejected$"):
        wire(**changes)


@pytest.mark.parametrize("changes", [
    dict(origin="paptrading_header"), dict(schema="normal-origin/1"),
    dict(extra="broker-specific-message"), dict(credential_mac="untrusted"),
    dict(tenant_id=str(OWNER.tenant_id).upper()), dict(expires_ms=AT),
])
def test_strict_record_schema(changes):
    record = {**json.loads(wire()), **changes}
    if changes.get("tenant_id"):
        record["tenant_id"] = "{"+record["tenant_id"]+"}"
    with pytest.raises(own.DemoProvisioningRejected):
        own.DemoOriginApproval(own._canonical(record))


def test_noncanonical_and_duplicate_json_reject():
    raw = wire()
    for changed in (b" "+raw, raw[:-1]+b',"origin":"operator_attested_bitget_demo_mode"}'):
        with pytest.raises(own.DemoProvisioningRejected):
            own.DemoOriginApproval(changed)


@pytest.mark.parametrize("changes", [
    dict(broker_uid="654321"), dict(parent_uid="654321"), dict(egress_ip="192.0.2.19"),
    dict(authorities=["coor", "cpor", "stor"]), dict(expires_ms=AT+40_000),
    dict(attestation_id=str(UUID(int=6))),
])
def test_mac_authenticates_approval_metadata_before_any_request(harness, changes):
    altered = own.DemoOriginApproval(own._canonical({**json.loads(wire()), **changes}))
    provider = own.DemoNativeProvisioner(read_approval=lambda: altered,
        load_provenance_key=lambda: KEY, transport=harness.transport,
        milliseconds=lambda: harness.now)
    with pytest.raises(own.DemoProvisioningRejected):
        provider(TRIPLE, owner=OWNER, account_id=ACCOUNT, connection_id=CONNECTION, expires_ms=AT+30_000)
    assert harness.requests == []


@pytest.mark.parametrize("changes", [
    dict(owner=OwnerContext(OWNER.tenant_id, uuid4())), dict(account_id=uuid4()),
    dict(connection_id="untrusted"), dict(expires_ms=AT+100),
    dict(expires_ms=AT+60_101), dict(expires_ms=True),
    dict(credentials=Credentials("other-api", "synthetic-demo-secret-ß", "synthetic-demo-pass")),
    dict(credentials=Credentials("synthetic-demo-api", "other-secret", "synthetic-demo-pass")),
    dict(credentials=Credentials("synthetic-demo-api", "synthetic-demo-secret-ß", "other-pass")),
])
def test_original_actor_account_exact_triple_and_deadline_before_send(harness, changes):
    with pytest.raises(own.DemoProvisioningRejected):
        harness.run(**changes)
    assert harness.requests == []


@pytest.mark.parametrize("info", [
    dict(userId="654321"), dict(parentId=42), dict(parentId=None),
    dict(ips=None), dict(ips=""), dict(ips="192.0.2.19"),
    dict(ips="192.0.2.18,192.0.2.19"), dict(authorities=["coor"]),
    dict(authorities=["coor", "cpor", "stor"]), dict(authorities=["coor", "cpor", "trade"]),
    dict(accountMode="uta"), dict(uid="123456"),
])
def test_native_identity_ip_and_exact_read_permissions(harness, info):
    harness.response = reply(**info)
    with pytest.raises(own.DemoProvisioningRejected):
        harness.run()
    assert len(harness.requests) == 1


@pytest.mark.parametrize("native_time", [AT+101, AT-4901])
def test_future_and_stale_native_time(harness, native_time):
    harness.response = reply(at=native_time)
    with pytest.raises(own.DemoProvisioningRejected):
        harness.run()
    assert len(harness.requests) == 1


@pytest.mark.parametrize("change", ["elapsed", "rollback", "expiry", "rotation", "approval", "deletion"])
def test_changes_during_network_reject_whole_probe_no_retry(harness, change):
    def mutate():
        if change == "elapsed":
            harness.now += own.PROBE_MS+1
        elif change == "rollback":
            harness.now -= 1
        elif change == "expiry":
            harness.now = AT+30_000
        elif change == "rotation":
            harness.key = b"changed-origin-key-00000000000000"
        elif change == "approval":
            harness.mutate(wire(broker_uid="654321"))
        else:
            harness.path.unlink()
    harness.before_reply = mutate
    with pytest.raises(own.DemoProvisioningRejected):
        harness.run()
    assert len(harness.requests) == 1


def test_final_native_age_includes_guard_io(harness):
    harness.response = reply(at=AT-4800)  # Initially 4.9 seconds old.
    original, reads = harness.reader, []
    def slow_read():
        reads.append(True)
        if len(reads) == 4:
            harness.now += 200
        return original()
    provider = own.DemoNativeProvisioner(read_approval=slow_read,
        load_provenance_key=lambda: KEY, transport=harness.transport,
        milliseconds=lambda: harness.now)
    with pytest.raises(own.DemoProvisioningRejected):
        provider(TRIPLE, owner=OWNER, account_id=ACCOUNT, connection_id=CONNECTION, expires_ms=AT+30_000)
    assert len(harness.requests) == 1


def test_expired_approval_changed_key_and_slow_key_provider_before_send(harness):
    for key, time in ((b"x"*32, AT+100), (KEY, AT-1), (KEY, AT+30_000)):
        harness.key, harness.now = key, time
        with pytest.raises(own.DemoProvisioningRejected):
            harness.run(expires_ms=harness.now+30_000)
    assert harness.requests == []
    harness.now = AT+100
    def slow_key():
        harness.now += 5001
        return KEY
    provider = own.DemoNativeProvisioner(read_approval=harness.reader,
        load_provenance_key=slow_key, transport=harness.transport, milliseconds=lambda: harness.now)
    with pytest.raises(own.DemoProvisioningRejected):
        provider(TRIPLE, owner=OWNER, account_id=ACCOUNT, connection_id=CONNECTION, expires_ms=AT+30_000)
    assert harness.requests == []


def test_unknown_transport_response_is_static_and_failed_send_consumes_interval(harness):
    def failed(request):
        harness.requests.append(request)
        raise RuntimeError("sensitive key body provider message")
    provider = own.DemoNativeProvisioner(read_approval=harness.reader, load_provenance_key=lambda: KEY,
        transport=failed, milliseconds=lambda: harness.now)
    for _ in range(2):
        with pytest.raises(own.DemoProvisioningRejected, match="^demo_provisioning_rejected$"):
            provider(TRIPLE, owner=OWNER, account_id=ACCOUNT, connection_id=CONNECTION, expires_ms=AT+30_000)
    assert len(harness.requests) == 1


def test_normal_transport_never_accepts_demo_signed_request(harness):
    provider = own.DemoNativeProvisioner(read_approval=harness.reader,
        load_provenance_key=lambda: KEY, transport=HTTPSReadTransport(), milliseconds=lambda: harness.now)
    with pytest.raises(own.DemoProvisioningRejected):
        provider(TRIPLE, owner=OWNER, account_id=ACCOUNT, connection_id=CONNECTION, expires_ms=AT+30_000)


@pytest.mark.parametrize("kind", ["mode", "root_mode", "file_symlink", "parent_symlink",
    "hardlink", "fifo", "wrong_owner", "wrong_hash", "oversize"])
def test_actual_private_file_intake_rejects_unsafe_paths(tmp_path, kind):
    root = tmp_path / "root"
    root.mkdir(mode=0o700)
    file = root / "origin.json"
    file.write_bytes(wire())
    file.chmod(0o400)
    owner, expected = os.getuid(), hashlib.sha256(wire()).hexdigest()
    if kind == "mode":
        file.chmod(0o600)
    elif kind == "root_mode":
        root.chmod(0o755)
    elif kind == "file_symlink":
        target = root / "target"
        file.rename(target)
        file.symlink_to(target)
    elif kind == "parent_symlink":
        alternate = tmp_path / "link"
        alternate.symlink_to(root, target_is_directory=True)
        file = alternate / "origin.json"
    elif kind == "hardlink":
        os.link(file, root / "alias")
    elif kind == "fifo":
        file.unlink()
        os.mkfifo(file, mode=0o400)
    elif kind == "wrong_owner":
        owner += 1
    elif kind == "wrong_hash":
        expected = "f"*64
    else:
        file.chmod(0o600)
        file.write_bytes(b"x"*(own.MAX_BYTES+1))
        file.chmod(0o400)
    with pytest.raises(own.DemoProvisioningRejected):
        own.PrivateDemoOriginReader(str(file), owner_uid=owner, expected_sha256=expected)


@pytest.mark.parametrize("change", ["same_content_replaced", "same_content_mutated", "root_replaced"])
def test_original_inode_and_metadata_are_retained(harness, change):
    if change == "same_content_replaced":
        harness.path.unlink()
        harness.path.write_bytes(wire())
        harness.path.chmod(0o400)
    elif change == "same_content_mutated":
        harness.mutate(wire())
    else:
        renamed = harness.root.with_name("old")
        harness.root.rename(renamed)
        harness.root.mkdir(mode=0o700)
        harness.path.write_bytes(wire())
        harness.path.chmod(0o400)
    with pytest.raises(own.DemoProvisioningRejected):
        harness.run()
    assert harness.requests == []


def test_original_ancestor_is_not_adopted_when_leaf_directory_is_preserved(tmp_path):
    ancestor = tmp_path / "ancestor"
    ancestor.mkdir(mode=0o700)
    harness = Harness(ancestor)
    old = tmp_path / "old"
    ancestor.rename(old)
    ancestor.mkdir(mode=0o700)
    (old / "private").rename(ancestor / "private")
    with pytest.raises(own.DemoProvisioningRejected):
        harness.run()
    assert harness.requests == []


def test_pid_busy_rate_and_private_objects(harness, monkeypatch):
    harness.provider._lock.acquire()
    try:
        with pytest.raises(own.DemoProvisioningRejected):
            harness.run()
    finally:
        harness.provider._lock.release()
    harness.run()
    with pytest.raises(own.DemoProvisioningRejected):
        harness.run()
    assert len(harness.requests) == 1
    for value in (harness.reader, harness.reader(), harness.provider):
        assert "synthetic-demo" not in repr(value)
        with pytest.raises(TypeError):
            pickle.dumps(value)
    monkeypatch.setattr(own.os, "getpid", lambda: -1)
    for callback in (harness.run, harness.reader):
        with pytest.raises(own.DemoProvisioningRejected):
            callback()
