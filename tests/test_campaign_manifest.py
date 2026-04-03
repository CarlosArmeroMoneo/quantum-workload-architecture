from pathlib import Path

import pytest

from aqs.db import (
    apply_schema,
    insert_campaign_cell,
    insert_campaign_profile,
    insert_campaign_registry,
    insert_campaign_run,
)
from aqs.manifest import load_yaml, validate_manifest
from aqs.repo_metadata import capture_repo_metadata


def test_campaign_manifests_validate():
    for path in sorted(Path("configs/campaigns").glob("*.yaml")):
        manifest = load_yaml(path)
        assert validate_manifest(manifest) == [], f"{path} should validate"


@pytest.mark.db
def test_campaign_registry_tables_accept_rows(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    db_path = tmp_path / "campaign.duckdb"
    apply_schema(db_path)

    insert_campaign_registry(
        db_path,
        {
            "campaign_id": "camp_test",
            "campaign_name": "cpu_dry_run_v1",
            "api_version": "aqs.campaign.v1",
            "manifest_path": "configs/campaigns/cpu_dry_run_v1.yaml",
            "objective": "ttfr",
            "system_manifest": "configs/systems/cpu_probe.yml",
            "outdir": "artifacts/campaigns/cpu_dry_run_v1",
            "repo_metadata": capture_repo_metadata(),
            "summary_json": {"status": "pending"},
        },
    )
    insert_campaign_cell(
        db_path,
        {
            "cell_id": "cell_test",
            "campaign_id": "camp_test",
            "workload_id": "wkl_test",
            "replicate_count": 2,
            "parameter_json": {"planner_budget": "quick"},
            "plan_json": {"plan_id": "plan_test", "mode": "exact_tn"},
        },
    )
    insert_campaign_run(
        db_path,
        "camp_test",
        "cell_test",
        {
            "run_id": "run_test",
            "replicate_idx": 1,
        },
    )
    insert_campaign_profile(db_path, "camp_test", "cell_test", "prof_test", "synthetic")

    conn = duckdb.connect(str(db_path))
    try:
        registry_count = conn.execute("SELECT count(*) FROM experiment.campaign_registry").fetchone()[0]
        cell_count = conn.execute("SELECT count(*) FROM experiment.campaign_cell").fetchone()[0]
        run_row = conn.execute(
            "SELECT run_id, replicate_idx FROM experiment.campaign_run WHERE campaign_id = 'camp_test'"
        ).fetchone()
        profile_row = conn.execute(
            "SELECT profile_id, profiler_kind FROM experiment.campaign_profile WHERE campaign_id = 'camp_test'"
        ).fetchone()
    finally:
        conn.close()

    assert registry_count == 1
    assert cell_count == 1
    assert run_row == ("run_test", 1)
    assert profile_row == ("prof_test", "synthetic")
