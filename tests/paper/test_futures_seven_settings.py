"""Actual restricted PG/settings + ordinary file API with seven native Paper axes."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from investalo_api import main
from investalo_workers.futures_account_worker import FuturesAccountWorker
from test_postgres_store import context
from test_futures_settings_postgres import actor, request
from test_futures_account_binding import reader
from test_futures_assets import request as assets_request


def test_actual_pg_worker_seven_assets_but_three_funded_ranges(actor, tmp_path):
    from test_futures_seven_candidates import configured_seven, SEVEN_SYMBOLS
    assert request(actor, {"expected_revision": 0, "basket_limit": 7}).status_code == 200
    journal, _, publisher, source, provider, _ = configured_seven(
        tmp_path, str(actor["tenant"]), str(actor["account"]))
    try:
        worker = FuturesAccountWorker(source, reader(actor, lambda: provider.now))
        assert worker.run_once().outcome == "warmed"
        assert worker.run_once().entries == 3
        before = journal.receipt
        settings = replace(actor["settings"], futures_paper_status_root=str(tmp_path / "status"),
                           futures_paper_assets_preview=True)
        client = TestClient(main.create_app(settings))
        clock = SimpleNamespace(now=lambda *_: provider.now)
        with patch("investalo_api.futures_paper_settings.datetime", clock), \
                patch("investalo_api.futures_paper_assets.datetime", clock):
            body = request(actor, client=client).json()
            own = next(a for a in body["accounts"] if a["account_id"] == str(actor["account"]))
            assert (own["runtime_ready"], own["recommendation"], own["basket_limit"]) == (True, 3, 7)
            assert own["capacity"]["funded_capacity"] == 3
            assert own["capacity"]["eligible_assets"] == 7
            response = assets_request(client, settings, actor["subject"], actor["tenant"])
            assert response.status_code == 200
            values = response.json()["accounts"]
            own = next(a for a in values if a["account_id"] == str(actor["account"]))["snapshot"]
            assert tuple(a["symbol"] for a in own["assets"]) == SEVEN_SYMBOLS
            assert len(own["assets"]) == 7
            assert sum(a["position"] is not None for a in own["assets"]) == 3
            assert next(a for a in values if a["account_id"] == str(actor["other"]))["snapshot"] is None
        assert journal.receipt == before  # Neither HTTP reader changes the financial state.
        with actor["admin"]() as db:
            assert db.execute("SELECT count(*) n FROM platform.futures_paper_settings_audit "
                              "WHERE tenant_id=%s", (actor["tenant"],)).fetchone()["n"] == 1
    finally:
        publisher.close()
        journal.close()
