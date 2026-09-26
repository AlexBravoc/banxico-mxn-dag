"""Postgres persistence for Banxico exchange rates."""
from __future__ import annotations

import os
from typing import Iterable, Protocol

from banxico.api import ExchangeRate

UPSERT_SQL = """
    INSERT INTO banxico.usd_mxn_rates (rate_date, fix_rate, series_id, updated_at)
    VALUES (%(rate_date)s, %(fix_rate)s, %(series_id)s, now())
    ON CONFLICT (rate_date) DO UPDATE
        SET fix_rate = EXCLUDED.fix_rate,
            series_id = EXCLUDED.series_id,
            updated_at = now();
"""


class Connection(Protocol):
    """The subset of a DB-API 2.0 connection this module relies on."""

    def cursor(self): ...
    def commit(self) -> None: ...


def get_connection_params() -> dict:
    """Read Postgres connection parameters from the environment.

    Kept separate from `fetch_and_load` so tests can construct connections
    however they like without going through env vars.
    """
    return {
        "host": os.environ.get("BANXICO_DB_HOST", "postgres"),
        "port": int(os.environ.get("BANXICO_DB_PORT", "5432")),
        "dbname": os.environ.get("BANXICO_DB_NAME", "airflow"),
        "user": os.environ.get("BANXICO_DB_USER", "airflow"),
        "password": os.environ.get("BANXICO_DB_PASSWORD", "airflow"),
    }


def upsert_rates(conn: Connection, rates: Iterable[ExchangeRate]) -> int:
    """Upsert exchange rates into banxico.usd_mxn_rates. Returns rows written."""
    rows = [
        {
            "rate_date": rate.rate_date,
            "fix_rate": rate.fix_rate,
            "series_id": rate.series_id,
        }
        for rate in rates
    ]
    if not rows:
        return 0

    with conn.cursor() as cur:
        cur.executemany(UPSERT_SQL, rows)
    conn.commit()
    return len(rows)
