"""Central configuration: paths, expected schema, segment definitions and scenario defaults.

Nothing in this file is a finding. Thresholds and scenario defaults are design
choices or assumptions; every reported number is computed from the data.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RAW_CSV = ROOT / "data" / "raw" / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
PROCESSED_DIR = ROOT / "data" / "processed"
CLEAN_CSV = PROCESSED_DIR / "telco_clean.csv"
DB_PATH = PROCESSED_DIR / "churn.db"
QUERIES_DIR = ROOT / "queries"
SCHEMA_SQL = ROOT / "src" / "schema.sql"
REPORTS_DIR = ROOT / "reports"
QUERY_RESULTS_DIR = REPORTS_DIR / "query_results"
METRICS_JSON = REPORTS_DIR / "metrics.json"
AUDIT_REPORT = REPORTS_DIR / "audit_report.md"
TEMPLATES_DIR = ROOT / "templates"
ASSETS_DIR = ROOT / "assets"

# The exact columns of the public IBM Telco Customer Churn file. If the file
# differs, the pipeline stops rather than guessing.
EXPECTED_COLUMNS = [
    "customerID", "gender", "SeniorCitizen", "Partner", "Dependents", "tenure",
    "PhoneService", "MultipleLines", "InternetService", "OnlineSecurity",
    "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV",
    "StreamingMovies", "Contract", "PaperlessBilling", "PaymentMethod",
    "MonthlyCharges", "TotalCharges", "Churn",
]

RENAME = {
    "customerID": "customer_id",
    "gender": "gender",
    "SeniorCitizen": "senior_citizen",
    "Partner": "partner",
    "Dependents": "dependents",
    "tenure": "tenure_months",
    "PhoneService": "phone_service",
    "MultipleLines": "multiple_lines",
    "InternetService": "internet_service",
    "OnlineSecurity": "online_security",
    "OnlineBackup": "online_backup",
    "DeviceProtection": "device_protection",
    "TechSupport": "tech_support",
    "StreamingTV": "streaming_tv",
    "StreamingMovies": "streaming_movies",
    "Contract": "contract",
    "PaperlessBilling": "paperless_billing",
    "PaymentMethod": "payment_method",
    "MonthlyCharges": "monthly_charges",
    "TotalCharges": "total_charges",
    "Churn": "churn_label",
}

ADDON_COLUMNS = [
    "online_security", "online_backup", "device_protection",
    "tech_support", "streaming_tv", "streaming_movies",
]

ADDON_LABELS = {
    "online_security": "Online security",
    "online_backup": "Online backup",
    "device_protection": "Device protection",
    "tech_support": "Tech support",
    "streaming_tv": "Streaming TV",
    "streaming_movies": "Streaming movies",
}

# ---------------------------------------------------------------------------
# Segment rules. The SQL implementation lives in src/schema.sql (view
# customer_profile); these constants document it and are checked against it
# in tests/test_data_integrity.py so the two cannot drift apart.
# ---------------------------------------------------------------------------
NEW_CUSTOMER_MAX_TENURE = 11      # tenure 0-11 months = first year
HIGH_SPEND_MIN_MONTHLY = 70.0     # close to the median monthly charge, rounded
FULL_BUNDLE_MIN_SERVICES = 5      # out of 9 possible services

SEGMENT_ORDER = [
    "New High-Spend",
    "New Standard",
    "Established Thin Bundle",
    "Established Full Bundle",
    "Established Low-Spend",
]

_T = NEW_CUSTOMER_MAX_TENURE + 1
_V = f"${HIGH_SPEND_MIN_MONTHLY:,.0f}"
_E = FULL_BUNDLE_MIN_SERVICES

SEGMENTS = {
    "New High-Spend": {
        "rule": f"Tenure under {_T} months and monthly charge of {_V} or more",
        "action": (
            "Spend here first. Offer a discount for moving from month-to-month to a one-year "
            "contract while they are still in their first year. When to make the offer: [PLACEHOLDER]."
        ),
    },
    "New Standard": {
        "rule": f"Tenure under {_T} months and monthly charge under {_V}",
        "action": (
            "Cheap onboarding, not discounts. A setup check and a free trial of tech support "
            "or online security."
        ),
    },
    "Established Thin Bundle": {
        "rule": f"Tenure {_T} months or more, monthly charge of {_V} or more, {_E - 1} or fewer services",
        "action": (
            "Paying a lot for not much. Check the plan fits. Add security or support at no extra "
            "cost so the bill feels worth it."
        ),
    },
    "Established Full Bundle": {
        "rule": f"Tenure {_T} months or more, monthly charge of {_V} or more, {_E} or more services",
        "action": (
            "The most valuable group. Don't discount. Look after them and get in touch before "
            "contracts come up for renewal."
        ),
    },
    "Established Low-Spend": {
        "rule": f"Tenure {_T} months or more and monthly charge under {_V}",
        "action": (
            "Stable and cheap to keep. Spend little. Try selling one add-on through the bill."
        ),
    },
}


# ---------------------------------------------------------------------------
# Money layer assumptions. These are assumptions, not findings; they are
# shown on screen and in the memo wherever they are used.
# ---------------------------------------------------------------------------
HORIZON_MONTHS = 12               # revenue at risk and scenario benefits use a 12-month horizon
DEFAULT_DISCOUNT = 0.15           # 15% off the monthly bill
DEFAULT_SAVE_RATE = 0.25          # 25% of would-be churners stay because of the offer
DEFAULT_STAYER_UPTAKE = 1.0       # share of customers who would have stayed anyway that also take the discount
CURRENCY = "$"

# Model settings
TEST_SIZE = 0.25
RANDOM_STATE = 42

DISCLAIMER = "Public dataset. Analysis illustrates method, not a real company's results."
