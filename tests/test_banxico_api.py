import datetime as dt
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from banxico.api import (
    BanxicoAPIError,
    ExchangeRate,
    fetch_exchange_rates,
    fetch_latest_exchange_rate,
)


def _banxico_payload(datos):
    return {"bmx": {"series": [{"idSerie": "SF43718", "datos": datos}]}}


@patch("banxico.api.requests.get")
def test_fetch_exchange_rates_parses_datos(mock_get):
    mock_get.return_value = Mock(
        status_code=200,
        json=Mock(
            return_value=_banxico_payload(
                [
                    {"fecha": "01/09/2026", "dato": "18.1234"},
                    {"fecha": "02/09/2026", "dato": "18.2000"},
                ]
            )
        ),
    )

    rates = fetch_exchange_rates(
        dt.date(2026, 9, 1), dt.date(2026, 9, 2), token="fake-token"
    )

    assert rates == [
        ExchangeRate(dt.date(2026, 9, 1), Decimal("18.1234")),
        ExchangeRate(dt.date(2026, 9, 2), Decimal("18.2000")),
    ]


@patch("banxico.api.requests.get")
def test_fetch_exchange_rates_skips_no_data_days(mock_get):
    mock_get.return_value = Mock(
        status_code=200,
        json=Mock(
            return_value=_banxico_payload(
                [
                    {"fecha": "05/09/2026", "dato": "N/E"},  # weekend
                    {"fecha": "07/09/2026", "dato": "18.5000"},
                ]
            )
        ),
    )

    rates = fetch_exchange_rates(
        dt.date(2026, 9, 5), dt.date(2026, 9, 7), token="fake-token"
    )

    assert len(rates) == 1
    assert rates[0].rate_date == dt.date(2026, 9, 7)


@patch("banxico.api.requests.get")
def test_fetch_exchange_rates_raises_on_http_error(mock_get):
    mock_get.return_value = Mock(status_code=401, text="invalid token")

    with pytest.raises(BanxicoAPIError, match="401"):
        fetch_exchange_rates(
            dt.date(2026, 9, 1), dt.date(2026, 9, 2), token="bad-token"
        )


@patch("banxico.api.requests.get")
def test_fetch_exchange_rates_raises_on_unexpected_payload(mock_get):
    mock_get.return_value = Mock(status_code=200, json=Mock(return_value={}))

    with pytest.raises(BanxicoAPIError, match="Unexpected Banxico API payload"):
        fetch_exchange_rates(
            dt.date(2026, 9, 1), dt.date(2026, 9, 2), token="fake-token"
        )


def test_fetch_exchange_rates_requires_token():
    with pytest.raises(BanxicoAPIError, match="token"):
        fetch_exchange_rates(dt.date(2026, 9, 1), dt.date(2026, 9, 2), token="")


def test_fetch_exchange_rates_rejects_inverted_range():
    with pytest.raises(ValueError):
        fetch_exchange_rates(
            dt.date(2026, 9, 2), dt.date(2026, 9, 1), token="fake-token"
        )


@patch("banxico.api.fetch_exchange_rates")
def test_fetch_latest_exchange_rate_returns_most_recent(mock_fetch):
    mock_fetch.return_value = [
        ExchangeRate(dt.date(2026, 9, 1), Decimal("18.10")),
        ExchangeRate(dt.date(2026, 9, 3), Decimal("18.30")),
        ExchangeRate(dt.date(2026, 9, 2), Decimal("18.20")),
    ]

    latest = fetch_latest_exchange_rate(token="fake-token", as_of=dt.date(2026, 9, 3))

    assert latest.rate_date == dt.date(2026, 9, 3)


@patch("banxico.api.fetch_exchange_rates")
def test_fetch_latest_exchange_rate_returns_none_when_empty(mock_fetch):
    mock_fetch.return_value = []

    assert fetch_latest_exchange_rate(token="fake-token") is None
