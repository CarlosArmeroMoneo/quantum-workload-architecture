from __future__ import annotations

import duckdb
import pytest

from aqs.arch import analyze_execution_payload
from aqs.db import apply_schema
from aqs.doctor import collect_system_profile
from aqs.execution_real import REAL_EXECUTION_SOURCE


def _require_ovh_profile_host(profile: dict[str, object]) -> None:
    if profile.get("gpu_model") != "Quadro RTX 5000":
        pytest.skip("canonical live profiler tests are pinned to the OVH Quadro RTX 5000 host")


@pytest.mark.gpu
@pytest.mark.profiler
def test_live_nsys_profile_real_amplitude_persists_rows_and_real_arch_nomination(tmp_path):
    profile = collect_system_profile()
    required = {"cupy_present", "cuquantum_present", "qiskit_present", "nsys_present"}
    if not all(bool(profile.get(key)) for key in required):
        pytest.skip("real Nsight Systems environment is not available")
    _require_ovh_profile_host(profile)

    from aqs.profiler_tools import run_nsys_profile

    db_path = tmp_path / "warehouse.duckdb"
    apply_schema(db_path)
    payload = run_nsys_profile(
        manifest_path="workloads/manifests/imported/real_ghz3_amplitude.yaml",
        system_manifest_path="configs/systems/ovh_gra9_rtx5000_28.yml",
        outdir=tmp_path / "nsys",
        measurement_repeats=2,
        db_path=db_path,
    )

    run = payload["execution_run"]
    assert run["execution_source"] == REAL_EXECUTION_SOURCE
    assert payload["profile_summary"]["profiler_kind"] == "nsys"
    assert any(asset["role"] == "nsys_report" for asset in payload["linked_assets"])
    assert payload["profile_summary"]["nvtx_phase_times_json"] or payload["profile_summary"]["top_kernels_json"]

    conn = duckdb.connect(str(db_path))
    try:
        attempt_count = conn.execute(
            "SELECT count(*) FROM profiling.profiler_attempt WHERE run_id = ? AND tool_kind = 'nsys' AND attempt_role = 'profile'",
            [run["run_id"]],
        ).fetchone()[0]
        profile_count = conn.execute(
            "SELECT count(*) FROM profiling.profile_summary WHERE run_id = ? AND profiler_kind = 'nsys'",
            [run["run_id"]],
        ).fetchone()[0]
    finally:
        conn.close()

    assert attempt_count >= 1
    assert profile_count == 1

    analysis = analyze_execution_payload(payload)
    assert any(row["nomination_source"] == "real_profiler_analysis" for row in analysis["nominations"])


@pytest.mark.gpu
@pytest.mark.profiler
def test_live_ncu_profile_real_batched_persists_rows_and_real_metrics(tmp_path):
    profile = collect_system_profile()
    required = {"cupy_present", "cuquantum_present", "qiskit_present", "ncu_present"}
    if not all(bool(profile.get(key)) for key in required):
        pytest.skip("real Nsight Compute environment is not available")
    _require_ovh_profile_host(profile)

    from aqs.profiler_tools import run_ncu_profile

    db_path = tmp_path / "warehouse.duckdb"
    apply_schema(db_path)
    payload = run_ncu_profile(
        manifest_path="workloads/manifests/imported/real_dense_ring6_batched.yaml",
        system_manifest_path="configs/systems/ovh_gra9_rtx5000_28.yml",
        outdir=tmp_path / "ncu",
        measurement_repeats=2,
        db_path=db_path,
    )

    run = payload["execution_run"]
    summary = payload["profile_summary"]
    assert run["execution_source"] == REAL_EXECUTION_SOURCE
    assert summary["profiler_kind"] == "ncu"
    assert any(asset["role"] == "ncu_report" for asset in payload["linked_assets"])
    assert summary["top_kernels_json"] or any(summary.get(metric) is not None for metric in ("dram_util_pct", "sm_util_pct", "occupancy_pct"))
    assert payload["profiler_attempt"]["state_json"]["kernel_seen"] is True

    conn = duckdb.connect(str(db_path))
    try:
        attempt_count = conn.execute(
            "SELECT count(*) FROM profiling.profiler_attempt WHERE run_id = ? AND tool_kind = 'ncu' AND attempt_role = 'profile'",
            [run["run_id"]],
        ).fetchone()[0]
        profile_count = conn.execute(
            "SELECT count(*) FROM profiling.profile_summary WHERE run_id = ? AND profiler_kind = 'ncu'",
            [run["run_id"]],
        ).fetchone()[0]
    finally:
        conn.close()

    assert attempt_count >= 1
    assert profile_count == 1
