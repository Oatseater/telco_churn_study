"""Kaplan-Meier retention in Python, mirroring queries/08 and 09.

The SQL files are the source of record for the overall and by-contract curves.
This module exists so the dashboard can recompute the same curve for any
filtered subset (e.g. fiber customers in one segment) without writing dynamic
SQL. tests/test_sql_queries.py checks that both give identical results.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Curves are cut where fewer than this many customers remain at risk: below it a
# single churner moves the curve by several points, which reads as signal but is noise.
MIN_AT_RISK = 30


def kaplan_meier(df: pd.DataFrame, max_month: int | None = None) -> pd.DataFrame:
    """Return tenure_month, at_risk, churned, monthly_churn_hazard, retention."""
    if max_month is None:
        max_month = int(df["tenure_months"].max()) if len(df) else 0
    tenure = df["tenure_months"].to_numpy()
    churned = df["churned"].to_numpy()
    rows = [(0, len(df), 0, 0.0, 1.0)]
    s = 1.0
    for t in range(1, max_month + 1):
        at_risk = int((tenure >= t).sum())
        d = int(((tenure == t) & (churned == 1)).sum())
        h = d / at_risk if at_risk > 0 else np.nan
        s *= 1.0 - (h if at_risk > 0 else 0.0)
        rows.append((t, at_risk, d, h, s))
    return pd.DataFrame(rows, columns=["tenure_month", "at_risk", "churned",
                                       "monthly_churn_hazard", "retention"])


def kaplan_meier_by(df: pd.DataFrame, group_col: str, min_at_risk: int = MIN_AT_RISK) -> pd.DataFrame:
    """KM curve per group, truncated where at_risk falls below min_at_risk."""
    max_month = int(df["tenure_months"].max()) if len(df) else 0
    out = []
    for key, g in df.groupby(group_col, sort=True):
        km = kaplan_meier(g, max_month=max_month)
        km.insert(0, group_col, key)
        out.append(km)
    if not out:
        return pd.DataFrame()
    res = pd.concat(out, ignore_index=True)
    return truncate(res, min_at_risk)


def truncate(km: pd.DataFrame, min_at_risk: int = MIN_AT_RISK) -> pd.DataFrame:
    return km[km["at_risk"] >= min_at_risk].reset_index(drop=True)


def retention_at(km: pd.DataFrame, month: int) -> float:
    row = km.loc[km["tenure_month"] == month, "retention"]
    return float(row.iloc[0]) if len(row) else float("nan")
