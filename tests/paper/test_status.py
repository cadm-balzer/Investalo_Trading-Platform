from datetime import datetime, timezone
import json
from uuid import uuid4

import pytest
from investalo_trading import PaperRunner
from investalo_api.paper_status import publish_rows

NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
TENANT, ACCOUNT = uuid4(), uuid4()


def rows():
    runner = PaperRunner(str(TENANT), str(ACCOUNT))
    c = json.loads(runner.dump(runner.start(NOW)))["checkpoint"]
    state = c["state"]
    return [{
        "account_id": ACCOUNT, "account_name": "Paper", "account_status": "ready",
        "snapshot": {"revision": 0, "observed_at": NOW.isoformat(), "checksum_valid": True,
                     "account": state["account"], "quotes": state["quotes"], "positions": state["baskets"]},
        "journal": [],
    }]


def test_zero_state_and_old_daily_baseline_remain_explicit():
    value = rows()
    result = publish_rows(value, TENANT, now=NOW.replace(day=2))["accounts"][0]["snapshot"]
    assert result["equity"] == result["cash"] == "10000"
    assert result["daily_baseline_ready"] is False
    assert all(p["quantity"] == "0" for p in result["positions"])


def test_unstarted_account_has_no_invented_equity():
    value = rows(); value[0]["snapshot"] = None
    assert publish_rows(value, TENANT, now=NOW)["accounts"][0]["snapshot"] is None


@pytest.mark.parametrize("age,expected,fresh", [(None, None, False), (31, "10100", False), (0, "10100", True)])
def test_held_position_missing_stale_and_fresh_quotes_are_distinct(age, expected, fresh):
    from datetime import timedelta
    value = rows()
    value[0]["snapshot"]["positions"][0].update(quantity="1", entries=[{"principal": "90", "quantity": "1"}])
    if age is not None:
        value[0]["snapshot"]["quotes"] = [{
            "symbol": "BTCUSDT", "observed_at": (NOW-timedelta(seconds=age)).isoformat(),
            "bid": "100", "ask": "101",
        }]
    snapshot = publish_rows(value, TENANT, now=NOW)["accounts"][0]["snapshot"]
    assert snapshot["equity"] == expected and snapshot["valuation_fresh"] is fresh


def test_private_text_and_unknown_domain_events_do_not_escape():
    value = rows()
    value[0]["snapshot"]["revision"] = 1
    value[0]["journal"] = [{
        "revision": 1, "at": NOW.isoformat(), "input_kind": "quote", "fill_count": 1,
        "events": [{"kind": "entry_blocked", "reason": "private-note", "reference": "private-key"},
                   {"kind": "private-note", "symbol": "private-note"}],
    }]
    published = publish_rows(value, TENANT, now=NOW)
    assert "private-" not in json.dumps(published)
    assert published["accounts"][0]["journal"][0]["messages"] == ["Einstieg blockiert."]


@pytest.mark.parametrize("change", [
    lambda x: x[0]["snapshot"].update(checksum_valid=False),
    lambda x: x[0]["snapshot"]["account"].update(tenant_id=str(ACCOUNT)),
    lambda x: x[0]["snapshot"]["account"].update(cash="NaN"),
    lambda x: x[0]["snapshot"]["positions"][0].update(quantity="-1"),
    lambda x: x[0]["snapshot"]["positions"].reverse(),
    lambda x: x[0]["snapshot"].update(revision=-1),
])
def test_corrupt_or_cross_actor_state_rejected(change):
    value = rows(); change(value)
    with pytest.raises((ValueError, KeyError)):
        publish_rows(value, TENANT, now=NOW)
