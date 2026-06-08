from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ingest_accelerator_run.py"
SYSTEM = "configs/systems/hyperstack_a100.template.yml"
WORKLOAD = "workloads/manifests/imported/real_dense_ring6_batched.yaml"


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _base_execution() -> dict[str, Any]:
    return {
        "accuracy_eval": {"status": "pass"},
        "execution_run": {
            "run_id": "run_ingest_ok",
            "status": "success",
            "execution_source": "cuquantum_tensornet_gpu",
            "ttfr_s": 1.2,
            "steady_iter_ms": 42.0,
            "failure_detail_json": {
                "phase_times": {
                    "load_circuit": 0.1,
                    "convert_to_einsum": 0.2,
                    "contract_first": 0.7,
                    "postprocess": 0.1,
                }
            },
        },
        "selected_plan": {
            "predicted_ttfr_s": 0.6,
            "predicted_iter_ms": 14.0,
        },
        "system_manifest": {
            "system_name": "hyperstack_a100",
            "gpu_model": "NVIDIA A100",
            "gpu_arch_target": "sm80",
            "gpu_mem_gb": 40,
        },
    }


def _base_profile() -> dict[str, Any]:
    return {
        "run_id": "run_ingest_ok",
        "profiler_kind": "ncu",
        "derived_signals_json": {
            "profile_source": "real_ncu_profile",
            "csv_nonempty": True,
            "setup_share_pct": 36.0,
            "contract_share_pct": 64.0,
            "tensor_count": 24,
        },
        "top_kernels_json": [{"name": "cutensor_contraction_kernel"}],
    }


def _run_ingest(tmp_path: Path, execution: dict[str, Any], profile: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    execution_path = _write_json(tmp_path / "run.execution.json", execution)
    args = [
        sys.executable,
        str(SCRIPT),
        "--system-manifest",
        SYSTEM,
        "--workload-manifest",
        WORKLOAD,
        "--execution-payload",
        str(execution_path),
    ]
    if profile is not None:
        profile_path = _write_json(tmp_path / "run.profile_summary.json", profile)
        args.extend(["--profile-summary", str(profile_path)])
    completed = subprocess.run(
        args,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.stderr == ""
    return completed.returncode, json.loads(completed.stdout)


def test_post_run_ingestion_accepts_complete_fixture(tmp_path: Path):
    code, result = _run_ingest(tmp_path, _base_execution(), _base_profile())

    assert code == 0
    assert result["status"] == "accepted"
    assert result["evidence_tier"] == "Tier 2"
    assert result["calibration_record"]["interpretation_class"] == "model_miscalibrated"


def test_post_run_ingestion_missing_profile_is_pending(tmp_path: Path):
    code, result = _run_ingest(tmp_path, _base_execution(), None)

    assert code == 1
    assert result["status"] == "pending"
    assert "profile_summary_missing" in result["reason_codes"]


def test_post_run_ingestion_rejects_wrong_gpu(tmp_path: Path):
    execution = _base_execution()
    execution["system_manifest"]["gpu_model"] = "NVIDIA L4"

    code, result = _run_ingest(tmp_path, execution, _base_profile())

    assert code == 2
    assert result["status"] == "rejected"
    assert "system_gpu_model_mismatch" in result["reason_codes"]


def test_post_run_ingestion_rejects_missing_accuracy(tmp_path: Path):
    execution = _base_execution()
    execution.pop("accuracy_eval")

    code, result = _run_ingest(tmp_path, execution, _base_profile())

    assert code == 2
    assert result["status"] == "rejected"
    assert "accuracy_missing_or_not_pass" in result["reason_codes"]


def test_post_run_ingestion_sparse_profile_is_pending(tmp_path: Path):
    profile = copy.deepcopy(_base_profile())
    profile["derived_signals_json"] = {"profile_source": "real_ncu_profile"}
    profile["top_kernels_json"] = []

    code, result = _run_ingest(tmp_path, _base_execution(), profile)

    assert code == 1
    assert result["status"] == "pending"
    assert "sparse_profile_summary" in result["reason_codes"]
