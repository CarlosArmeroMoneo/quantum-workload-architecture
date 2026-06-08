import pytest

from aqs.db import apply_schema


@pytest.mark.db
def test_plan_prediction_error_view_has_guarded_ratio_columns(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    db_path = tmp_path / "warehouse.duckdb"
    apply_schema(db_path)
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            INSERT INTO planning.plan_candidate (
                plan_id, workload_id, project, planner_version, objective, mode,
                predicted_ttfr_s, predicted_iter_ms, feasibility_label, explanation_json
            )
            VALUES (
                'plan_ratio', 'workload_ratio', 'tnep', 'planner', 'ttfr', 'exact_tn',
                2.0, 0.0, 'feasible', '{}'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO execution.execution_run (
                run_id, plan_id, workload_id, system_id, status, ttfr_s, steady_iter_ms, execution_source
            )
            VALUES (
                'run_ratio', 'plan_ratio', 'workload_ratio', 'system_ratio', 'success', 3.0, 4.0, 'cuquantum_tensornet_gpu'
            )
            """
        )
        row = conn.execute(
            """
            SELECT ttfr_error_ratio, iter_error_ratio
            FROM marts.plan_prediction_error
            WHERE plan_id = 'plan_ratio'
            """
        ).fetchone()
    finally:
        conn.close()

    assert row[0] == pytest.approx(1.5)
    assert row[1] is None
