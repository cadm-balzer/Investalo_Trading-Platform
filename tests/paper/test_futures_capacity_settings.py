"""Actual restricted PG/HTTP + same owned v2 publication; synthetic native GET."""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from investalo_api import main
from investalo_trading.futures_paper_status import FuturesAssetPublisher
from investalo_workers.futures_capacity_source import FuturesPaperCapacitySource
from investalo_workers.futures_account_worker import FuturesAccountWorker
from test_futures_settings_postgres import actor, request
from test_postgres_store import context
from test_futures_account_binding import configuration, reader


def started(actor, tmp_path):
    from test_futures_paper_capacity import contracts_payload
    assert request(actor, {"expected_revision": 0, "basket_limit": 3}).status_code == 200
    saved, archive, old_publisher, source, provider = configuration(str(tmp_path), actor)
    old_publisher.close()
    calibration = FuturesPaperCapacitySource(saved, archive, lambda: provider.now,
                                             lambda: contracts_payload(saved.state))
    publisher = FuturesAssetPublisher(tmp_path/"status", saved, clock=lambda: provider.now,
                                     capacity_reader=calibration)
    source = replace(source, publisher=publisher)
    worker = FuturesAccountWorker(source, reader(actor, lambda: provider.now))
    worker.run_once()
    worker.run_once()
    settings = replace(actor["settings"], futures_paper_status_root=str(tmp_path/"status"))
    client = TestClient(main.create_app(settings))
    return saved, publisher, provider, worker, client


def test_actual_file_reader_cash_and_minimums_only_for_own_account_and_fresh_settings(actor, tmp_path):
    saved, publisher, provider, worker, client = started(actor, tmp_path)
    try:
        clock = SimpleNamespace(now=lambda *_: provider.now)
        with patch("investalo_api.futures_paper_settings.datetime", clock):
            values = request(actor, client=client).json()["accounts"]
            own = next(a for a in values if a["account_id"] == str(actor["account"]))
            other = next(a for a in values if a["account_id"] == str(actor["other"]))
            assert (own["runtime_ready"], own["recommendation"], own["capacity"]["active_baskets"]) == (True, 3, 3)
            assert other["capacity"] is None and other["recommendation"] is None
            before = saved.receipt
            saved_setting = request(actor, {"expected_revision": 1, "basket_limit": 7}, client=client)
            assert saved_setting.status_code == 200
            assert saved_setting.json()["accounts"][0]["recommendation_reason"] == "paper_settings_pending"
            assert saved.receipt == before  # API never mutates financial state.
            provider.now += timedelta(seconds=1)
            worker.run_once()
            own = next(a for a in request(actor, client=client).json()["accounts"]
                       if a["account_id"] == str(actor["account"]))
            assert own["recommendation"] == 3 and own["capacity"]["funded_capacity"] == 3
            assert own["basket_limit"] == 7  # Preference cannot invent profit capacity.
            with actor["admin"]() as db:
                assert db.execute("SELECT count(*) n FROM platform.futures_paper_settings_audit "
                                  "WHERE tenant_id=%s", (actor["tenant"],)).fetchone()["n"] == 2
    finally:
        publisher.close()
        saved.close()


def test_stale_paused_foreign_or_broken_capacity_does_not_hide_saved_preference(actor, tmp_path):
    saved, publisher, provider, _, client = started(actor, tmp_path)
    try:
        provider.now += timedelta(seconds=31)
        with patch("investalo_api.futures_paper_settings.datetime", SimpleNamespace(now=lambda *_: provider.now)):
            own = next(a for a in request(actor, client=client).json()["accounts"]
                       if a["account_id"] == str(actor["account"]))
            assert own["recommendation"] is None and own["recommendation_reason"] == "stale_instrument_data"
            with actor["admin"]() as db:
                db.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",
                           (actor["tenant"], actor["account"]))
            own = next(a for a in request(actor, client=client).json()["accounts"]
                       if a["account_id"] == str(actor["account"]))
            assert own["recommendation_reason"] == "account_unavailable"
        assert request(actor, tenant=actor["foreign"], client=client).status_code == 403
        broken = Mock()
        broken.capacity.side_effect = ValueError("private path hidden")
        client = TestClient(main.create_app(actor["settings"], futures_paper_state_reader=broken))
        result = request(actor, {"expected_revision": 1, "basket_limit": 4}, client=client)
        assert result.status_code == 200
        assert result.json()["accounts"][0]["recommendation_reason"] == "capacity_unavailable"
        assert "private path" not in result.text
    finally:
        publisher.close()
        saved.close()
