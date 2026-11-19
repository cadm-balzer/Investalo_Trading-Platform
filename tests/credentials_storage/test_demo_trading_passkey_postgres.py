"""Actual015 issuance/consume/lock with synthetic WebAuthn verdicts and keys."""
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from hashlib import sha256
import hmac
import json
import os
import secrets
from threading import Barrier
from time import time
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from investalo_credential_store.demo_trading_passkey_assertion import DemoTradingPasskeyRequestVerifier
from investalo_credential_store.demo_trading_passkey_authorization import DemoTradingPasskeyAuthorizationClient
from investalo_credential_store.passkey_request_assertion import PasskeyRequestContext, PasskeyRequestVerifier
from investalo_credential_store.models import StoreContext
from investalo_credential_store.request_assertion import OnboardingRejected
from conftest import connect_as
from test_passkey_authorization_flow import RP, ORIGIN, KEY, actor, clock, enroll, receipt as normal_receipt, token as normal_token
from test_demo_trading_store_postgres import registered

PREPARE = "SELECT * FROM platform.demo_trading_passkey_credential_prepare(" + ",".join(["%s"]*12) + ")"
AUTHORIZE = "SELECT platform.demo_trading_passkey_credential_authorize(" + ",".join(["%s"]*8) + ") AS receipt"
CONSUME = "SELECT platform.demo_trading_credential_consume_passkey_authorization(%s::jsonb) AS id"
LOCK = "SELECT platform.demo_trading_credential_lock_passkey_authorization(%s::jsonb) AS valid"


@pytest.fixture
def demo_context(credential_database):
    f = credential_database
    with connect_as("admin") as db:
        assert db.execute("SELECT 1 FROM platform.schema_migrations WHERE version='019_demo_trading_passkey'").fetchone()
        db.execute("UPDATE platform.accounts SET mode='bitget_demo',status='ready' WHERE tenant_id=%s AND id=%s",
                   (f["tenant_a"], f["account_a"]))
    return f


def prepare(f, action="register", *, enrolled=False):
    if not enrolled:
        enroll(f)
    connection = uuid4()
    if action == "revoke":
        _, spec, _ = registered(f)
        connection = spec.binding.credential_ref
    body = dict(platform_account_id=str(f["account_a"]), connection_id=str(connection))
    if action == "register":
        body["credentials"] = dict(api_key="synthetic-demo-api", secret="synthetic-demo-päß",
                                   passphrase="synthetic-demo-phrase")
    else:
        body.update(expected_revision=1, expected_storage=1)
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    binding, confirmation = secrets.token_bytes(32), secrets.token_bytes(32)
    with connect_as("runtime") as db:
        actor(db, f)
        oidc = clock(db)-600
        p = db.execute(PREPARE, (f["account_a"], action, connection if action=="register" else None,
            RP, ORIGIN, secrets.token_bytes(32), binding, confirmation,
            sha256(raw).hexdigest(), clock(db)+600, 0, oidc)).fetchone()
    return p, oidc, raw


