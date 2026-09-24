"""Check the public reading path against tracked files and recorded results."""

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DOCS = (
    "README.md",
    "PROJECT_OVERVIEW.md",
    "docs/README.md",
    "docs/reports/measured_results.md",
    "docs/reports/how_to_review_this_project.md",
    "docs/reports/current_state_truth_pass.md",
)
SLICE = ROOT / "evidence/first_real_profiler_slice"
STEM = "real_dense_ring6_batched.ncu.0e70e7aabe3342c1"


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("relative_path", PUBLIC_DOCS)
def test_public_document_local_links_exist(relative_path):
    path = ROOT / relative_path
    text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
    for target in re.findall(r"!?\[[^\]]*\]\(([^\s)]+)\)", text):
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path:
            continue
        resolved = (path.parent / unquote(url.path)).resolve()
        assert resolved.is_relative_to(ROOT), (relative_path, target)
        assert resolved.exists(), (relative_path, target)


def test_project_release_and_package_names_are_explained():
    for relative_path in ("README.md", "PROJECT_OVERVIEW.md"):
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        for term in ("Quantum Workload Atlas", "quantum-workload-architecture", "`aqs`", "v0.2-crossover-calibration"):
            assert term in text
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "v0.5.0-evidence" in readme
    assert "historical evidence-archive tag" in readme


def test_canonical_result_card_matches_recorded_evidence():
    payload = _json(SLICE / f"{STEM}.execution.json")
    profile = _json(SLICE / f"{STEM}.profile_summary.json")
    analysis = _json(SLICE / "real_dense_ring6_batched.arch.json")
    text = (ROOT / "docs/reports/measured_results.md").read_text(encoding="utf-8")
    run = payload["execution_run"]
    phases = run["failure_detail_json"]["phase_times"]
    setup = sum(phases[name] for name in ("load_circuit", "convert_to_einsum", "postprocess"))
    share = 100 * setup / sum(phases.values())
    nomination = next(row for row in analysis["nominations"] if row["bottleneck_family"] == "launch_overhead")
    assert run["run_id"] == profile["run_id"] == analysis["source_run_id"]
    assert analysis["source_profile_id"] == profile["profile_id"]
    assert nomination["supporting_profile_ids"] == [profile["profile_id"]]
    assert nomination["nomination_reason_json"]["setup_share_pct"] == pytest.approx(share, abs=1e-6)
    assert f"`{share:.2f}%`" in text
    assert f"{setup:.9f} s" in text
    assert f"{sum(phases.values()):.9f} s" in text
    assert payload["accuracy_eval"]["status"] == "pass"
    assert payload["probe"]["status"] == "probe_fail"
    assert "`probe_fail`" in text
    plan = payload["selected_plan"]
    assert f"`{run['ttfr_s'] / plan['predicted_ttfr_s']:.4f}`" in text
    assert f"`{run['steady_iter_ms'] / plan['predicted_iter_ms']:.4f}`" in text
    for key in ("occupancy_pct", "sm_util_pct", "dram_util_pct"):
        assert profile[key] is None


def test_session_result_card_matches_recorded_summary():
    summary = _json(ROOT / "artifacts/session_runner/ovh_session_runner_prototype_v1/summary.json")
    text = (ROOT / "docs/reports/measured_results.md").read_text(encoding="utf-8")
    assert summary["fallback_count"] == 0
    assert summary["ranking_changed"] is False
    assert summary["pass_bars"]["no_correctness_drift"] is True
    assert summary["pass_bars"]["no_selected_plan_drift"] is True
    for row in summary["same_workload_medians"]:
        expected = f"| {row['persistent_warm_cli_ms']:.3f} | {row['session_runner_existing_worker_ms']:.3f} |"
        assert expected in text
    assert "excludes cold worker startup" in text


@pytest.mark.db
def test_documented_cpu_workflow_writes_a_plan(tmp_path):
    pytest.importorskip("duckdb")
    manifest = "workloads/manifests/generated/dense_universal_smoke.yaml"
    system = "configs/systems/cpu_probe.yml"
    output = tmp_path / "smoke.plan.json"
    commands = (
        ["scripts/init_db.py", "--db", str(tmp_path / "smoke.duckdb"), "--schema", "benchmarks/warehouse/schema.sql"],
        ["-m", "aqs", "manifest", "validate", "--mode", "implemented", manifest, system],
        ["-m", "aqs", "tnep", "probe", "--manifest", manifest, "--probe-strategy", "structural_real"],
        ["-m", "aqs", "tnep", "plan", "--manifest", manifest, "--system-manifest", system, "--probe-strategy", "structural_real", "--out", str(output)],
    )
    for args in commands:
        completed = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, timeout=90)
        assert completed.returncode == 0, completed.stdout + completed.stderr
    assert isinstance(_json(output), dict)
    assert _json(output)
