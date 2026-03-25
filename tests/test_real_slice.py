from __future__ import annotations

import csv
import sqlite3

import numpy as np
import pytest

from aqs.doctor import collect_system_profile
from aqs.db import apply_schema, upsert_asset_file
from aqs.execution import execute_selected_plan
from aqs.execution_real import (
    REAL_EXECUTION_SOURCE,
    RealExecutionError,
    execute_real_plan_candidate,
    validate_real_execution_request,
)
from aqs.manifest import load_yaml, validate_workload_manifest
from aqs.nvtx import NVTX_DOMAIN, NVTX_PHASES, NVTX_PHASE_VERSION
from aqs.profiler_tools import _profile_output_prefix, reduce_ncu_artifacts, reduce_nsys_artifacts
from aqs.tnprobe import ProbeConfig, run_exact_tn_probe


def _require_ovh_profile_host(profile: dict[str, object]) -> None:
    if profile.get("gpu_model") != "Quadro RTX 5000":
        pytest.skip("canonical live profiler tests are pinned to the OVH Quadro RTX 5000 host")


def _inline_manifest(qasm_text: str, *, execution_target: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "api_version": "aqs.workload.v1",
        "family_id": "dense_universal",
        "family_version": "0.2.0",
        "generator_name": "imported_qasm2",
        "generator_version": "0.2.0",
        "source_format": "qiskit",
        "source": {
            "loader": "qasm2_inline",
            "text": qasm_text,
        },
        "semantic_target": "amplitude",
        "execution_target": execution_target or {"kind": "amplitude", "bitstring": "0"},
        "reference_tier": "smoke",
        "split_tag": "demo",
        "repeat_count_hint": 1,
        "parameters": {
            "n_qubits": 1,
            "depth": 1,
            "topology": "ring",
            "two_qubit_density": "low",
            "measurement_pattern": "terminal_observable_only",
        },
        "ids": {
            "workload_id": "wkl_inline_test",
            "source_hash": "inline",
        },
    }


def test_manifest_requires_execution_target_for_imported_amplitude():
    manifest = _inline_manifest(
        "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[1];\nh q[0];\n",
        execution_target=None,
    )
    manifest.pop("execution_target", None)
    errors = validate_workload_manifest(manifest)
    assert any("execution_target is required" in error for error in errors)


def test_validate_real_execution_request_rejects_reset_and_intermediate_measurement():
    system_profile = {
        "system_id": "sys_test",
        "gpu_present": True,
        "cupy_present": True,
        "cuquantum_present": True,
        "qiskit_present": True,
    }
    reset_manifest = _inline_manifest(
        "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[1];\nreset q[0];\n",
    )
    with pytest.raises(RealExecutionError) as reset_error:
        validate_real_execution_request(reset_manifest, system_profile=system_profile)
    assert reset_error.value.code == "reset_present"

    meas_manifest = _inline_manifest(
        "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[1];\ncreg c[1];\nh q[0];\nmeasure q[0] -> c[0];\nh q[0];\n",
    )
    with pytest.raises(RealExecutionError) as meas_error:
        validate_real_execution_request(meas_manifest, system_profile=system_profile)
    assert meas_error.value.code == "intermediate_measurement_present"


def test_cuquantum_required_probe_fails_precisely_without_stack():
    manifest = load_yaml("workloads/manifests/imported/qiskit_qasm2_ghz3.yaml")
    probe = run_exact_tn_probe(manifest, ProbeConfig(probe_strategy="cuquantum_required"))
    assert probe["status"] == "unsupported"
    assert "cuQuantum/Qiskit-backed real circuit conversion" in probe["raw_info_json"]["error_message"]


def test_require_real_execute_fails_with_precise_reason_when_stack_missing():
    payload = execute_selected_plan(
        "workloads/manifests/imported/qiskit_qasm2_ghz3.yaml",
        "configs/systems/cpu_probe.yml",
        measurement_repeats=2,
        allow_distributed=False,
        execution_intent="require_real",
    )
    run = payload["execution_run"]
    assert run["execution_source"] == REAL_EXECUTION_SOURCE
    assert run["status"] == "runtime_error"
    assert run["failure_detail_json"]["reason_code"] in {"missing_cupy", "missing_cuquantum", "missing_qiskit", "missing_gpu"}


