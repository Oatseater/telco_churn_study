"""Cleaning: each fix corresponds to an entry in DECISIONS.md."""
from __future__ import annotations

import pandas as pd

from src import config


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()

    # 1. Strip whitespace from every text cell (defensive; the audit reports the count).
    for col in df.columns:
        df[col] = df[col].str.strip()

    # 2. TotalCharges is text with blanks. Blanks occur only for tenure-0 customers,
    #    who have not completed a billing cycle, so the correct value is 0, not a
    #    guess and not a dropped row.
    blank_tc = df["TotalCharges"].eq("")
    assert (df.loc[blank_tc, "tenure"].astype(int) == 0).all(), (
        "Blank TotalCharges found for customers with tenure > 0; the zero-fill rule "
        "no longer holds. Re-audit before cleaning.")
    df.loc[blank_tc, "TotalCharges"] = "0"

    # 3. Cast types explicitly.
    df["SeniorCitizen"] = df["SeniorCitizen"].astype(int)
    df["tenure"] = df["tenure"].astype(int)
    df["MonthlyCharges"] = df["MonthlyCharges"].astype(float)
    df["TotalCharges"] = df["TotalCharges"].astype(float)

    # 4. Consistent snake_case names for SQL.
    df = df.rename(columns=config.RENAME)

    # 5. Binary churn flag for arithmetic; keep the original label for readability.
    df["churned"] = (df["churn_label"] == "Yes").astype(int)

    # 6. Keep "No internet service" / "No phone service" as recorded. They are
    #    informative (the customer does not have the base service). Analyses that
    #    need a yes/no add-on flag handle it explicitly in SQL.

    # 7. Duplicates on every column except ID are kept: IDs are unique and the
    #    repeated profiles are plausible (e.g. new phone-only customers on the same
    #    plan). Removing them would delete real customers.

    # 8. Outliers: none outside the IQR fences; nothing removed or capped.
    return df


def validate_clean(df: pd.DataFrame) -> None:
    """Hard checks that must hold after cleaning; the pipeline stops if any fail."""
    assert df["customer_id"].is_unique, "customer_id must be unique"
    assert df.notna().all().all(), "no nulls allowed after cleaning"
    assert df["tenure_months"].between(0, 1000).all()
    assert (df["monthly_charges"] > 0).all()
    assert (df["total_charges"] >= 0).all()
    assert set(df["churned"].unique()) <= {0, 1}
    assert set(df["contract"].unique()) == {"Month-to-month", "One year", "Two year"}