def grant(f, p, oidc, offset=0):
    with connect_as("runtime") as db:
        actor(db, f)
        db.execute("SELECT * FROM platform.demo_trading_passkey_action_claim(%s,%s,%s,%s,%s)",
                   (p["attempt_id"], RP, p["session_binding"], 0, oidc)).fetchone()
    with connect_as("runtime") as db:
        actor(db, f)
        return db.execute("SELECT * FROM platform.demo_trading_passkey_action_finish(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (p["attempt_id"], RP, p["session_binding"], 0, True, False, clock(db)+offset, 0, oidc)).fetchone()


def authorize(f, p, g, oidc, **changes):
    args = dict(authorization=p["authorization_id"], grant=g["grant_id"], rp=RP, origin=ORIGIN,
                binding=p["session_binding"], confirmation=p["confirmation_hash"], epoch=0, oidc=oidc)
    args.update(changes)
    with connect_as("runtime") as db:
        actor(db, f)
        return db.execute(AUTHORIZE, tuple(args.values())).fetchone()["receipt"]


def issued(f, action="register"):
    p, oidc, raw = prepare(f, action)
    return authorize(f, p, grant(f, p, oidc), oidc), raw


def claims(receipt, **changes):
    part = normal_token(receipt).split(".")[1]
    data = json.loads(base64.urlsafe_b64decode(part+"="*(-len(part)%4)))
    data.update(aud="investalo-credentials-demo-trading-passkey",
                htu="/v1/credentials/bitget-demo-trading/"+receipt["target"]["action"])
    data.update(changes)
    return data


def token(data):
    b64 = lambda raw: base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    wire = b64(b'{"alg":"HS256","typ":"JWT"}')+"."+b64(json.dumps(data, separators=(",", ":")).encode())
    return wire+"."+b64(hmac.digest(KEY, wire.encode(), "sha256"))


def client(f, r, *, connect=None):
    return DemoTradingPasskeyAuthorizationClient(
        StoreContext(tenant_id=f["tenant_a"], user_id=f["user_a"],
                     expected_login_role=os.environ["CREDENTIAL_TEST_USER_A"]),
        context(r),
        verifier=DemoTradingPasskeyRequestVerifier(key=KEY, oidc_issuer=f["issuer"], origin=ORIGIN, clock=lambda: int(time())),
        connect=connect or (lambda: connect_as("a", tuple_rows=True)))


def context(r):
    return PasskeyRequestContext(tenant_id=UUID(r["tenant_id"]), user_id=UUID(r["user_id"]),
        subject=r["subject"], auth_epoch=r["auth_epoch"], oidc_auth_time=r["oidc_auth_time"],
        session_binding=r["session_binding"], session_expires_at=r["session_expires_at"])


def state(r):
    with connect_as("admin") as db:
        return db.execute("SELECT state,receipt,consumed_claims FROM platform.demo_trading_passkey_credential_authorizations "
                          "WHERE authorization_id=%s", (UUID(r["authorization_id"]),)).fetchone()


def denied(operation, code="42501"):
    with pytest.raises(psycopg.Error) as error:
        operation()
    assert error.value.sqlstate == code


def worker(sql, data):
    with connect_as("a") as db:
        return db.execute(sql, (Jsonb(data),)).fetchone()


@pytest.mark.parametrize("field,value", (
    ("aud", "investalo-credentials-demo-passkey"),
    ("authorization_kind", "passkey-demo-credential-authorization/1"),
    ("htu", "/v1/credentials/bitget-demo/register"),
))
def test_read_domain_claims_reject_before_any_database_access(demo_context, field, value):
    r, raw = issued(demo_context)
    calls = []
    def forbidden():
        calls.append(True)
        raise RuntimeError("synthetic-private-driver-canary")
    with pytest.raises(OnboardingRejected, match="authentication_required"):
        client(demo_context, r, connect=forbidden).consume(
            "register", token=token(claims(r, **{field: value})), body=raw)
    assert calls == [] and state(r)["state"] == "authorized"


def test_actual_read_and_trading_proofs_verifiers_consumers_and_handles_are_separate(demo_context):
    from investalo_credential_store.demo_passkey_authorization import DemoPasskeyAuthorizationClient
    import test_demo_passkey_postgres as read
    f = demo_context
    p, oidc, _ = read.prepare(f)
    with connect_as("runtime") as db:
        actor(db, f)
        denied(lambda: db.execute(
            "SELECT * FROM platform.demo_trading_passkey_action_claim(%s,%s,%s,%s,%s)",
            (p["attempt_id"], RP, p["session_binding"], 0, oidc)))
    old = read.authorize(f, p, read.grant(f, p, oidc), oidc)
    p, oidc, raw = prepare(f, enrolled=True)
    with connect_as("runtime") as db:
        actor(db, f)
        denied(lambda: db.execute("SELECT * FROM platform.demo_passkey_action_claim(%s,%s,%s,%s,%s)",
            (p["attempt_id"], RP, p["session_binding"], 0, oidc)))
    r = authorize(f, p, grant(f, p, oidc), oidc)
    own = client(f, r)
    with pytest.raises(OnboardingRejected, match="authentication_required"):
        own.consume("register", token=read.token(read.claims(old)), body=raw)
    denied(lambda: worker(CONSUME, read.claims(old)), "22023")
    denied(lambda: worker("SELECT platform.demo_credential_consume_passkey_authorization(%s::jsonb)",
                          claims(r)), "22023")
    old_verifier = read.DemoPasskeyRequestVerifier(key=KEY, oidc_issuer=f["issuer"],
        origin=ORIGIN, clock=lambda: int(time()))
    with pytest.raises(OnboardingRejected):
        old_verifier.verify(token(claims(r)), action="register", body=raw, context=context(r))
    with pytest.raises(OnboardingRejected, match="invalid_context"):
        DemoPasskeyAuthorizationClient(own._store_context, context(r),
            verifier=own._verifier, connect=lambda: connect_as("a", tuple_rows=True))
    handle = own.consume("register", token=token(claims(r)), body=raw)
    with pytest.raises(OnboardingRejected, match="invalid_context"):
        with read.client(f, old).lock(handle):
            pass
    with own.lock(handle):
        pass


@pytest.mark.parametrize("action", ("register", "revoke"))
def test_actual_own_consent_signed_consume_then_terminal_separate_lock(demo_context, action):
    f = demo_context
    r, raw = issued(f, action)
    assert r["kind"] == "passkey-demo-trading-credential-authorization/1"
    assert r["oidc_auth_time"] < r["checked_at"] <= r["authorized_at"]
    assert len({r[k] for k in ("authorization_id","proof_id","grant_id")}) == 3
    assert r["body_sha256"] == sha256(raw).hexdigest()
    own = client(f, r)
    handle = own.consume(action, token=token(claims(r)), body=raw)
    assert state(r)["state"] == "consumed"
    with own.lock(handle) as db:
        assert db.execute("SELECT 1").fetchone() == (1,)
    assert state(r)["state"] == "locked"
    with pytest.raises(OnboardingRejected):
        own.consume(action, token=token(claims(r)), body=raw)
    with pytest.raises(OnboardingRejected):
        with own.lock(handle):
            pass
    with connect_as("admin") as db:
        events = db.execute("SELECT event FROM platform.demo_trading_passkey_credential_authorization_audit "
                            "WHERE authorization_id=%s", (UUID(r["authorization_id"]),)).fetchall()
        assert {e["event"] for e in events} == {"prepared","authorized","consumed","locked"}
        assert db.execute("SELECT count(*) AS n FROM platform.demo_credential_connections "
                          "WHERE tenant_id=%s AND connection_id=%s",
                          (f["tenant_a"], UUID(r["target"]["connection_id"]))).fetchone()["n"] == (action=="revoke")
    assert "synthetic-demo-päß" not in json.dumps(state(r), ensure_ascii=False)


def test_paused_own_account_allows_fresh_keyless_revoke_purpose(demo_context):
    f = demo_context
    _, oidc, raw = prepare(f, "revoke")
    # Pause invalidates old metadata; prepare fresh consent for the paused account.
    with connect_as("admin") as db:
        db.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",
                   (f["tenant_a"], f["account_a"]))
    with connect_as("runtime") as db:
        actor(db, f)
        p = db.execute(PREPARE, (f["account_a"], "revoke", None, RP, ORIGIN,
            secrets.token_bytes(32), secrets.token_bytes(32), secrets.token_bytes(32),
            sha256(raw).hexdigest(), clock(db)+600, 0, oidc)).fetchone()
    r = authorize(f, p, grant(f, p, oidc), oidc)
    own = client(f, r)
    handle = own.consume("revoke", token=token(claims(r)), body=raw)
    with own.lock(handle):
        pass
    assert state(r)["state"] == "locked"


