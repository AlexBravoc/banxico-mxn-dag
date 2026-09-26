import os
from pathlib import Path

import pytest

airflow = pytest.importorskip(
    "airflow", reason="apache-airflow is only needed to test DAG structure"
)

DAGS_FOLDER = Path(__file__).resolve().parent.parent / "dags"


@pytest.fixture(scope="module")
def dagbag():
    os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "false")
    from airflow.models import DagBag

    return DagBag(dag_folder=str(DAGS_FOLDER), include_examples=False)


def test_dagbag_has_no_import_errors(dagbag):
    assert dagbag.import_errors == {}


def test_banxico_dag_is_loaded(dagbag):
    assert "banxico_usdmxn_daily" in dagbag.dags


def test_banxico_dag_task_dependencies(dagbag):
    dag = dagbag.dags["banxico_usdmxn_daily"]
    task_ids = set(dag.task_dict)

    assert task_ids == {"extract", "load"}
    assert dag.get_task("load").upstream_task_ids == {"extract"}


def test_banxico_dag_has_retries_configured(dagbag):
    dag = dagbag.dags["banxico_usdmxn_daily"]

    assert dag.default_args["retries"] >= 1
