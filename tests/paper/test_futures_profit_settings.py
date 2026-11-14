"""Actual runtime PG/RLS and normal HTTP reader after journal-backed Q36 growth."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from investalo_api import main
from investalo_workers.futures_account_worker import FuturesAccountWorker
from test_postgres_store import context
from test_futures_settings_postgres import actor, request
from test_futures_account_binding import reader


def test_actual_own_pg_settings_worker_profit_publication_and_api_recommend_four(actor, tmp_path):
    from test_futures_profit_worker import configured_profit, profitable_quotes
    assert request(actor, {"expected_revision": 0, "basket_limit": 7}).status_code == 200
    saved, _, publisher, source, provider, _ = configured_profit(
        str(tmp_path), str(actor["tenant"]), str(actor["account"]))
    try:
        worker = FuturesAccountWorker(source, reader(actor, lambda: provider.now))
        result = profitable_quotes(worker, provider)
        assert result.closures == 3
        before = saved.receipt
        settings = replace(actor["settings"], futures_paper_status_root=str(tmp_path / "status"))
        client = TestClient(main.create_app(settings))
        with patch("investalo_api.futures_paper_settings.datetime",
                   SimpleNamespace(now=lambda *_: provider.now)):
            body = request(actor, client=client).json()
        own = next(a for a in body["accounts"] if a["account_id"] == str(actor["account"]))
        assert (own["runtime_ready"], own["recommendation"], own["basket_limit"]) == (True, 4, 7)
        assert own["capacity"]["funded_capacity"] == 4
        assert own["capacity"]["active_baskets"] == 0
        assert own["capacity"]["range_budget"] == "3333.33333333"
        assert saved.receipt == before
        with actor["admin"]() as db:
            assert db.execute("SELECT count(*) n FROM platform.futures_paper_settings_audit "
                              "WHERE tenant_id=%s", (actor["tenant"],)).fetchone()["n"] == 1
    finally:
        publisher.close()
        saved.close()
