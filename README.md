# Banxico USD/MXN Rates DAG

An Airflow DAG that fetches the daily USD/MXN FIX exchange rate from Banco de
México's [SIE API](https://www.banxico.org.mx/SieAPIRest/service/v1/) and
loads it into Postgres.

## How it works

- **Series**: `SF43718` (USD/MXN FIX), published on business days.
- **DAG** (`dags/banxico_usdmxn_dag.py`, id `banxico_usdmxn_daily`): runs
  daily at 19:00 UTC (~1pm Mexico City), after the day's FIX rate is
  published.
  - `extract`: calls the Banxico API for the last 5 days (a lookback window
    so a missed run or a Banxico publication delay self-heals on the next
    successful run, instead of needing a manual backfill).
  - `load`: upserts the returned rates into `banxico.usd_mxn_rates`, keyed
    on `rate_date`, so re-running a day is always safe.
- **Storage**: the same Postgres instance used for Airflow's metadata DB
  also holds the `banxico` schema (see `sql/create_table.sql`), to keep the
  Compose stack to a single database service.

## Project layout

```
dags/
  banxico_usdmxn_dag.py   # the DAG
  banxico/
    api.py                # Banxico SIE API client
    db.py                 # Postgres upsert helper
sql/
  create_table.sql        # banxico.usd_mxn_rates schema
tests/                    # pytest unit tests
docker-compose.yml
Dockerfile
```

## Running it

1. Get a free Banxico API token at
   https://www.banxico.org.mx/SieAPIRest/service/v1/token.
2. Copy the env template and fill in `BANXICO_API_TOKEN` (and change the
   default passwords):
   ```
   cp .env.example .env
   ```
3. Start the stack:
   ```
   docker compose up --build
   ```
   This builds the Airflow image, brings up Postgres (running
   `sql/create_table.sql` on first boot), runs `airflow-init` to migrate the
   metadata DB, create an admin user, and seed `BANXICO_API_TOKEN` as the
   `banxico_api_token` Airflow Variable — then starts the webserver and
   scheduler.
4. Open http://localhost:8080 (login from `AIRFLOW_ADMIN_USER` /
   `AIRFLOW_ADMIN_PASSWORD` in `.env`) and unpause `banxico_usdmxn_daily`,
   or trigger it manually to backfill immediately.
5. Check the data:
   ```
   docker compose exec postgres psql -U airflow -d airflow \
     -c "select * from banxico.usd_mxn_rates order by rate_date desc limit 5;"
   ```

If you didn't set `BANXICO_API_TOKEN` before first boot, set the Airflow
Variable manually instead:
```
docker compose exec airflow-webserver airflow variables set banxico_api_token <your-token>
```

## Tests

The `banxico.api` and `banxico.db` unit tests only need `requirements.txt`
plus `pytest`:
```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # includes apache-airflow, for the DAG-structure tests too
pytest
```

`apache-airflow` is a heavy dependency; if you'd rather skip installing it
locally, `pip install -r requirements.txt pytest` is enough to run
everything except `tests/test_dag_integrity.py`, which skips automatically
when `airflow` isn't importable. Alternatively, run the full suite inside
the built container:
```
docker compose run --rm airflow-webserver pytest
```

## Notes / assumptions

- The 19:00 UTC schedule assumes the FIX rate is published earlier that
  day; adjust `schedule` in the DAG if Banxico's publication time changes.
- `docker-compose.yml` was validated for syntax but not smoke-tested with a
  live `docker compose up` in this environment (Docker wasn't available
  here) — please do a first run yourself and open an issue/PR for anything
  that needs adjusting.
