"""Every SQL file runs and returns rows; key results reconcile with each other
and with the Python mirror used by the dashboard."""
import numpy as np
import pandas as pd
import pytest

from src import database, retention

QUERY_FILES = database.query_files()


def test_there_are_query_files():
    assert len(QUERY_FILES) >= 10


@pytest.mark.parametrize("path", QUERY_FILES, ids=[p.name for p in QUERY_FILES])
def test_query_runs_and_returns_rows(path):
    df = database.run_query_file(path)
    assert len(df) > 0, f"{path.name} returned no rows"
    assert df.notna().any().all(), f"{path.name} has an all-null column"


@pytest.mark.parametrize("path", QUERY_FILES, ids=[p.name for p in QUERY_FILES])
def test_query_states_its_business_question(path):
    assert database.business_question(path), f"{path.name} lacks a '-- Business question:' header"


DIMENSION_QUERIES = [
    "02_churn_by_contract.sql", "03_churn_by_tenure_bucket.sql",
    "04_churn_by_payment_method.sql", "05_churn_by_internet_service.sql",
    "07_churn_by_service_count.sql", "10_segment_summary.sql",
]


@pytest.mark.parametrize("name", DIMENSION_QUERIES)
def test_breakdowns_reconcile_to_overall(name):
    overall = database.run_query_file("01_overall_churn.sql").iloc[0]
    df = database.run_query_file(name)
    assert df["customers"].sum() == overall["customers"]
    assert df["churned"].sum() == overall["churned"]
    if "annual_revenue_at_risk" in df:
        assert np.isclose(df["annual_revenue_at_risk"].sum(), overall["annual_revenue_at_risk"])
    if "share_of_customers" in df:
        assert np.isclose(df["share_of_customers"].sum(), 1.0)


def test_overall_churn_matches_pandas(customers):
    overall = database.run_query_file("01_overall_churn.sql").iloc[0]
    assert overall["customers"] == len(customers)
    assert np.isclose(overall["churn_rate"], customers["churned"].mean())
    churned_rev = customers.loc[customers["churned"] == 1, "monthly_charges"].sum() * 12
    assert np.isclose(overall["annual_revenue_at_risk"], churned_rev)


def test_addon_query_counts_internet_customers_only(customers):
    df = database.run_query_file("06_churn_by_addon_service.sql")
    n_internet = int((customers["internet_service"] != "No").sum())
    assert ((df["customers_with"] + df["customers_without"]) == n_internet).all()


def test_retention_sql_matches_python_overall(customers):
    sql = database.run_query_file("08_retention_curve_overall.sql")
    py = retention.kaplan_meier(customers)
    assert len(sql) == len(py)
    assert np.allclose(sql["retention"], py["retention"])
    assert (sql["at_risk"].to_numpy() == py["at_risk"].to_numpy()).all()


def test_retention_sql_matches_python_by_contract(customers):
    sql = database.run_query_file("09_retention_curve_by_contract.sql")
    for contract, g in customers.groupby("contract"):
        py = retention.kaplan_meier(g, max_month=int(customers["tenure_months"].max()))
        s = sql[sql["contract"] == contract].reset_index(drop=True)
        assert np.allclose(s["retention"], py["retention"]), contract


def test_retention_is_monotone_non_increasing():
    sql = database.run_query_file("08_retention_curve_overall.sql")
    assert (np.diff(sql["retention"]) <= 1e-12).all()
    assert sql["retention"].iloc[0] == 1.0
