CREATE SCHEMA IF NOT EXISTS banxico;

CREATE TABLE IF NOT EXISTS banxico.usd_mxn_rates (
    rate_date DATE PRIMARY KEY,
    fix_rate NUMERIC(12, 6) NOT NULL,
    series_id TEXT NOT NULL DEFAULT 'SF43718',
    inserted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
