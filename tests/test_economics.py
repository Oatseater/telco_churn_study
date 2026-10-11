"""The scenario calculator's arithmetic."""
import math

import numpy as np
import pytest

from src import database, economics as ec

SEG = ec.SegmentEconomics(segment="Test", customers=1000, churn_rate=0.4,
                          avg_charge_churned=80.0, avg_charge_retained=60.0)


def test_zero_discount_costs_nothing():
    r = ec.run_scenario(SEG, discount=0.0, save_rate=0.3)
    assert r.discount_cost == 0
    assert r.net_benefit == pytest.approx(r.revenue_saved)


def test_zero_save_rate_loses_the_stayer_subsidy():
    r = ec.run_scenario(SEG, discount=0.1, save_rate=0.0)
    assert r.revenue_saved == 0
    assert r.net_benefit == pytest.approx(-0.1 * 12 * 600 * 60.0)


def test_hand_calculation():
    r = ec.run_scenario(SEG, discount=0.2, save_rate=0.25, stayer_uptake=0.5, horizon_months=12)
    saved = 1000 * 0.4 * 0.25                      # 100 customers
    revenue = saved * 80 * 12                      # 96,000
    cost = 0.2 * 12 * (saved * 80 + 0.5 * 600 * 60)  # 0.2*12*(8,000+18,000) = 62,400
    assert r.customers_saved == pytest.approx(saved)
    assert r.revenue_saved == pytest.approx(revenue)
    assert r.discount_cost == pytest.approx(cost)
    assert r.net_benefit == pytest.approx(revenue - cost)


def test_break_even_save_rate_gives_zero_net():
    r = ec.run_scenario(SEG, discount=0.15, save_rate=0.25)
    assert r.break_even_save_rate is not None
    r0 = ec.run_scenario(SEG, discount=0.15, save_rate=r.break_even_save_rate)
    assert r0.net_benefit == pytest.approx(0, abs=1e-6)


def test_unreachable_break_even_is_none():
    low = ec.SegmentEconomics("Low", 1000, 0.02, 40.0, 40.0)
    assert ec.run_scenario(low, 0.3, 0.5).break_even_save_rate is None


@pytest.mark.parametrize("bad", [(-0.1, 0.2), (0.2, 1.5)])
def test_inputs_validated(bad):
    with pytest.raises(ValueError):
        ec.run_scenario(SEG, *bad)


def test_customer_level_economics_match_sql_summary(profile):
    summary = database.run_query_file("10_segment_summary.sql")
    from_sql = ec.segment_economics(summary)
    for seg, e in from_sql.items():
        e2 = ec.economics_from_customers(profile, seg)
        assert e2.customers == e.customers
        assert math.isclose(e2.churn_rate, e.churn_rate)
        assert math.isclose(e2.avg_charge_churned, e.avg_charge_churned)
        assert math.isclose(e2.avg_charge_retained, e.avg_charge_retained)


def test_month_to_month_filter_is_subset(profile):
    seg = "Established Full Bundle"
    full = ec.economics_from_customers(profile, seg)
    mtm = ec.economics_from_customers(profile, seg, month_to_month_only=True)
    assert 0 < mtm.customers < full.customers
    assert mtm.churn_rate > full.churn_rate
