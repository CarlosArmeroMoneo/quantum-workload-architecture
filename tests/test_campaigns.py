import csv
import json

import pytest

from aqs.campaigns import enumerate_campaign_cells, run_campaign_manifest, summarize_campaign_manifest


def test_campaign_enumeration_is_deterministic():
    first = enumerate_campaign_cells("configs/campaigns/cpu_dry_run_v1.yaml")
    second = enumerate_campaign_cells("configs/campaigns/cpu_dry_run_v1.yaml")
    assert [cell["cell_id"] for cell in first["cells"]] == [cell["cell_id"] for cell in second["cells"]]


def test_cpu_dry_run_campaign_writes_summary_report_and_plots(tmp_path):
    outdir = tmp_path / "cpu_dry_run_v1"
    summary = run_campaign_manifest("configs/campaigns/cpu_dry_run_v1.yaml", outdir=outdir)

    assert summary["campaign_name"] == "cpu_dry_run_v1"
    assert summary["cell_count"] >= 1
    assert summary["run_count"] == summary["cell_count"] * 2
    assert summary["status_counts"] == {"success": summary["run_count"]}
    assert (outdir / "summary.json").exists()
    assert (outdir / "results.csv").exists()
    assert (outdir / "report.md").exists()
    assert any((outdir / "plots").glob("*.svg"))

    rerendered = summarize_campaign_manifest("configs/campaigns/cpu_dry_run_v1.yaml", outdir=outdir)
    assert rerendered["campaign_id"] == summary["campaign_id"]

    with (outdir / "results.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert rows[0]["cell_id"]


def test_campaign_rerun_discards_stale_cell_and_run_artifacts(tmp_path):
    outdir = tmp_path / "cpu_dry_run_v1"
    first = run_campaign_manifest("configs/campaigns/cpu_dry_run_v1.yaml", outdir=outdir)

    stale_cell = outdir / "cells" / "cell_stale.json"
    stale_cell.parent.mkdir(parents=True, exist_ok=True)
    stale_cell.write_text(
        json.dumps(
            {
                "campaign_id": first["campaign_id"],
                "campaign_name": first["campaign_name"],
                "cell_id": "cell_stale",
                "manifest_path": "stale.yaml",
                "workload_id": "wkl_stale",
                "parameter_json": {},
                "plan_json": {"plan_id": "plan_stale"},
                "replicate_count": 1,
            }
        ),
        encoding="utf-8",
    )
    stale_run = outdir / "runs" / "cell_stale" / "replicate_0.execution.json"
    stale_run.parent.mkdir(parents=True, exist_ok=True)
    stale_run.write_text(
        json.dumps(
            {
                "execution_run": {
                    "run_id": "run_stale",
                    "replicate_idx": 0,
                    "status": "runtime_error",
                }
            }
        ),
        encoding="utf-8",
    )

    second = run_campaign_manifest("configs/campaigns/cpu_dry_run_v1.yaml", outdir=outdir)
    assert second["cell_count"] == first["cell_count"]
    assert second["run_count"] == first["run_count"]
    assert not stale_cell.exists()
    assert not stale_run.exists()


def test_repeat_roi_cpu_dry_run_emits_roi_metrics_and_report_outputs(tmp_path):
    outdir = tmp_path / "repeat_roi_cpu_dry_run_v1"
    summary = run_campaign_manifest("configs/campaigns/repeat_roi_cpu_dry_run_v1.yaml", outdir=outdir)

    assert summary["status_counts"] == {"success": summary["run_count"]}
    assert summary["repeat_roi"]["analysis_version"] == "aqs.repeat_roi.v1"
    assert summary["repeat_roi"]["dry_run_only"] is True
    assert summary["repeat_roi"]["finding_count"] == summary["cell_count"]
    assert summary["repeat_roi"]["suggested_policy_overrides"]["confidence"] == "dry_run_structural_model_only"
    report_text = (outdir / "report.md").read_text(encoding="utf-8")
    assert "Repeat ROI Foundation" in report_text
    assert "Dry-run only" in report_text
    assert (outdir / "plots" / "repeat_roi_break_even.svg").exists()


def test_cuda_graphs_ablation_enumerates_graph_mode_cells():
    preview = enumerate_campaign_cells("configs/campaigns/cuda_graphs_ablation_v1.yaml")

    assert preview["campaign_name"] == "cuda_graphs_ablation_v1"
    assert {cell["parameter_json"]["graph_mode"] for cell in preview["cells"]} == {"off", "warm_only", "steady_state"}
    assert len({cell["cell_id"] for cell in preview["cells"]}) == len(preview["cells"])
    assert all(cell["plan_json"].get("graph_mode") == cell["parameter_json"]["graph_mode"] for cell in preview["cells"])


@pytest.mark.db
def test_campaign_run_populates_experiment_tables(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    outdir = tmp_path / "cpu_dry_run_v1"
    db_path = tmp_path / "campaign.duckdb"
    summary = run_campaign_manifest("configs/campaigns/cpu_dry_run_v1.yaml", outdir=outdir, db_path=db_path)

    conn = duckdb.connect(str(db_path))
    try:
        registry_count = conn.execute("SELECT count(*) FROM experiment.campaign_registry").fetchone()[0]
        cell_count = conn.execute("SELECT count(*) FROM experiment.campaign_cell").fetchone()[0]
        run_count = conn.execute("SELECT count(*) FROM experiment.campaign_run").fetchone()[0]
    finally:
        conn.close()

    assert summary["run_count"] >= 1
    assert registry_count == 1
    assert cell_count == summary["cell_count"]
    assert run_count == summary["run_count"]


@pytest.mark.db
def test_campaign_db_allows_shared_ir_hash_across_workloads(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    outdir = tmp_path / "cpu_dry_run_v1"
    db_path = tmp_path / "campaign.duckdb"
    run_campaign_manifest("configs/campaigns/cpu_dry_run_v1.yaml", outdir=outdir, db_path=db_path)

    conn = duckdb.connect(str(db_path))
    try:
        normalized_ir_count = conn.execute("SELECT count(*) FROM corpus.normalized_ir").fetchone()[0]
        shared_hash_rows = conn.execute(
            """
            SELECT count(*)
            FROM (
                SELECT ir_hash
                FROM corpus.normalized_ir
                GROUP BY ir_hash
                HAVING count(*) > 1
            )
            """
        ).fetchone()[0]
    finally:
        conn.close()

    assert normalized_ir_count >= 2
    assert shared_hash_rows >= 1
