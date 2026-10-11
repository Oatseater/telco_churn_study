"""Cached data loaders for the Streamlit app. All data comes from the SQLite
database and reports/metrics.json produced by run_pipeline.py.

Caches are keyed on the files' modification times, so re-running the pipeline
while the app is open refreshes the numbers on the next interaction.
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src import config, database


def pipeline_ready() -> bool:
    return config.DB_PATH.exists() and config.METRICS_JSON.exists()


def require_pipeline() -> None:
    if not pipeline_ready():
        st.error("Processed data not found. Run `python run_pipeline.py` first, then reload this page.")
        st.stop()


def _stamp(path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


@st.cache_data(show_spinner=False)
def _query(name: str, stamp_value: float) -> pd.DataFrame:
    return database.run_query_file(name)


@st.cache_data(show_spinner=False)
def _customers(stamp_value: float) -> pd.DataFrame:
    return database.read_table("SELECT * FROM customer_profile")


@st.cache_data(show_spinner=False)
def _metrics(stamp_value: float) -> dict:
    return json.loads(config.METRICS_JSON.read_text(encoding="utf-8"))


def query(name: str) -> pd.DataFrame:
    return _query(name, _stamp(config.DB_PATH))


def customers() -> pd.DataFrame:
    return _customers(_stamp(config.DB_PATH))


def metrics() -> dict:
    return _metrics(_stamp(config.METRICS_JSON))
