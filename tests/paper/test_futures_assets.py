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


def test_futures_assets_configured_file_reader_uses_acknowledged_private_publication(context, tmp_path):
    from investalo_trading.futures_paper_status import FuturesAssetPublisher
    from test_futures_paper_status import ready
    from test_futures_paper_view import initial, NOW
    settings, _, subject = status_actor(context)
    settings = replace(settings, futures_paper_assets_preview=True, futures_paper_status_root=str(tmp_path))
    genesis = initial(str(context["tenant"]), str(context["account"]))
    with ready(tmp_path / "paper.jsonl", genesis) as saved:
        with FuturesAssetPublisher(tmp_path, saved, clock=lambda: NOW) as publisher:
            publisher.publish(expected_revision=2)
    client = TestClient(main.create_app(settings))
    response = request(client, settings, subject, context["tenant"])
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    value = response.json()
    account = next(a for a in value["accounts"] if a["account_id"] == str(context["account"]))
    assert account["snapshot"]["revision"] == 2
    assert account["snapshot"]["observed_at"] == NOW.isoformat()
    assert not account["snapshot"]["data_fresh"]  # Fixture quote never refreshed by file loading.
    assert sum(a["position"] is not None for a in account["snapshot"]["assets"]) == 3
    assert all(a["snapshot"] is None for a in value["accounts"] if a != account)
    assert not any(word in response.text for word in ("journal_receipt", "state_digest", str(tmp_path)))
    assert request(client, settings, subject, context["foreign"]).status_code == 403


def test_futures_assets_file_reader_missing_preserves_unknown_and_corrupt_is_generic_503(context, tmp_path):
    from investalo_trading.futures_paper_status import FuturesAssetPublisher
    from test_futures_paper_status import ready
    from test_futures_paper_view import initial, NOW
    settings, _, subject = status_actor(context)
    settings = replace(settings, futures_paper_assets_preview=True, futures_paper_status_root=str(tmp_path))
    client = TestClient(main.create_app(settings))
    assert all(a["snapshot"] is None for a in request(client, settings, subject, context["tenant"]).json()["accounts"])
    genesis = initial(str(context["tenant"]), str(context["account"]))
    with ready(tmp_path / "paper.jsonl", genesis) as saved:
        with FuturesAssetPublisher(tmp_path, saved, clock=lambda: NOW) as publisher:
            publisher.publish(expected_revision=2)
    next(tmp_path.glob("*.json")).write_bytes(b"bad private evidence")
    response = request(client, settings, subject, context["tenant"])
    assert response.status_code == 503
    assert response.json() == {"detail": "Futures status unavailable"}
    assert str(tmp_path) not in response.text


def test_futures_assets_status_root_remains_unused_without_preview_opt_in(context, tmp_path):
    settings, _, subject = status_actor(context)
    settings = replace(settings, futures_paper_status_root=str(tmp_path / "missing"))
    client = TestClient(main.create_app(settings))
    assert client.app.state.futures_paper_state_reader is None
    with patch.object(main, "transaction", side_effect=AssertionError("unexpected storage")):
        assert request(client, settings, subject, context["tenant"]).status_code == 404
