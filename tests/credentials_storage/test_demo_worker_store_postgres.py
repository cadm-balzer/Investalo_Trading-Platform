"""Real restricted PostgreSQL/AEAD; signed synthetic worker delegations only."""
from dataclasses import replace
from datetime import datetime, timezone
import os
import time
import hashlib
import hmac
import json

import pytest

from conftest import connect_as
from test_demo_trading_store_postgres import trading_database, registered
from test_demo_store_postgres import authority, ring, rejected
from investalo_credential_store import StoreRejected, ErrorCode
from investalo_credential_store.demo_worker_authorization import WorkerIntent
from investalo_credential_store.demo_worker_store import DemoWorkerCredentialStore, READ_SQL
from investalo_credential_store.demo_worker_start import DemoWorkerStartProbe
from investalo_bitget.futures_demo_read import SignedDemoReadRequest
from investalo_bitget.futures_demo import DemoRejected
from test_futures_demo import response


def delegated(f, spec):
    return WorkerIntent(spec.binding.owner.tenant_id, spec.binding.account_id, spec.binding.owner.user_id,
        f["subject_a"], 0, spec.binding.credential_ref, 1, 1, 1, "start", 3,
        ("BNBUSDT", "BTCUSDT", "ETHUSDT"), time.time_ns()//1_000_000, "d"*64)


def worker(f, intent, *, guard=lambda _: None, **changes):
    return DemoWorkerCredentialStore(authority(f).context, intent,
        oidc_issuer=changes.pop("oidc_issuer", f["issuer"]),
        connect=lambda: connect_as("a", tuple_rows=True), control_guard=guard,
        expires_ms=time.time_ns()//1_000_000+30000, **changes)


def test_actual_delegation_provider_does_not_use_oidc_session_or_allow_credential_writes(trading_database):
    f = trading_database
    _, spec, original = registered(f)
    intent = delegated(f, spec)
    store = worker(f, intent)
    snapshot = store.read_snapshot(spec.binding, spec.binding.owner)
    assert snapshot.spec.record() == original.spec.record()
    lease = store.provider(spec, load_keyring=ring)(spec.binding, spec.binding.owner)
    assert lease.credentials._api_key == "synthetic-demo-key"
    assert not any(hasattr(store, k) for k in ("register", "rewrap", "revoke"))
    # Durable authorization, not a short browser session; its original time
    # remains valid until epoch/reauth/account/key changes.
    old = replace(intent, requested_ms=intent.requested_ms-86400000)
    assert worker(f, old).read_snapshot(spec.binding, spec.binding.owner).storage_version == 1


@pytest.mark.parametrize("change", ["epoch", "subject", "issuer", "future", "storage"])
def test_original_delegation_and_fresh_key_binding_are_checked(trading_database, change):
    f = trading_database
    _, spec, _ = registered(f)
    i = delegated(f, spec)
    args = {}
    if change == "epoch":
        i = replace(i, auth_epoch=1)
    elif change == "subject":
        i = replace(i, subject="foreign")
    elif change == "issuer":
        args["oidc_issuer"] = "https://foreign.invalid"
    elif change == "future":
        i = replace(i, requested_ms=i.requested_ms+100000)
    else:
        i = replace(i, storage_version=2)
    rejected(ErrorCode.ACCESS_DENIED, lambda: worker(f, i, **args).read_snapshot(spec.binding, spec.binding.owner))


@pytest.mark.parametrize("change", ["inactive", "membership", "reauth", "account", "key", "epoch"])
def test_actual_revocation_during_sessionless_worker_blocks_decryption(trading_database, change):
    f = trading_database
    client, spec, _ = registered(f)
    i = delegated(f, spec)
    store = worker(f, i)
    provider = store.provider(spec, load_keyring=ring)
    provider(spec.binding, spec.binding.owner)
    if change == "key":
        client.revoke(spec.binding.credential_ref, expected_revision=1, expected_storage=1)
    else:
        with connect_as("admin") as db:
            if change == "inactive":
                db.execute("UPDATE platform.users SET active=false WHERE id=%s", (f["user_a"],))
            elif change == "epoch":
                db.execute("UPDATE platform.users SET auth_epoch=auth_epoch+1 WHERE id=%s", (f["user_a"],))
            elif change == "membership":
                db.execute("UPDATE platform.memberships SET active=false WHERE tenant_id=%s AND user_id=%s",
                           (f["tenant_a"], f["user_a"]))
            elif change == "reauth":
                db.execute("UPDATE platform.users SET reauth_after=to_timestamp(%s) WHERE id=%s",
                           ((i.requested_ms+1)/1000, f["user_a"]))
            else:
                db.execute("UPDATE platform.accounts SET status='paused' WHERE id=%s", (f["account_a"],))
    with pytest.raises(Exception):
        provider(spec.binding, spec.binding.owner)


def test_live_control_guard_change_stops_snapshot_publication(trading_database):
    f = trading_database
    _, spec, _ = registered(f)
    i = delegated(f, spec)
    calls = []
    def guard(_):
        calls.append(1)
        if len(calls) > 1:
            raise ValueError("synthetic current control changed")
    rejected(ErrorCode.UNAVAILABLE, lambda: worker(f, i, guard=guard).read_snapshot(spec.binding, spec.binding.owner))


def test_function_boundary_rejects_runtime_research_unbound_and_foreign_owner(trading_database):
    f = trading_database
    _, spec, _ = registered(f)
    i = delegated(f, spec)
    args = (spec.binding.credential_ref, i.auth_epoch, i.subject, f["issuer"], i.requested_ms,
            1, 1, i.requested_ms+30000)
    for identity in ("runtime", "research", "unbound", "b"):
        with pytest.raises(Exception), connect_as(identity, tuple_rows=True) as db:
            db.execute(READ_SQL, args).fetchall()


@pytest.mark.parametrize("case", ["flat", "unknown_grant", "approved_unknown_grant", "changed_control", "bad_signature"])
def test_real_signed_intent_restricted_database_aead_to_fixed_native_start_gets(trading_database, case):
    f = trading_database
    _, spec, _ = registered(f)
    binding = spec.binding
    now = time.time_ns()//1_000_000
    key = b"synthetic-worker-intent-key-0000"
    value = dict(schema="investalo-demo-h1-intent/1", binding=dict(
        tenant_id=str(binding.owner.tenant_id), account_id=str(binding.account_id),
        user_id=str(binding.owner.user_id), connection_id=str(binding.credential_ref),
        subject=f["subject_a"], auth_epoch=0, credential_revision=1, storage_version=1),
        revision=1, action="start", basket_limit=3, assets=["BNBUSDT", "BTCUSDT", "ETHUSDT"],
        requested_at=datetime.fromtimestamp(now/1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"))
    def sign(value):
        payload = json.dumps(value, separators=(",", ":"))
        return json.dumps(dict(payload=payload, mac=hmac.new(key, payload.encode(), hashlib.sha256).hexdigest())).encode()
    control = [sign(value)]
    if case == "bad_signature":
        control[0] = control[0].replace(b'"mac": "', b'"mac": "a')
    calls = []
    def native(packet):
        assert type(packet) is SignedDemoReadRequest and packet.method == "GET"
        packet.validate()
        assert packet.headers["paptrading"] == "1"
        calls.append(packet.axis)
        if packet.axis == "identity":
            data = dict(userId=binding.broker_uid, parentId=0, ips="", authorities=["coow", "cpow", "stow"])
        elif packet.axis == "wallet":
            data = [dict(marginCoin="USDT", accountEquity="9999.911", available="9999.911",
                locked="0", unrealizedPL="0", isolatedMargin="0", crossedMargin="0",
                coupon="0", grant=None if "unknown_grant" in case else "0", assetMode="single")]
            if case == "changed_control":
                control[0] = sign({**value, "action": "pause", "revision": 2})
        else:
            data = []
        return response(data, at=time.time_ns()//1_000_000)
    from investalo_bitget.futures_demo_policy import ApprovedDemoStrategyPolicy
    policy_factory = (lambda snapshot: ApprovedDemoStrategyPolicy(
        snapshot.spec.binding, 1, snapshot.storage_version)) if case == "approved_unknown_grant" else None
    probe = DemoWorkerStartProbe(dict(tenant_id=f["tenant_a"], user_id=f["user_a"],
        account_id=f["account_a"], broker_uid=binding.broker_uid, parent_uid="0",
        egress_ip="192.0.2.8", oidc_issuer=f["issuer"], ip_binding="unavailable_in_demo"),
        authority(f).context, read_control=lambda: control[0], intent_key=key,
        connect=lambda: connect_as("a", tuple_rows=True), keyring=ring,
        installation_guard=lambda: None, transport=native, policy_factory=policy_factory)
    if case in ("bad_signature", "changed_control"):
        with pytest.raises(DemoRejected):
            probe.read()
        assert calls == ([] if case == "bad_signature" else ["identity", "wallet"])
    else:
        report = probe.read()
        assert calls == ["identity", "wallet", "positions"]
        assert report.control_revision == 1 and not report.execution_enabled
        if case in ("flat", "approved_unknown_grant"):
            assert str(report.native.account.equity) == "9999.911"
            assert report.native.blockers == ()
            if case == "approved_unknown_grant":
                assert report.native.unconfirmed_fields == ("grant",) and report.native.policy_digest
        else:
            assert report.native.account is None
            assert report.native.blockers == ("collateral_unconfirmed",)
