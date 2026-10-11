"""Data integrity: the raw file, the cleaned table and the SQLite load agree."""
import pandas as pd
import pytest

from src import audit, clean, config, database


def test_raw_file_exists_with_expected_schema():
    raw = audit.load_raw()
    assert list(raw.columns) == config.EXPECTED_COLUMNS
    assert len(raw) > 0


def test_schema_guard_stops_on_wrong_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("customerID,gender\nA,Male\n", encoding="utf-8")
    with pytest.raises(audit.SchemaError):
        audit.load_raw(bad)


def test_schema_guard_stops_on_missing_file(tmp_path):
    with pytest.raises(audit.SchemaError):
        audit.load_raw(tmp_path / "missing.csv")


def test_row_counts_match_through_pipeline(customers):
    raw = audit.load_raw()
    cleaned = pd.read_csv(config.CLEAN_CSV)
    assert len(raw) == len(cleaned) == len(customers), "no rows may be lost or added"


def test_customer_id_unique(customers):
    assert customers["customer_id"].is_unique


def test_no_nulls_after_cleaning(customers):
    assert customers.notna().all().all()


def test_total_charges_numeric_and_zero_only_for_new_customers(customers):
    assert pd.api.types.is_float_dtype(customers["total_charges"])
    zero = customers["total_charges"] == 0
    assert (customers.loc[zero, "tenure_months"] == 0).all()
    assert (customers.loc[customers["tenure_months"] > 0, "total_charges"] > 0).all()


def test_blank_total_charges_were_all_tenure_zero():
    raw = audit.load_raw()
    blanks = raw["TotalCharges"].str.strip().eq("")
    assert blanks.sum() > 0
    assert (raw.loc[blanks, "tenure"].astype(int) == 0).all()


def test_churn_flag_matches_label(customers):
    assert set(customers["churned"].unique()) == {0, 1}
    assert ((customers["churned"] == 1) == (customers["churn_label"] == "Yes")).all()


def test_value_ranges(customers):
    assert customers["tenure_months"].between(0, 72).all()
    assert (customers["monthly_charges"] > 0).all()
    assert set(customers["senior_citizen"].unique()) <= {0, 1}


def test_clean_is_deterministic():
    raw = audit.load_raw()
    a, b = clean.clean(raw), clean.clean(raw)
    pd.testing.assert_frame_equal(a, b)


def test_service_counts_in_range(profile):
    assert profile["n_services"].between(0, 9).all()
    assert profile["n_addons"].between(0, 6).all()
    assert (profile["n_addons"] <= profile["n_services"]).all()


def test_every_customer_in_exactly_one_known_segment(profile):
    assert profile["segment"].notna().all()
    assert set(profile["segment"]) == set(config.SEGMENT_ORDER)


def test_sql_segment_rules_match_config_thresholds(profile):
    """The SQL view and the documented thresholds in config.py must not drift apart."""
    new = profile["tenure_months"] <= config.NEW_CUSTOMER_MAX_TENURE
    high = profile["monthly_charges"] >= config.HIGH_SPEND_MIN_MONTHLY
    full = profile["n_services"] >= config.FULL_BUNDLE_MIN_SERVICES
    expected = pd.Series("Established Low-Spend", index=profile.index)
    expected[~new & high & full] = "Established Full Bundle"
    expected[~new & high & ~full] = "Established Thin Bundle"
    expected[new & ~high] = "New Standard"
    expected[new & high] = "New High-Spend"
    assert (expected == profile["segment"]).all()


def test_sqlite_has_expected_objects():
    tables = database.read_table("SELECT name, type FROM sqlite_master")
    names = set(tables["name"])
    assert {"customers", "customer_profile"} <= names
