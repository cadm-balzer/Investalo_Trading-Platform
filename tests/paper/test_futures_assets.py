"""Authenticated own-account API against the existing restricted fixture LOGIN."""
import base64
from dataclasses import replace
import hmac
import json
from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient
from investalo_api import main
from test_postgres_store import context, status_actor, status_headers

PATH = "/v1/futures-paper-assets"


def own_state(tenant, account):
    from test_futures_paper_view import initial, opened
    return opened(initial(str(tenant), str(account)))


def request(client, settings, subject, tenant):
    template = status_headers(settings, subject, tenant)["Authorization"].removeprefix("Bearer ")
    header, encoded, _ = template.split(".")
    claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    claims["htu"] = PATH
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    prefix = header + "." + payload
    signature = base64.urlsafe_b64encode(
        hmac.digest(settings.internal_key.encode(), prefix.encode(), "sha256")).rstrip(b"=").decode()
    return client.get(PATH, headers={"Authorization": "Bearer " + prefix + "." + signature})


def test_futures_assets_current_actor_scope_and_actual_positions(context):
    settings, _, subject = status_actor(context)
    settings = replace(settings, futures_paper_assets_preview=True)
    state = own_state(context["tenant"], context["account"])
    calls = []
    def reader(tenant, account):
        calls.append((tenant, account))
        return state if account == str(context["account"]) else None
    client = TestClient(main.create_app(settings, futures_paper_state_reader=reader))
    response = request(client, settings, subject, context["tenant"])
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    value = response.json()
    snapshot = next(a for a in value["accounts"] if a["account_id"] == str(context["account"]))["snapshot"]
    assert sum(a["position"] is not None for a in snapshot["assets"]) == 3
    assert snapshot["assets"][0]["next_buy"]["maximum_fill_price"] == "95.00"
    assert all(t == str(context["tenant"]) for t, _ in calls)
    assert not any(word in response.text for word in ("audit_head", "event_ids", "source_digest"))
    assert client.get(PATH).status_code == 401
    assert request(client, settings, subject, context["foreign"]).status_code == 403


def test_futures_assets_missing_reader_preserves_unknown_positions(context):
    settings, _, subject = status_actor(context)
    settings = replace(settings, futures_paper_assets_preview=True)
    client = TestClient(main.create_app(settings))
    response = request(client, settings, subject, context["tenant"])
    assert response.status_code == 200
    assert response.json()["accounts"]
    assert all(a["snapshot"] is None for a in response.json()["accounts"])


def test_futures_assets_foreign_reader_state_is_rejected_without_leak(context):
    settings, _, subject = status_actor(context)
    settings = replace(settings, futures_paper_assets_preview=True)
    for state in (own_state(uuid4(), context["account"]), own_state(context["tenant"], uuid4())):
        client = TestClient(main.create_app(settings, futures_paper_state_reader=lambda *_: state))
        response = request(client, settings, subject, context["tenant"])
        assert response.status_code == 503
        assert response.json() == {"detail": "Futures status unavailable"}
        assert "BITGET" not in response.text


def test_futures_assets_disabled_before_any_storage_or_reader(context):
    settings, _, subject = status_actor(context)
    client = TestClient(main.create_app(settings, futures_paper_state_reader=lambda *_: 1 / 0))
    with patch.object(main, "transaction", side_effect=AssertionError("unexpected DB call")):
        assert request(client, settings, subject, context["tenant"]).status_code == 404
