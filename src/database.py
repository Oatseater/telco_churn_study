"""SQLite helpers: load the cleaned table, create views, run query files."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd

from src import config


def connect(db_path: Path = config.DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def load_to_sqlite(df: pd.DataFrame, db_path: Path = config.DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    with connect(db_path) as con:
        df.to_sql("customers", con, index=False)
        con.execute("CREATE UNIQUE INDEX idx_customers_id ON customers(customer_id)")
        con.executescript(config.SCHEMA_SQL.read_text(encoding="utf-8"))


def query_files() -> list[Path]:
    return sorted(config.QUERIES_DIR.glob("*.sql"))


def business_question(path: Path) -> str:
    """Return the business question stated in a query file's header comment."""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"--\s*Business question:\s*(.+?)(?:\n--\s*\n|\n(?!--))", text, re.S)
    if not m:
        return ""
    return " ".join(line.lstrip("-").strip() for line in m.group(1).splitlines())


def run_query_file(path: Path | str, db_path: Path = config.DB_PATH) -> pd.DataFrame:
    path = Path(path)
    if not path.is_absolute():
        path = config.QUERIES_DIR / path
    sql = path.read_text(encoding="utf-8")
    with connect(db_path) as con:
        return pd.read_sql_query(sql, con)


def read_table(sql: str, db_path: Path = config.DB_PATH) -> pd.DataFrame:
    with connect(db_path) as con:
        return pd.read_sql_query(sql, con)
