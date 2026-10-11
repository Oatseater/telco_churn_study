"""Baseline churn model: logistic regression only.

Purpose: confirm which factors are associated with churn when looked at
together, in plain English. It is not tuned and not meant for production scoring.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             roc_auc_score)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from src import config

# Categorical features and the reference level each is compared against.
CATEGORICAL_REFERENCES = {
    "contract": "Month-to-month",
    "internet_service": "DSL",
    "payment_method": "Bank transfer (automatic)",
}
BINARY_FEATURES = {
    # column: (value treated as 1, plain-English label)
    "senior_citizen": (1, "Is a senior citizen"),
    "partner": ("Yes", "Has a partner"),
    "dependents": ("Yes", "Has dependents"),
    "paperless_billing": ("Yes", "Uses paperless billing"),
    "phone_service": ("Yes", "Has phone service"),
    "multiple_lines": ("Yes", "Has multiple lines"),
    "online_security": ("Yes", "Has online security"),
    "online_backup": ("Yes", "Has online backup"),
    "device_protection": ("Yes", "Has device protection"),
    "tech_support": ("Yes", "Has tech support"),
    "streaming_tv": ("Yes", "Has streaming TV"),
    "streaming_movies": ("Yes", "Has streaming movies"),
}
# Numeric features and the unit used to explain them.
NUMERIC_FEATURES = {
    "tenure_months": (12, "Each extra 12 months of tenure"),
}
EXCLUDED = {
    "customer_id": "identifier",
    "gender": "protected attribute; no business case for using it to target offers",
    "total_charges": "almost exactly tenure x monthly charge, so it duplicates information already in the model",
    "monthly_charges": "almost entirely determined by which services a customer holds (see services_explain_charges_r2); "
                       "keeping both makes their coefficients fight each other and flip sign",
}


def services_explain_charges_r2(df: pd.DataFrame) -> float:
    """R-squared of monthly charge regressed on the service flags: evidence for dropping it."""
    from sklearn.linear_model import LinearRegression
    X, _ = build_features(df)
    service_cols = [c for c in X.columns
                    if c in ("phone_service", "multiple_lines", *config.ADDON_COLUMNS)
                    or c.startswith("internet_service=")]
    lr = LinearRegression().fit(X[service_cols], df["monthly_charges"])
    return float(lr.score(X[service_cols], df["monthly_charges"]))


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    X = pd.DataFrame(index=df.index)
    labels: dict[str, str] = {}
    for col, (unit, label) in NUMERIC_FEATURES.items():
        X[col] = df[col].astype(float)
        labels[col] = label
    for col, (pos, label) in BINARY_FEATURES.items():
        X[col] = (df[col] == pos).astype(int)
        labels[col] = label
    for col, ref in CATEGORICAL_REFERENCES.items():
        for level in sorted(df[col].unique()):
            if level == ref:
                continue
            name = f"{col}={level}"
            X[name] = (df[col] == level).astype(int)
            pretty_col = col.replace("_", " ")
            labels[name] = f"{pretty_col.capitalize()}: {level} (vs {ref})"
    return X, labels


def _odds_sentence(label: str, odds_ratio: float) -> str:
    if abs(odds_ratio - 1) < 0.10:
        return f"{label}: little difference in the odds of churning"
    if odds_ratio >= 1:
        return f"{label}: odds of churning {odds_ratio:.2f}x higher"
    return f"{label}: odds of churning {(1 - odds_ratio):.0%} lower"


def train_baseline(df: pd.DataFrame) -> dict:
    X, labels = build_features(df)
    y = df["churned"].astype(int)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.TEST_SIZE, stratify=y, random_state=config.RANDOM_STATE)

    # Scale numeric columns only, so binary coefficients stay interpretable as
    # "has it vs does not". Scaling helps the solver converge.
    num_cols = list(NUMERIC_FEATURES)
    scaler = StandardScaler().fit(X_train[num_cols])
    Xtr, Xte = X_train.copy(), X_test.copy()
    Xtr[num_cols] = scaler.transform(X_train[num_cols])
    Xte[num_cols] = scaler.transform(X_test[num_cols])

    model = LogisticRegression(max_iter=1000)
    model.fit(Xtr, y_train)
    proba = model.predict_proba(Xte)[:, 1]
    pred = (proba >= 0.5).astype(int)

    # Comparison points so the model's value is judged honestly.
    rule_score = (X_test["contract=One year"] == 0) & (X_test["contract=Two year"] == 0)
    auc_contract_rule = roc_auc_score(y_test, rule_score.astype(int))
    majority_acc = max(y_test.mean(), 1 - y_test.mean())

    # Lift: churn rate in the top 10% of predicted risk vs the test-set average.
    order = np.argsort(-proba)
    top_n = int(np.ceil(0.10 * len(proba)))
    top_decile_rate = float(y_test.to_numpy()[order[:top_n]].mean())

    # Convert coefficients back to interpretable units.
    drivers = []
    for i, col in enumerate(X.columns):
        coef = float(model.coef_[0][i])
        if col in NUMERIC_FEATURES:
            unit = NUMERIC_FEATURES[col][0]
            sd = float(scaler.scale_[num_cols.index(col)])
            coef_unit = coef / sd * unit
        else:
            coef_unit = coef
        orr = float(np.exp(coef_unit))
        drivers.append({
            "feature": col,
            "label": labels[col],
            "coefficient": coef_unit,
            "odds_ratio": orr,
            "direction": "raises risk" if orr >= 1 else "lowers risk",
            "plain_english": _odds_sentence(labels[col], orr),
        })
    drivers.sort(key=lambda d: abs(np.log(d["odds_ratio"])), reverse=True)

    return {
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "test_churn_rate": float(y_test.mean()),
        "metric_name": "ROC AUC",
        "roc_auc": float(roc_auc_score(y_test, proba)),
        "roc_auc_contract_rule": float(auc_contract_rule),
        "accuracy": float(accuracy_score(y_test, pred)),
        "majority_class_accuracy": float(majority_acc),
        "precision_at_0_5": float(precision_score(y_test, pred)),
        "recall_at_0_5": float(recall_score(y_test, pred)),
        "top_decile_churn_rate": top_decile_rate,
        "top_decile_lift": top_decile_rate / float(y_test.mean()),
        "excluded_features": EXCLUDED,
        "drivers": drivers,
    }
