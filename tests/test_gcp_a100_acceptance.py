from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "validate_gcp_a100_acceptance.py"
GATE = REPO_ROOT / "configs" / "profiling" / "gcp_a100_acceptance_gate.yaml"


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_csv(path: Path) -> Path:
    path.write_text(
        "Kernel Name,Device,CC,device__attribute_display_name\n"
        "cutensor_contraction_kernel,0,8.0,NVIDIA A100-SXM4-40GB\n",
        encoding="utf-8",
    )
    return path


def _base_payloads(tmp_path: Path) -> dict[str, dict[str, Any]]:
    execution = {
        "accuracy_eval": {"status": "pass"},
        "execution_run": {
            "run_id": "run_a100_ok",
            "status": "success",
            "execution_source": "cuquantum_tensornet_gpu",
            "failure_detail_json": {
                "execution_source": "cuquantum_tensornet_gpu",
                "execution_target": {"kind": "amplitude", "bitstring": "000"},
                "phase_times": {"contract_first": 0.002},
            },
            "workload_id": "wkl_ghz3",
        },
        "probe": {"raw_info_json": {"qubit_count": 3}},
        "selected_plan": {"gpu_arch_target": "sm80"},
        "system_manifest": {
            "system_name": "gcp_a100_sxm4_40gb",
            "gpu_model": "NVIDIA A100-SXM4-40GB",
            "gpu_arch_target": "sm80",
            "gpu_mem_gb": 40,
        },
    }
    profile = {
        "run_id": "run_a100_ok",
        "profiler_kind": "ncu",
        "derived_signals_json": {
            "profile_source": "real_ncu_profile",
            "csv_nonempty": True,
            "ncu_csv_path": "accepted.ncu.csv",
        },
        "top_kernels_json": [{"kind": "gpu_kernel", "name": "cutensor_contraction_kernel"}],
    }
    artifact_manifest = {
        "api_version": "qwa.gcp_a100_artifacts.v1",
        "interpretation_class": "portability_validation",
        "throughput_benchmark": False,
        "workload": {"manifest": "workloads/manifests/imported/real_ghz3_amplitude.yaml"},
        "execution_json": {"repo_path": "evidence/gcp_a100/real_ghz3.ncu.abcdef.execution.json"},
        "profile_summary_json": {"repo_path": "evidence/gcp_a100/real_ghz3.ncu.abcdef.profile_summary.json"},
        "csv": {"repo_path": "evidence/gcp_a100/real_ghz3.ncu.abcdef.ncu.csv"},
    }
    _write_csv(tmp_path / "accepted.ncu.csv")
    return {
        "execution": execution,
        "profile": profile,
        "artifact_manifest": artifact_manifest,
    }


def _write_fixture_set(tmp_path: Path, payloads: dict[str, dict[str, Any]]) -> dict[str, Path]:
    return {
        "execution": _write_json(tmp_path / "real_ghz3.ncu.abcdef.execution.json", payloads["execution"]),
        "profile": _write_json(tmp_path / "real_ghz3.ncu.abcdef.profile_summary.json", payloads["profile"]),
        "artifact_manifest": _write_json(tmp_path / "real_ghz3.ncu.abcdef.artifacts.json", payloads["artifact_manifest"]),
    }


def _run_validator(*args: str) -> tuple[int, dict[str, Any]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--gate", str(GATE), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.stderr == ""
    return completed.returncode, json.loads(completed.stdout)


def test_accepts_a100_portability_evidence_from_evidence_dir(tmp_path: Path):
    _write_fixture_set(tmp_path, _base_payloads(tmp_path))

    code, result = _run_validator("--evidence-dir", str(tmp_path))

    assert code == 0
    assert result["status"] == "accepted"
    assert result["gpu_model"] == "NVIDIA A100-SXM4-40GB"
    assert result["gpu_arch_target"] == "sm80"
    assert result["profile_source"] == "real_ncu_profile"
    assert result["interpretation_class"] == "portability_validation"
    assert result["tiny_workload"] is True
    assert result["throughput_benchmark"] is False
    assert result["rejections"] == []
    assert result["pending"] == []


def test_rejects_wrong_gpu_l4_evidence(tmp_path: Path):
    payloads = _base_payloads(tmp_path)
    payloads["execution"] = copy.deepcopy(payloads["execution"])
    payloads["execution"]["system_manifest"].update(
        {
            "gpu_model": "NVIDIA L4",
            "gpu_arch_target": "sm89",
            "gpu_mem_gb": 24,
        }
    )
    paths = _write_fixture_set(tmp_path, payloads)

    code, result = _run_validator(
        "--execution",
        str(paths["execution"]),
        "--profile-summary",
        str(paths["profile"]),
        "--artifact-manifest",
        str(paths["artifact_manifest"]),
    )

    assert code == 2
    assert result["status"] == "rejected"
    rejected_names = {check["name"] for check in result["rejections"]}
    assert {"gpu_model", "gpu_arch_target", "gpu_memory"} <= rejected_names


def test_missing_profile_summary_is_pending_not_rejected(tmp_path: Path):
    paths = _write_fixture_set(tmp_path, _base_payloads(tmp_path))
    paths["profile"].unlink()

    code, result = _run_validator(
        "--execution",
        str(paths["execution"]),
        "--artifact-manifest",
        str(paths["artifact_manifest"]),
    )

    assert code == 1
    assert result["status"] == "pending"
    assert result["rejections"] == []
    pending_names = {check["name"] for check in result["pending"]}
    assert "profile_summary" in pending_names
    assert "profile_summary_input" in pending_names


def test_rejects_tiny_workload_throughput_overclaim(tmp_path: Path):
    payloads = _base_payloads(tmp_path)
    payloads["artifact_manifest"] = copy.deepcopy(payloads["artifact_manifest"])
    payloads["artifact_manifest"]["throughput_benchmark"] = True
    paths = _write_fixture_set(tmp_path, payloads)

    code, result = _run_validator(
        "--execution",
        str(paths["execution"]),
        "--profile-summary",
        str(paths["profile"]),
        "--artifact-manifest",
        str(paths["artifact_manifest"]),
    )

    assert code == 2
    assert result["status"] == "rejected"
    assert any(check["name"] == "tiny_workload_throughput_claim" for check in result["rejections"])


def test_rejects_wildcard_artifact_path(tmp_path: Path):
    payloads = _base_payloads(tmp_path)
    payloads["artifact_manifest"] = copy.deepcopy(payloads["artifact_manifest"])
    payloads["artifact_manifest"]["csv"]["repo_path"] = "evidence/gcp_a100/*.ncu.csv"
    paths = _write_fixture_set(tmp_path, payloads)

    code, result = _run_validator(
        "--execution",
        str(paths["execution"]),
        "--profile-summary",
        str(paths["profile"]),
        "--artifact-manifest",
        str(paths["artifact_manifest"]),
    )

    assert code == 2
    assert result["status"] == "rejected"
    assert any(check["name"] == "artifact_paths" for check in result["rejections"])
