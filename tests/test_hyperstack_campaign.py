from pathlib import Path

from aqs.manifest import load_yaml


def test_hyperstack_campaign_is_budgeted_and_bounded():
    manifest = load_yaml("configs/experiments/hyperstack_crossover_campaign_v0_2.yaml")

    assert manifest["status"] == "planning_no_execution"
    assert manifest["total_budget_cap"] == 15.0
    assert manifest["broad_sweeps_allowed"] is False
    assert Path(manifest["preferred_system_template"]).exists()
    assert Path(manifest["fallback_system_template"]).exists()
    assert Path(manifest["triage_policy"]).exists()

    phase_count = len(manifest["phases"])
    assert phase_count == 3
    for phase in manifest["phases"]:
        for path in phase.get("workloads", []):
            assert Path(path).exists()
        for path in phase.get("workload_options", []):
            assert Path(path).exists()
        assert phase["stop_rules"]

    assert manifest["phases"][2]["max_selected_workloads"] == 1
    assert manifest["claim_boundary"]["no_existing_hyperstack_result"] is True


def test_hyperstack_runbook_includes_budget_and_credential_boundaries():
    text = Path("docs/runbooks/hyperstack_crossover_campaign.md").read_text(encoding="utf-8")

    assert "Do not commit API tokens" in text
    assert "Budget cap: EUR 3" in text
    assert "Budget cap: EUR 5 additional" in text
    assert "Delete the VM" in text
