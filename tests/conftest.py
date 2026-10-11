"""Shared fixtures. Tests read the artefacts produced by run_pipeline.py; if they
are missing, the pipeline is run once first."""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import config, database  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def pipeline_outputs():
    if not (config.DB_PATH.exists() and config.METRICS_JSON.exists()):
        import run_pipeline
        assert run_pipeline.main() == 0
    return True


@pytest.fixture(scope="session")
def customers() -> pd.DataFrame:
    return database.read_table("SELECT * FROM customers")


@pytest.fixture(scope="session")
def profile() -> pd.DataFrame:
    return database.read_table("SELECT * FROM customer_profile")


@pytest.fixture(scope="session")
def metrics() -> dict:
    return json.loads(config.METRICS_JSON.read_text(encoding="utf-8"))
