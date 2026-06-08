from pathlib import Path

from aqs.manifest import load_yaml


def test_launch_overhead_counterfactual_manifest_is_bounded():
    manifest = load_yaml("configs/experiments/launch_overhead_counterfactual_v0_2.yaml")

    assert manifest["status"] == "planning_no_execution"
    assert manifest["broad_sweeps_allowed"] is False
    assert manifest["arm_selection"] == "paired_not_cartesian"
    assert len(manifest["candidate_arms"]) <= 6
    assert manifest["knobs"]["repeat_count_hint"] == [1, 8, 32]
    assert "ttfr_s" in manifest["required_metrics"]
    assert "steady_iter_ms" in manifest["required_metrics"]
    assert "setup_share_pct" in manifest["required_metrics"]
    assert "profiler evidence missing" in manifest["stop_criteria"]
    assert Path(manifest["source_nomination"]["workload"]).exists()


def test_launch_overhead_counterfactual_runbook_and_doc_link_manifest():
    runbook = Path("docs/runbooks/launch_overhead_counterfactual_runbook.md").read_text(encoding="utf-8")
    doc = Path("docs/experiments/launch_overhead_counterfactual.md").read_text(encoding="utf-8")

    assert "configs/experiments/launch_overhead_counterfactual_v0_2.yaml" in runbook
    assert "configs/experiments/launch_overhead_counterfactual_v0_2.yaml" in doc
    assert "paired-arm" in doc
