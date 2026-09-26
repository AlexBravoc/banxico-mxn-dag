"""Client for Banco de Mexico's SIE API (https://www.banxico.org.mx/SieAPIRest)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

import requests

BASE_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"

# USD/MXN FIX exchange rate, published daily by Banxico.
USD_MXN_FIX_SERIES_ID = "SF43718"

# Banxico marks days with no published value (weekends, holidays) this way.
NO_DATA_MARKER = "N/E"


class BanxicoAPIError(RuntimeError):
    """Raised when the Banxico API returns an error or an unexpected payload."""


@dataclass(frozen=True)
class ExchangeRate:
    rate_date: dt.date
    fix_rate: Decimal
    series_id: str = USD_MXN_FIX_SERIES_ID


def _parse_date(fecha: str) -> dt.date:
    return dt.datetime.strptime(fecha, "%d/%m/%Y").date()


def fetch_exchange_rates(
    start_date: dt.date,
    end_date: dt.date,
    token: str,
    series_id: str = USD_MXN_FIX_SERIES_ID,
    timeout: int = 30,
) -> list[ExchangeRate]:
    """Fetch published exchange rates for `series_id` in [start_date, end_date].

    Days without a published value (weekends, holidays) are skipped rather
    than raising, since that is expected behavior for this series.
    """
    if start_date > end_date:
        raise ValueError("start_date must not be after end_date")
    if not token:
        raise BanxicoAPIError("A Banxico API token is required")

    url = (
        f"{BASE_URL}/{series_id}/datos/"
        f"{start_date:%Y-%m-%d}/{end_date:%Y-%m-%d}"
    )
    response = requests.get(
        url,
        headers={"Bmx-Token": token, "Accept": "application/json"},
        timeout=timeout,
    )
    if response.status_code != 200:
        raise BanxicoAPIError(
            f"Banxico API returned HTTP {response.status_code}: {response.text}"
        )

    payload = response.json()
    try:
        series = payload["bmx"]["series"][0]
        datos = series.get("datos", [])
    except (KeyError, IndexError, TypeError) as exc:
        raise BanxicoAPIError(f"Unexpected Banxico API payload: {payload}") from exc

    rates: list[ExchangeRate] = []
    for entry in datos:
        raw_value = entry.get("dato", NO_DATA_MARKER)
        if raw_value == NO_DATA_MARKER:
            continue
        try:
            fix_rate = Decimal(raw_value)
        except InvalidOperation as exc:
            raise BanxicoAPIError(f"Unexpected rate value: {raw_value!r}") from exc
        rates.append(
            ExchangeRate(
                rate_date=_parse_date(entry["fecha"]),
                fix_rate=fix_rate,
                series_id=series_id,
            )
        )
    return rates


def fetch_latest_exchange_rate(
    token: str,
    as_of: Optional[dt.date] = None,
    lookback_days: int = 7,
    series_id: str = USD_MXN_FIX_SERIES_ID,
) -> Optional[ExchangeRate]:
    """Fetch the most recently published rate on or before `as_of`.

    A lookback window is used because the FIX rate is not published on
    weekends or Mexican holidays.
    """
    as_of = as_of or dt.date.today()
    start_date = as_of - dt.timedelta(days=lookback_days)
    rates = fetch_exchange_rates(start_date, as_of, token, series_id=series_id)
    if not rates:
        return None
    return max(rates, key=lambda r: r.rate_date)