def test_real_executor_maps_plan_fields_and_keeps_warm_outputs_identical(monkeypatch):
    manifest = load_yaml("workloads/manifests/imported/qiskit_qasm2_ghz3.yaml")
    reference_result = np.asarray(1.0 + 0.0j, dtype=np.complex128)

    class FakeStream:
        def synchronize(self) -> None:
            return None

    class FakePool:
        def used_bytes(self) -> int:
            return 1024 * 1024

    class FakeCuPy:
        class cuda:  # noqa: D401 - simple test double
            @staticmethod
            def get_current_stream() -> FakeStream:
                return FakeStream()

        @staticmethod
        def get_default_memory_pool() -> FakePool:
            return FakePool()

    class FakeCircuit:
        qubits = [0, 1, 2]

    class FakeConverter:
        def __init__(self, circuit, dtype, backend):
            self.circuit = circuit
            self.dtype = dtype
            self.backend = backend

        def amplitude(self, bitstring):
            assert bitstring == "000"
            return "abc->", [np.ones((1,), dtype=np.complex128)]

    class FakeNetwork:
        instances: list["FakeNetwork"] = []

        def __init__(self, expr, *operands, options=None):
            self.expr = expr
            self.operands = operands
            self.options = options
            self.path_optimize = None
            self.autotune_kwargs = None
            self.release_workspace_flags: list[bool] = []
            FakeNetwork.instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def contract_path(self, optimize=None):
            self.path_optimize = optimize
            return ([], type("Info", (), {"largest_intermediate": 4, "opt_cost": 7.0, "num_slices": 1})())

        def autotune(self, iterations=None, release_workspace=None):
            self.autotune_kwargs = {"iterations": iterations, "release_workspace": release_workspace}
            return None

        def contract(self, release_workspace=False):
            self.release_workspace_flags.append(bool(release_workspace))
            return np.asarray(reference_result)

    monkeypatch.setattr("aqs.execution_real.maybe_load_qiskit_circuit", lambda manifest: FakeCircuit())
    monkeypatch.setattr("aqs.execution_real._import_real_stack", lambda: (FakeCuPy(), FakeNetwork, FakeConverter))
    monkeypatch.setattr("aqs.execution_real._reference_result_from_qiskit_circuit", lambda circuit, target: reference_result)

    bundle = execute_real_plan_candidate(
        manifest,
        {
            "plan_id": "plan_real_fake",
            "mode": "exact_tn",
            "workspace_gb": 1.5,
            "hyper_samples": 8,
            "autotune": True,
            "precision": "complex128",
        },
        system_profile={
            "system_id": "sys_fake",
            "gpu_present": True,
            "cupy_present": True,
            "cuquantum_present": True,
            "qiskit_present": True,
            "nsys_present": False,
            "ncu_present": False,
        },
        config=type(
            "Cfg",
            (),
            {
                "precision": "complex128",
                "measurement_repeats": 3,
                "probe_strategy": "structural_real",
            },
        )(),
    )

    run = bundle["execution_run"]
    assert run["status"] == "success"
    assert run["execution_source"] == REAL_EXECUTION_SOURCE
    assert bundle["accuracy_eval"]["status"] == "pass"
    fake_network = FakeNetwork.instances[-1]
    assert fake_network.options["memory_limit"] in {int(1.5 * (1024 ** 3)), "1.500000 GiB", 1.5}
    assert fake_network.path_optimize == {"samples": 8}
    assert fake_network.autotune_kwargs == {"iterations": 5, "release_workspace": False}
    assert fake_network.release_workspace_flags[:-1] == [False, False, False, False]
    assert fake_network.release_workspace_flags[-1] is True
    assert np.allclose(np.asarray(bundle["result"]), np.asarray(bundle["warm_result"]))


def test_nvtx_phase_names_are_stable():
    assert NVTX_DOMAIN == "aqs"
    assert NVTX_PHASE_VERSION == "aqs.nvtx.v1"
    assert NVTX_PHASES == (
        "load_circuit",
        "convert_to_einsum",
        "contract_path",
        "autotune",
        "contract_first",
        "contract_warm",
        "postprocess",
    )


def test_profile_output_prefix_is_deterministic():
    first = _profile_output_prefix("nsys", "workloads/manifests/imported/real_ghz3_amplitude.yaml", 1)
    second = _profile_output_prefix("nsys", "workloads/manifests/imported/real_ghz3_amplitude.yaml", 1)
    third = _profile_output_prefix("ncu", "workloads/manifests/imported/real_dense_ring6_batched.yaml", 1)
    assert first == second
    assert first != third


def test_asset_indexing_is_deterministic(tmp_path):
    db_path = tmp_path / "aqs.duckdb"
    apply_schema(db_path)
    asset_path = tmp_path / "sample.json"
    asset_path.write_text('{"ok": true}', encoding="utf-8")
    first = upsert_asset_file(db_path, asset_path, asset_type="json")
    second = upsert_asset_file(db_path, asset_path, asset_type="json")
    assert first["asset_id"] == second["asset_id"]