def test_frozen_metadata_purpose_and_claim_commit_precede_verdict(demo_context):
    f = demo_context
    p, oidc, _ = prepare(f)
    assert p["metadata"]["purpose"] == "demo_futures_spot_trading"
    assert p["metadata"]["profile"] == "bitget-classic-demo-trading-secret/1"
    assert p["metadata"]["environment"] == "demo"
    assert p["metadata"]["key_authorities"] is None
    with connect_as("runtime") as db:
        actor(db, f)
        db.execute("SELECT * FROM platform.demo_trading_passkey_action_claim(%s,%s,%s,%s,%s)",
                   (p["attempt_id"], RP, p["session_binding"], 0, oidc))
        # Same transaction cannot act as acknowledged committed claim.
        denied(lambda: db.execute("SELECT * FROM platform.demo_trading_passkey_action_finish(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (p["attempt_id"], RP, p["session_binding"], 0, True, False, clock(db), 0, oidc)))
    with connect_as("admin") as db:
        assert db.execute("SELECT state FROM platform.passkey_action_proofs WHERE proof_id=%s",
                          (p["attempt_id"],)).fetchone()["state"] == "prepared"


def test_old_normal_proof_entry_points_do_not_accept_demo_proof(demo_context):
    f = demo_context
    p, oidc, _ = prepare(f)
    with connect_as("runtime") as db:
        actor(db, f)
        denied(lambda: db.execute("SELECT * FROM platform.passkey_action_claim(%s,%s,%s,%s,%s)",
                                 (p["attempt_id"], RP, p["session_binding"], 0, oidc)))
    g = grant(f, p, oidc)
    with connect_as("runtime") as db:
        actor(db, f)
        denied(lambda: db.execute("SELECT * FROM platform.passkey_action_confirm(%s,%s,%s,%s,%s,%s)",
            (g["grant_id"], RP, p["session_binding"], p["confirmation_hash"], 0, oidc)))
    assert authorize(f, p, g, oidc)["kind"] == "passkey-demo-trading-credential-authorization/1"


@pytest.mark.parametrize("field,value", (("aud","investalo-credentials-passkey"),
    ("authorization_kind","passkey-credential-authorization/1"),("htu","/v1/credentials/bitget/register"),
    ("htm","GET"),("origin","https://other.local.test:8443"),("auth_epoch",1),
    ("session_binding","e"*64),("body_sha256","e"*64),("exp",1),("passkey_checked_at",1)))
def test_wrong_signed_domain_context_body_or_clock_never_opens_database(demo_context, field, value):
    f = demo_context
    r, raw = issued(f)
    opened = []
    def unavailable():
        opened.append(True)
        raise RuntimeError("synthetic-private-driver-secret")
    own = client(f, r, connect=unavailable)
    c = claims(r)
    c[field] = value
    with pytest.raises(OnboardingRejected) as error:
        own.consume("register", token=token(c), body=raw)
    assert str(error.value) == "authentication_required" and opened == []
    assert state(r)["state"] == "authorized"


def test_signed_body_preserves_exact_bytes_and_rejects_extra_fields(demo_context):
    f = demo_context
    r, raw = issued(f)
    own = client(f, r)
    with pytest.raises(OnboardingRejected):
        own.consume("register", token=token(claims(r)), body=raw+b" ")
    c = claims(r, body_sha256=sha256(raw+b" ").hexdigest())
    # Valid raw whitespace is verifiable, but no longer matches frozen DB consent.
    with pytest.raises(OnboardingRejected):
        own.consume("register", token=token(c), body=raw+b" ")
    body = json.loads(raw)
    body["broker_uid"] = "1234"
    changed = json.dumps(body).encode()
    with pytest.raises(OnboardingRejected):
        own.consume("register", token=token(claims(r, body_sha256=sha256(changed).hexdigest())), body=changed)
    assert state(r)["state"] == "authorized"


def test_legacy_verifier_and_sql_consumer_refuse_demo_and_reverse(credential_database):
    f = credential_database
    normal, normal_raw = normal_receipt(f, "register")
    denied(lambda: worker(CONSUME, json.loads(base64.urlsafe_b64decode(normal_token(normal).split(".")[1]+"=="))), "22023")
    demo = DemoTradingPasskeyRequestVerifier(key=KEY, oidc_issuer=f["issuer"], origin=ORIGIN, clock=lambda: int(time()))
    with pytest.raises(OnboardingRejected):
        demo.verify(normal_token(normal), action="register", body=normal_raw, context=context(normal))
    with connect_as("admin") as db:
        db.execute("UPDATE platform.accounts SET mode='bitget_demo',status='ready' WHERE tenant_id=%s AND id=%s",
                   (f["tenant_a"], f["account_a"]))
    p, oidc, raw = prepare(f, enrolled=True)
    r = authorize(f, p, grant(f,p,oidc), oidc)
    legacy = PasskeyRequestVerifier(key=KEY, oidc_issuer=f["issuer"], origin=ORIGIN, clock=lambda: int(time()))
    with pytest.raises(OnboardingRejected):
        legacy.verify(token(claims(r)), action="register", body=raw, context=context(r))
    denied(lambda: worker("SELECT platform.credential_consume_passkey_authorization(%s::jsonb)", claims(r)), "22023")


@pytest.mark.parametrize("field,value", (("confirmation", b"x"*32),("binding",b"x"*32),
    ("origin","https://other.local.test:8443"),("epoch",1),("grant",uuid4())))
def test_explicit_consent_context_mismatch_leaves_grant_usable(demo_context, field, value):
    f = demo_context
    p, oidc, _ = prepare(f)
    g = grant(f,p,oidc)
    denied(lambda: authorize(f,p,g,oidc,**{field:value}))
    r = authorize(f,p,g,oidc)
    assert r["grant_id"] == str(g["grant_id"])
    denied(lambda: authorize(f,p,g,oidc))


def test_future_factor_verdict_cannot_issue_consent(demo_context):
    f = demo_context
    p, oidc, _ = prepare(f)
    g = grant(f,p,oidc,offset=5)
    denied(lambda: authorize(f,p,g,oidc))


@pytest.mark.parametrize("change", ("metadata","epoch","role","factor","paused"))
def test_current_authority_metadata_factor_changes_block_consumed_handle(demo_context, change):
    f = demo_context
    r, raw = issued(f)
    own = client(f,r)
    handle = own.consume("register",token=token(claims(r)),body=raw)
    with connect_as("admin") as db:
        if change=="metadata":
            db.execute("UPDATE platform.accounts SET name='Changed' WHERE tenant_id=%s AND id=%s",(f["tenant_a"],f["account_a"]))
        elif change=="paused":
            db.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",(f["tenant_a"],f["account_a"]))
        elif change=="epoch":
            db.execute("UPDATE platform.users SET auth_epoch=1 WHERE id=%s",(f["user_a"],))
        elif change=="role":
            db.execute("UPDATE platform.memberships SET role='viewer' WHERE tenant_id=%s AND user_id=%s",(f["tenant_a"],f["user_a"]))
        else:
            db.execute("UPDATE platform.passkey_credentials SET status='revoked',revoked_at=clock_timestamp(),storage_version=storage_version+1 "
                       "WHERE passkey_id=%s",(UUID(r["passkey_id"]),))
    with pytest.raises(OnboardingRejected):
        with own.lock(handle):
            pass
    assert state(r)["state"]=="consumed"


def test_concurrent_demo_consume_has_one_winner(demo_context):
    f = demo_context
    r, raw = issued(f)
    wire, barrier = token(claims(r)), Barrier(2)
    def contender():
        own = client(f,r)
        barrier.wait(timeout=5)
        try:
            own.consume("register",token=wire,body=raw)
            return "consumed"
        except OnboardingRejected as e:
            return e.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result(timeout=15) for future in (pool.submit(contender),pool.submit(contender))]
    assert sorted(results)==["access_denied","consumed"]


def test_consume_must_commit_before_lock_and_rollback_keeps_authorized(demo_context):
    r,_ = issued(demo_context)
    data = claims(r)
    with connect_as("a") as db:
        db.execute(CONSUME,(Jsonb(data),))
        denied(lambda: db.execute(LOCK,(Jsonb(data),)))
    assert state(r)["state"]=="authorized"


def test_unknown_actual_consume_commit_does_not_return_handle_or_retry(demo_context):
    f = demo_context
    r,raw = issued(f)
    calls = []
    @contextmanager
    def lost_ack():
        calls.append(True)
        with connect_as("a",tuple_rows=True) as db:
            yield db
        raise RuntimeError("synthetic-driver-private-canary")
    own = client(f,r,connect=lost_ack)
    with pytest.raises(OnboardingRejected) as error:
        own.consume("register",token=token(claims(r)),body=raw)
    assert str(error.value)=="unavailable" and calls==[True]
    assert state(r)["state"]=="consumed"


def test_demo_jti_is_once_only_across_distinct_demo_authorizations(demo_context):
    f = demo_context
    first, raw = issued(f)
    original = claims(first)
    client(f, first).consume("register", token=token(original), body=raw)
    p, oidc, raw = prepare(f, enrolled=True)
    second = authorize(f, p, grant(f, p, oidc), oidc)
    reused = claims(second, jti=original["jti"])
    with pytest.raises(OnboardingRejected) as error:
        client(f, second).consume("register", token=token(reused), body=raw)
    assert str(error.value) == "access_denied"
    assert state(first)["state"] == "consumed"
    assert state(second)["state"] == "authorized"


def test_expiry_after_lock_yield_rolls_back_lock_and_audit(demo_context):
    f = demo_context
    r, raw = issued(f)
    own = client(f, r)
    c = claims(r, exp=int(time())+3)
    handle = own.consume("register", token=token(c), body=raw)
    with pytest.raises(OnboardingRejected):
        with own.lock(handle) as db:
            db.execute("SELECT pg_sleep(3.1)")
    assert state(r)["state"] == "consumed"
    with connect_as("admin") as db:
        assert db.execute("SELECT count(*) AS n FROM platform.demo_trading_passkey_credential_authorization_audit "
                          "WHERE authorization_id=%s AND event='locked'",
                          (UUID(r["authorization_id"]),)).fetchone()["n"] == 0


def test_same_handle_lock_can_recover_caller_rollback_then_becomes_terminal(demo_context):
    f = demo_context
    r,raw = issued(f)
    own = client(f,r)
    handle = own.consume("register",token=token(claims(r)),body=raw)
    with pytest.raises(OnboardingRejected):
        with own.lock(handle):
            raise RuntimeError("synthetic-private-error")
    assert state(r)["state"]=="consumed"
    with own.lock(handle):
        pass
    assert state(r)["state"]=="locked"
    with pytest.raises(OnboardingRejected):
        with client(f,r).lock(handle):
            pass


def test_demo_purpose_rls_private_helpers_and_frozen_records(demo_context):
    f = demo_context
    p,_,_ = prepare(f)
    for who in ("runtime","a","research"):
        with connect_as(who) as db:
            denied(lambda: db.execute("SELECT * FROM platform.demo_trading_passkey_credential_authorizations"))
    with connect_as("runtime") as db:
        actor(db,f)
        denied(lambda: db.execute("SELECT * FROM platform.demo_trading_passkey_action_prepare(%s,'register',%s,%s,%s,%s,%s,%s,0,1)",
            (f["account_a"],uuid4(),RP,b"a"*32,b"b"*32,b"c"*32,int(time())+60)))
    with connect_as("admin") as db:
        denied(lambda: db.execute("UPDATE platform.demo_trading_passkey_credential_authorizations SET body_sha256=repeat('e',64) "
                                 "WHERE authorization_id=%s",(p["authorization_id"],)))
    with connect_as("admin") as db:
        rows = db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid IN "
                          "('platform.demo_trading_passkey_credential_authorizations'::regclass,"
                          "'platform.demo_trading_passkey_credential_authorization_audit'::regclass)").fetchall()
        assert len(rows)==2 and all(r["relrowsecurity"] and r["relforcerowsecurity"] for r in rows)
        functions = db.execute("SELECT p.proname,p.proconfig,p.prosecdef,r.rolname AS owner FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_roles r ON r.oid=p.proowner "
            "WHERE n.nspname='platform' AND proname=ANY(%s)", ([
                "demo_trading_credential_passkey_metadata", "demo_trading_passkey_action_locked",
                "demo_trading_passkey_action_prepare", "demo_trading_passkey_action_claim",
                "demo_trading_passkey_action_finish", "demo_trading_passkey_action_read_grant",
                "demo_trading_passkey_action_confirm", "demo_trading_passkey_credential_prepare",
                "demo_trading_passkey_credential_receipt", "demo_trading_passkey_credential_authorize",
                "demo_trading_passkey_credential_claims_valid", "demo_trading_credential_passkey_authorization_locked",
                "demo_trading_credential_consume_passkey_authorization", "demo_trading_credential_lock_passkey_authorization",
            ],)).fetchall()
        assert len(functions) == 14
        assert all(row["proconfig"] == ["search_path=pg_catalog"] and row["owner"] == "investalo_migration"
                   for row in functions)
        passive = {"demo_trading_credential_passkey_metadata", "demo_trading_passkey_credential_receipt",
                   "demo_trading_passkey_credential_claims_valid"}
        assert all(row["prosecdef"] == (row["proname"] not in passive) for row in functions)
    for statement in (
        "DELETE FROM platform.demo_trading_passkey_credential_authorizations WHERE authorization_id=%s",
        "UPDATE platform.demo_trading_passkey_credential_authorization_audit SET event='locked' WHERE authorization_id=%s",
    ):
        with connect_as("admin") as db:
            denied(lambda: db.execute(statement, (p["authorization_id"],)))
    with connect_as("admin") as db:
        child = db.execute("SELECT to_regclass('platform.demo_trading_passkey_credential_completion_audit') AS relation").fetchone()
        denied(lambda: db.execute("TRUNCATE platform.demo_trading_passkey_credential_authorizations,"
                                  "platform.demo_trading_passkey_credential_authorization_audit"+
                                  (",platform.demo_trading_passkey_credential_completion_audit" if child["relation"] else "")))
