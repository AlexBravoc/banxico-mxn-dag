import datetime as dt
from decimal import Decimal
from unittest.mock import MagicMock

from banxico.api import ExchangeRate
from banxico.db import upsert_rates


def _mock_connection():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn, cursor


def test_upsert_rates_executes_and_commits():
    conn, cursor = _mock_connection()
    rates = [
        ExchangeRate(dt.date(2026, 9, 1), Decimal("18.1234")),
        ExchangeRate(dt.date(2026, 9, 2), Decimal("18.2000")),
    ]

    written = upsert_rates(conn, rates)

    assert written == 2
    cursor.executemany.assert_called_once()
    sql, rows = cursor.executemany.call_args.args
    assert "ON CONFLICT (rate_date)" in sql
    assert rows == [
        {"rate_date": dt.date(2026, 9, 1), "fix_rate": Decimal("18.1234"), "series_id": "SF43718"},
        {"rate_date": dt.date(2026, 9, 2), "fix_rate": Decimal("18.2000"), "series_id": "SF43718"},
    ]
    conn.commit.assert_called_once()


def test_upsert_rates_skips_db_call_when_empty():
    conn, cursor = _mock_connection()

    written = upsert_rates(conn, [])

    assert written == 0
    cursor.executemany.assert_not_called()
    conn.commit.assert_not_called()