def test_reduce_nsys_artifacts_from_fixture_exports(tmp_path):
    sqlite_path = tmp_path / "sample.sqlite"
    conn = sqlite3.connect(str(sqlite_path))
    conn.execute("CREATE TABLE sample(value INTEGER)")
    conn.commit()
    conn.close()

    nvtx_csv = tmp_path / "nvtxsum.csv"
    with nvtx_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Range Name", "Total Time (ns)"])
        writer.writeheader()
        writer.writerow({"Range Name": "aqs@contract_first", "Total Time (ns)": "1000"})
    kern_csv = tmp_path / "gpukernsum.csv"
    with kern_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Kernel Name", "Total Time (ns)"])
        writer.writeheader()
        writer.writerow({"Kernel Name": "kernel_a", "Total Time (ns)": "2000"})
    api_csv = tmp_path / "cudaapisum.csv"
    with api_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Name", "Total Time (ns)"])
        writer.writeheader()
        writer.writerow({"Name": "cudaLaunchKernel", "Total Time (ns)": "3000"})

    summary = reduce_nsys_artifacts(
        {"execution_run": {"run_id": "run_fixture", "failure_detail_json": {}}},
        sqlite_path,
        {"nvtxsum": nvtx_csv, "gpukernsum": kern_csv, "cudaapisum": api_csv},
        tmp_path / "sample.nsys-rep",
    )
    assert summary["profiler_kind"] == "nsys"
    assert summary["nvtx_phase_times_json"]["contract_first"] == pytest.approx(1.0e-6)
    assert summary["top_kernels_json"][0]["name"] == "kernel_a"
    assert "sample" in summary["derived_signals_json"]["nsys_sqlite_tables"]


def test_reduce_ncu_artifacts_from_fixture_csv(tmp_path):
    csv_path = tmp_path / "sample.ncu.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Kernel Name", "Kernel Time (ns)", "DRAM Throughput %", "SM Throughput %", "Achieved Occupancy %"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "Kernel Name": "contract_kernel",
                "Kernel Time (ns)": "4000",
                "DRAM Throughput %": "72.5",
                "SM Throughput %": "51.0",
                "Achieved Occupancy %": "48.0",
            }
        )

    summary = reduce_ncu_artifacts(
        {"execution_run": {"run_id": "run_fixture"}},
        csv_path,
        tmp_path / "sample.ncu-rep",
    )
    assert summary["profiler_kind"] == "ncu"
    assert summary["top_kernels_json"][0]["name"] == "contract_kernel"
    assert summary["dram_util_pct"] == pytest.approx(72.5)
    assert summary["sm_util_pct"] == pytest.approx(51.0)
    assert summary["occupancy_pct"] == pytest.approx(48.0)


@pytest.mark.gpu
@pytest.mark.profiler
def test_live_nsys_profile_real_slice(tmp_path):
    profile = collect_system_profile()
    required = {"cupy_present", "cuquantum_present", "qiskit_present", "nsys_present"}
    if not all(bool(profile.get(key)) for key in required):
        pytest.skip("real Nsight Systems environment is not available")
    _require_ovh_profile_host(profile)
    from aqs.profiler_tools import run_nsys_profile

    payload = run_nsys_profile(
        manifest_path="workloads/manifests/imported/real_ghz3_amplitude.yaml",
        system_manifest_path="configs/systems/ovh_gra9_rtx5000_28.yml",
        outdir=tmp_path / "nsys",
        measurement_repeats=2,
    )
    assert payload["profile_summary"]["profiler_kind"] == "nsys"
    assert any(asset["role"] == "nsys_report" for asset in payload["linked_assets"])


@pytest.mark.gpu
@pytest.mark.profiler
def test_live_ncu_profile_real_slice(tmp_path):
    profile = collect_system_profile()
    required = {"cupy_present", "cuquantum_present", "qiskit_present", "ncu_present"}
    if not all(bool(profile.get(key)) for key in required):
        pytest.skip("real Nsight Compute environment is not available")
    _require_ovh_profile_host(profile)
    from aqs.profiler_tools import run_ncu_profile

    payload = run_ncu_profile(
        manifest_path="workloads/manifests/imported/real_dense_ring6_batched.yaml",
        system_manifest_path="configs/systems/ovh_gra9_rtx5000_28.yml",
        outdir=tmp_path / "ncu",
        measurement_repeats=2,
    )
    assert payload["profile_summary"]["profiler_kind"] == "ncu"
    assert any(asset["role"] == "ncu_report" for asset in payload["linked_assets"])
