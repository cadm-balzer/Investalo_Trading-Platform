"""Actual restricted API LOGIN and fixture-only013, with synthetic identities."""
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import hmac
import json
import time
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from investalo_api import main
from test_postgres_store import context, status_actor


@pytest.fixture
def actor(context):
    settings, user, subject = status_actor(context)
    settings = replace(settings, futures_paper_settings_preview=True)
    with context["admin"]() as db:
        assert db.execute("SELECT 1 FROM platform.schema_migrations WHERE version='013_futures_paper_settings'").fetchone()
        db.execute("UPDATE platform.memberships SET role='trader' WHERE tenant_id=%s AND user_id=%s",
                   (context["tenant"], user))
    return {**context, "settings": settings, "user": user, "subject": subject,
            "client": TestClient(main.create_app(settings))}


def request(a, body=None, *, account=None, tenant=None, client=None):
    target = "/v1/futures-paper-settings"
    method = "GET"
    raw = b""
    if body is not None:
        target += "/"+str(account or a["account"])
        method, raw = "POST", json.dumps(body).encode()
    now = int(time.time())
    claims = {"iss": "investalo-bff", "aud": "investalo-api", "sub": a["subject"],
              "oidc_iss": a["settings"].oidc_issuer, "iat": now, "exp": now+30,
              "oidc_auth_time": now, "jti": str(uuid4()), "tenant_id": str(tenant or a["tenant"]),
              "auth_epoch": 0, "htm": method, "htu": target,
              "body_sha256": hashlib.sha256(raw).hexdigest()}
    encode = lambda v: base64.urlsafe_b64encode(json.dumps(v).encode()).rstrip(b"=").decode()
    prefix = encode({"alg": "HS256", "typ": "JWT"})+"."+encode(claims)
    signature = base64.urlsafe_b64encode(hmac.digest(a["settings"].internal_key.encode(),
                                          prefix.encode(), "sha256")).rstrip(b"=").decode()
    return (client or a["client"]).request(method, target, content=raw,
        headers={"Authorization": "Bearer "+prefix+"."+signature, "Content-Type": "application/json"})


def test_save_restart_read_and_audit_are_atomic_without_invented_futures_cash(actor):
    before = request(actor).json()
    assert {a["account_id"] for a in before["accounts"]} == {str(actor["account"]), str(actor["other"])}
    assert all(a["recommendation"] is None and a["runtime_ready"] is False for a in before["accounts"])
    saved = request(actor, {"expected_revision": 0, "basket_limit": 3})
    assert saved.status_code == 200
    assert saved.json()["accounts"][0]["revision"] == 1
    restarted = TestClient(main.create_app(actor["settings"]))
    a = next(a for a in request(actor, client=restarted).json()["accounts"] if a["account_id"] == str(actor["account"]))
    assert a["basket_limit"] == 3 and a["saved"]
    with actor["admin"]() as db:
        rows = db.execute("SELECT revision,basket_limit,actor_id FROM platform.futures_paper_settings_audit "
                          "WHERE tenant_id=%s AND account_id=%s", (actor["tenant"], actor["account"])).fetchall()
    assert rows == [{"revision": 1, "basket_limit": 3, "actor_id": actor["user"]}]


def test_concurrent_tabs_only_one_revision_wins(actor):
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda n: request(actor, {"expected_revision": 0, "basket_limit": n}), [3, 7]))
    assert sorted(r.status_code for r in responses) == [200, 409]
    with actor["admin"]() as db:
        assert db.execute("SELECT count(*) n FROM platform.futures_paper_settings_audit WHERE tenant_id=%s",
                          (actor["tenant"],)).fetchone()["n"] == 1


def test_foreign_account_membership_viewer_and_non_usdt_writes_rejected(actor):
    assert request(actor, {"expected_revision": 0, "basket_limit": 5}, account=actor["foreign_account"]).status_code == 404
    assert request(actor, tenant=actor["foreign"]).status_code == 403
    with actor["admin"]() as db:
        db.execute("UPDATE platform.accounts SET currency='EUR' WHERE tenant_id=%s AND id=%s",
                   (actor["tenant"], actor["other"]))
    assert request(actor, {"expected_revision": 0, "basket_limit": 5}, account=actor["other"]).status_code == 404
    with actor["admin"]() as db:
        db.execute("UPDATE platform.memberships SET role='viewer' WHERE tenant_id=%s AND user_id=%s",
                   (actor["tenant"], actor["user"]))
    assert request(actor).status_code == 200
    assert all(not a["can_edit"] for a in request(actor).json()["accounts"])
    assert request(actor, {"expected_revision": 0, "basket_limit": 5}).status_code == 403


@pytest.mark.parametrize("body", [
    {"expected_revision": 0, "basket_limit": True},
    {"expected_revision": 0, "basket_limit": "5"},
    {"expected_revision": 0, "basket_limit": 8},
    {"expected_revision": -1, "basket_limit": 5},
    {"expected_revision": 0, "basket_limit": 5, "cash": "100000"},
    {"expected_revision": 0, "basket_limit": 5, "live_enabled": True},
])
def test_browser_cannot_supply_balance_leverage_or_live_authority(actor, body):
    assert request(actor, body).status_code == 422


def test_unknown_response_after_committed_write_requires_readback_not_retry(actor, monkeypatch):
    original = main.transaction
    fail = [True]
    @contextmanager
    def lost_response(*args, **kwargs):
        with original(*args, **kwargs) as context:
            yield context
        if fail[0]:
            fail[0] = False
            raise HTTPException(503, "Service unavailable")
    monkeypatch.setattr(main, "transaction", lost_response)
    body = {"expected_revision": 0, "basket_limit": 4}
    assert request(actor, body).status_code == 503
    assert request(actor, body).status_code == 409
    saved = next(a for a in request(actor).json()["accounts"] if a["account_id"] == str(actor["account"]))
    assert saved["revision"] == 1 and saved["basket_limit"] == 4


def test_missing_audit_write_rolls_back_settings_and_default_off_stays_off(actor):
    # Existing audit key causes the final INSERT to fail; settings must roll back.
    with actor["admin"]() as db:
        db.execute("INSERT INTO platform.futures_paper_settings_audit "
                   "(tenant_id,account_id,revision,actor_id,basket_limit) VALUES(%s,%s,1,%s,5)",
                   (actor["tenant"], actor["account"], actor["user"]))
    assert request(actor, {"expected_revision": 0, "basket_limit": 4}).status_code == 503
    assert all(a["revision"] == 0 for a in request(actor).json()["accounts"])
    disabled = TestClient(main.create_app(replace(actor["settings"], futures_paper_settings_preview=False)))
    assert request(actor, client=disabled).status_code == 404
    assert request(actor, {"expected_revision": 0, "basket_limit": 5}, client=disabled).status_code == 404
