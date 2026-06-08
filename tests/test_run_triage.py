from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "triage_run_target.py"


def _run_triage(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.stderr == ""
    return completed.returncode, json.loads(completed.stdout)


def test_ghz3_preflight_recommends_local_preflight():
    code, result = _run_triage(
        "--workload",
        "workloads/manifests/imported/real_ghz3_amplitude.yaml",
        "--system-manifest",
        "configs/systems/local_nvidia_laptop_6gb.template.yml",
        "--evidence-goal",
        "preflight",
    )

    assert code == 0
    assert result["recommendation"] == "local_preflight"
    assert "local_6gb_tiny_preflight_allowed" in result["reason_codes"]


def test_medium_accepted_profile_on_local_6gb_is_blocked():
    code, result = _run_triage(
        "--workload",
        "workloads/manifests/generated/dense_universal_smoke.yaml",
        "--system-manifest",
        "configs/systems/local_nvidia_laptop_6gb.template.yml",
        "--evidence-goal",
        "accepted_profile",
    )

    assert code == 0
    assert result["recommendation"] == "do_not_run"
    assert "local_6gb_preflight_only" in result["reason_codes"]


def test_batched_calibration_with_budget_recommends_hyperstack():
    code, result = _run_triage(
        "--workload",
        "workloads/manifests/imported/real_dense_ring6_batched.yaml",
        "--target-class",
        "hyperstack",
        "--evidence-goal",
        "calibration_campaign",
        "--budget-cap-eur",
        "15",
    )

    assert code == 0
    assert result["recommendation"] == "hyperstack_budget"
    assert "budget_fits_hyperstack_mini_campaign" in result["reason_codes"]


def test_a100_acceptance_without_quota_waits():
    code, result = _run_triage(
        "--workload",
        "workloads/manifests/imported/real_ghz3_amplitude.yaml",
        "--target-class",
        "gcp_a100",
        "--evidence-goal",
        "accepted_profile",
    )

    assert code == 0
    assert result["recommendation"] == "gcp_wait_for_quota"
    assert "gcp_a100_quota_not_ready" in result["reason_codes"]


def test_invalid_workload_path_returns_clear_json_error():
    code, result = _run_triage(
        "--workload",
        "workloads/manifests/missing.yaml",
        "--target-class",
        "hyperstack",
        "--evidence-goal",
        "preflight",
    )

    assert code == 2
    assert "path does not exist" in result["error"]
