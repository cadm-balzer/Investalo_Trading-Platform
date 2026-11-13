from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest
from investalo_trading.futures_capacity import CapacityEvidence, recommend_capacity

NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)


def evidence(**values):
    return replace(CapacityEvidence(NOW, D("10000"), D(0), 0, 5, D("1500"), D("2000"), 5), **values)


def test_capacity_changes_follow_actual_cash_full_ranges_and_separate_profit_epoch():
    x = recommend_capacity(evidence(), 7, now=NOW)
    assert (x.recommended_limit, x.additional_baskets, x.new_range_budget) == (5, 5, D("2000"))
    # A preference of7 cannot finance two new ranges or release a profit epoch.
    x = recommend_capacity(evidence(unposted_cash=D("4000")), 7, now=NOW)
    assert x.recommended_limit is None and x.additional_baskets == 0
    x = recommend_capacity(evidence(unposted_cash=D("14000"), funded_capacity=7, eligible_assets=7), 7, now=NOW)
    assert (x.recommended_limit, x.additional_baskets, x.new_range_budget) == (7, 7, D("2000"))


def test_more_slots_require_more_eligible_assets_even_with_ample_cash():
    x = recommend_capacity(evidence(unposted_cash=D("14000"), funded_capacity=7), 7, now=NOW)
    assert x.recommended_limit == 5
    x = recommend_capacity(evidence(eligible_assets=2), 5, now=NOW)
    assert x.reason == "candidate_pool_insufficient" and x.recommended_limit is None


def test_free_profit_does_not_resize_an_unreleased_budget_epoch():
    x = recommend_capacity(evidence(unposted_cash=D("15000")), 7, now=NOW)
    assert x.recommended_limit == 5 and x.new_range_budget == D("2000")
    assert x.new_range_budget*x.additional_baskets == D("10000")
    x = recommend_capacity(evidence(unposted_cash=D("16000"), funded_capacity=7,
                                   eligible_assets=7, funded_range_budget=D("2200")), 7, now=NOW)
    assert x.recommended_limit == 7 and x.new_range_budget == D("2200")


def test_full_open_regular_manual_and_cost_reserves_remain_unavailable():
    x = evidence(unposted_cash=D("7000"), reserved_unposted_cash=D("3500"), active_baskets=2)
    result = recommend_capacity(x, 5, now=NOW)
    assert (result.free_cash, result.recommended_limit, result.additional_baskets,
            result.new_range_budget) == (D("3500"), 3, 1, D("2000"))
    # One full epoch range, never two resized/smaller ranges or reserved cash.
    assert x.reserved_unposted_cash == D("3500")


def test_lower_limit_never_resizes_or_forces_closure():
    x = recommend_capacity(evidence(active_baskets=5, reserved_unposted_cash=D("9000")), 3, now=NOW)
    assert (x.recommended_limit, x.additional_baskets, x.new_range_budget, x.reason) == (
        3, 0, None, "await_basket_closure")


def test_cash_rounding_cannot_overallocate_or_round_below_minimum_range():
    x = recommend_capacity(evidence(unposted_cash=D("10"), minimum_full_range=D("1"),
                                   funded_range_budget=D("3.33333333")), 3, now=NOW)
    assert x.new_range_budget == D("3.33333333")
    assert x.new_range_budget*x.additional_baskets <= x.free_cash
    x = recommend_capacity(evidence(unposted_cash=D("3.000000003"),
                                   minimum_full_range=D("1.000000001"),
                                   funded_range_budget=D("1")), 3, now=NOW)
    assert x.recommended_limit is None and x.reason == "range_below_market_minimum"


@pytest.mark.parametrize("change,reason", [
    ({"observed_at": NOW-timedelta(seconds=31)}, "stale_futures_cash"),
    ({"observed_at": NOW+timedelta(seconds=1)}, "stale_futures_cash"),
    ({"reserved_unposted_cash": D("10000.01")}, "reserved_cash_shortfall"),
])
def test_stale_future_and_underbacked_accounts_have_no_new_entry_recommendation(change, reason):
    x = recommend_capacity(evidence(**change), 5, now=NOW)
    assert x.reason == reason and x.recommended_limit is None and x.additional_baskets == 0


@pytest.mark.parametrize("change", [
    {"unposted_cash": D("-1")}, {"reserved_unposted_cash": D("-1")},
    {"minimum_full_range": D("NaN")}, {"minimum_full_range": D("0")},
    {"active_baskets": True}, {"funded_capacity": 8}, {"eligible_assets": True},
    {"funded_range_budget": D("1.000000001")},
])
def test_invalid_cash_and_capacity_cannot_produce_a_recommendation(change):
    with pytest.raises(ValueError):
        evidence(**change)
