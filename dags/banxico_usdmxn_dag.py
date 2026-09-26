"""Daily load of the Banxico USD/MXN FIX exchange rate into Postgres.

Requires a Banxico SIE API token, available free at
https://www.banxico.org.mx/SieAPIRest/service/v1/token, set as the Airflow
Variable `banxico_api_token` (or the BANXICO_API_TOKEN env var as a
fallback).
"""
from __future__ import annotations

import datetime as dt
import logging

import psycopg2
from airflow.decorators import dag, task
from airflow.models import Variable

from banxico.api import BanxicoAPIError, fetch_exchange_rates
from banxico.db import get_connection_params, upsert_rates

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    "owner": "data-eng",
    "retries": 3,
    "retry_delay": dt.timedelta(minutes=5),
}

# Look back a few days so a missed run (or a Banxico publication delay)
# still gets backfilled on the next successful run.
LOOKBACK_DAYS = 5


def _get_token() -> str:
    return Variable.get("banxico_api_token", default_var="")


@dag(
    dag_id="banxico_usdmxn_daily",
    description="Load the daily Banxico USD/MXN FIX rate into Postgres",
    default_args=DEFAULT_ARGS,
    schedule="0 19 * * *",  # ~1pm Mexico City time, after the FIX is published
    start_date=dt.datetime(2024, 1, 1),
    catchup=False,
    tags=["banxico", "fx", "postgres"],
)
def banxico_usdmxn_dag():
    @task
    def extract(data_interval_end: dt.datetime | None = None) -> list[dict]:
        token = _get_token()
        if not token:
            raise BanxicoAPIError(
                "Missing Banxico API token: set the 'banxico_api_token' "
                "Airflow Variable."
            )
        end_date = (data_interval_end or dt.datetime.now(dt.timezone.utc)).date()
        start_date = end_date - dt.timedelta(days=LOOKBACK_DAYS)
        rates = fetch_exchange_rates(start_date, end_date, token=token)
        logger.info("Fetched %d rate(s) between %s and %s", len(rates), start_date, end_date)
        return [
            {
                "rate_date": rate.rate_date.isoformat(),
                "fix_rate": str(rate.fix_rate),
                "series_id": rate.series_id,
            }
            for rate in rates
        ]

    @task
    def load(raw_rates: list[dict]) -> int:
        from banxico.api import ExchangeRate
        from decimal import Decimal

        rates = [
            ExchangeRate(
                rate_date=dt.date.fromisoformat(r["rate_date"]),
                fix_rate=Decimal(r["fix_rate"]),
                series_id=r["series_id"],
            )
            for r in raw_rates
        ]
        conn = psycopg2.connect(**get_connection_params())
        try:
            written = upsert_rates(conn, rates)
        finally:
            conn.close()
        logger.info("Upserted %d row(s) into banxico.usd_mxn_rates", written)
        return written

    load(extract())


banxico_usdmxn_dag()
