from __future__ import annotations

import csv
import os
import sqlite3
import sys
import types
from pathlib import Path

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
from aqs.profiler_tools import _execution_entrypoint_command, _profile_output_prefix, reduce_ncu_artifacts, reduce_nsys_artifacts
from aqs.tnprobe import ProbeConfig, run_exact_tn_probe


def _require_ovh_profile_host(profile: dict[str, object]) -> None:
    if profile.get("gpu_model") != "Quadro RTX 5000":
        pytest.skip("canonical live profiler tests are pinned to the OVH Quadro RTX 5000 host")


def _require_live_profiler_opt_in() -> None:
    if os.environ.get("AQS_RUN_LIVE_PROFILER_TESTS") != "1":
        pytest.skip("set AQS_RUN_LIVE_PROFILER_TESTS=1 to run live Nsight integration tests")


def _real_stack_is_available(profile: dict[str, object] | None = None) -> bool:
    profile = profile or collect_system_profile()
    required = ("gpu_present", "cupy_present", "cuquantum_present", "qiskit_present")
    return all(bool(profile.get(key)) for key in required)


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


def test_cuquantum_required_probe_reflects_real_stack_availability():
    manifest = load_yaml("workloads/manifests/imported/qiskit_qasm2_ghz3.yaml")
    probe = run_exact_tn_probe(manifest, ProbeConfig(probe_strategy="cuquantum_required"))
    if _real_stack_is_available():
        assert probe["status"] == "success"
        assert probe["raw_info_json"]["probe_source"] == "cuquantum_circuit_to_einsum"
        assert probe["raw_info_json"]["error_message"] is None
    else:
        assert probe["status"] == "unsupported"
        assert "cuQuantum/Qiskit-backed real circuit conversion" in probe["raw_info_json"]["error_message"]


def test_require_real_execute_reflects_real_stack_availability():
    payload = execute_selected_plan(
        "workloads/manifests/imported/qiskit_qasm2_ghz3.yaml",
        "configs/systems/cpu_probe.yml",
        measurement_repeats=2,
        allow_distributed=False,
        execution_intent="require_real",
    )
    run = payload["execution_run"]
    assert run["execution_source"] == REAL_EXECUTION_SOURCE
    if _real_stack_is_available():
        assert run["status"] == "success"
        assert run["ttfr_s"] is not None
        assert run["failure_detail_json"]["execution_intent"] == "require_real"
    else:
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
        float32 = np.float32

        class cuda:  # noqa: D401 - simple test double
            class Device:
                def use(self) -> None:
                    return None

            @staticmethod
            def get_current_stream() -> FakeStream:
                return FakeStream()

        @staticmethod
        def get_default_memory_pool() -> FakePool:
            return FakePool()

        @staticmethod
        def empty(shape, dtype=None):
            return np.empty(shape, dtype=dtype)

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
    assert "calibration_ttfr" not in run["failure_detail_json"]
    assert bundle["accuracy_eval"]["status"] == "pass"
    fake_network = FakeNetwork.instances[-1]
    assert fake_network.options["memory_limit"] in {int(1.5 * (1024 ** 3)), "1.500000 GiB", 1.5}
    assert fake_network.path_optimize == {"samples": 8}
    assert fake_network.autotune_kwargs == {"iterations": 5, "release_workspace": False}
    assert fake_network.release_workspace_flags[:-1] == [False, False, False, False]
    assert fake_network.release_workspace_flags[-1] is True
    assert np.allclose(np.asarray(bundle["result"]), np.asarray(bundle["warm_result"]))
    assert bundle["driver_timing_json"]["real_execute_s"] == run["wall_s"]
    assert bundle["driver_timing_json"]["post_execution_s"] >= 0.0
    assert bundle["driver_timing_json"]["network_build_s"] >= 0.0
    assert run["failure_detail_json"]["prewarm_mode"] == "none"
    assert run["failure_detail_json"]["prewarm_wall_s"] == 0.0
    assert run["failure_detail_json"]["prewarm_success"] is None
    assert run["failure_detail_json"]["pre_execute_request_validation_s"] >= 0.0
    assert run["failure_detail_json"]["import_real_stack_s"] >= 0.0
    assert run["failure_detail_json"]["network_build_s"] >= 0.0
    assert run["failure_detail_json"]["post_execution_s"] >= 0.0


def test_nvtx_phase_names_are_stable():
    assert NVTX_DOMAIN == "aqs"
    assert NVTX_PHASE_VERSION == "aqs.nvtx.v1"
    assert NVTX_PHASES == (
        "load_circuit",
        "convert_to_einsum",
        "contract_path",
        "autotune",
        "contract_first",
        "graph_capture",
        "contract_warm",
        "graph_replay_warm",
        "graph_replay_steady",
        "postprocess",
    )


def test_profile_output_prefix_is_deterministic():
    first = _profile_output_prefix("nsys", "workloads/manifests/imported/real_ghz3_amplitude.yaml", 1)
    second = _profile_output_prefix("nsys", "workloads/manifests/imported/real_ghz3_amplitude.yaml", 1)
    third = _profile_output_prefix("nsys", "workloads/manifests/imported/real_ghz3_amplitude.yaml", 1, graph_mode="steady_state")
    fourth = _profile_output_prefix("ncu", "workloads/manifests/imported/real_dense_ring6_batched.yaml", 1, graph_mode="steady_state", variant="diagnostic")
    assert first == second
    assert first != third
    assert third != fourth


def test_profiler_execution_entrypoint_carries_graph_mode():
    command = _execution_entrypoint_command(
        manifest_path="workloads/manifests/imported/real_ghz3_amplitude.yaml",
        system_manifest_path="configs/systems/ovh_gra9_rtx5000_28.yml",
        plan_rank=1,
        objective="ttfr",
        probe_strategy="structural_real",
        planner_budget="balanced",
        allow_distributed=False,
        measurement_repeats=2,
        execution_intent="require_real",
        graph_mode="warm_only",
        out_path=Path("artifacts/profiles/run.execution.json"),
    )
    assert "--graph-mode" in command
    assert "warm_only" in command


@pytest.mark.db
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
        {"execution_run": {"run_id": "run_fixture", "graph_mode": "warm_only", "failure_detail_json": {}}},
        sqlite_path,
        {"nvtxsum": nvtx_csv, "gpukernsum": kern_csv, "cudaapisum": api_csv},
        tmp_path / "sample.nsys-rep",
    )
    assert summary["profiler_kind"] == "nsys"
    assert summary["nvtx_phase_times_json"]["contract_first"] == pytest.approx(1.0e-6)
    assert summary["top_kernels_json"][0]["name"] == "kernel_a"
    assert summary["derived_signals_json"]["graph_mode"] == "warm_only"
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
        {
            "execution_run": {
                "run_id": "run_fixture",
                "graph_mode": "steady_state",
                "wall_s": 0.012,
                "ttfr_s": 0.003,
                "steady_iter_ms": 0.9,
                "failure_detail_json": {
                    "phase_times": {
                        "contract_path": 0.0004,
                        "contract_first": 0.0012,
                    }
                },
            },
            "repeat_count_hint": 8,
        },
        tmp_path / "sample.ncu-rep",
        csv_path,
        profile_mode="diagnostic",
        metric_config={"set": "full", "replay_mode": "kernel"},
    )
    assert summary["profiler_kind"] == "ncu"
    assert summary["top_kernels_json"][0]["name"] == "contract_kernel"
    assert summary["dram_util_pct"] == pytest.approx(72.5)
    assert summary["sm_util_pct"] == pytest.approx(51.0)
    assert summary["occupancy_pct"] == pytest.approx(48.0)
    assert summary["nvtx_phase_times_json"]["contract_path"] == pytest.approx(0.0004)
    assert summary["derived_signals_json"]["profile_mode"] == "diagnostic"
    assert summary["derived_signals_json"]["graph_mode"] == "steady_state"
    assert summary["derived_signals_json"]["ncu_parse_source"] == "csv_fallback"
    assert summary["derived_signals_json"]["memory_bound_signal"] == "high"


def test_reduce_ncu_artifacts_prefers_report_import_text_over_csv_fallback(tmp_path):
    csv_path = tmp_path / "sample.ncu.csv"
    csv_path.write_text("Kernel Name,Kernel Time (ns)\ncsv_kernel,1000\n", encoding="utf-8")
    summary = reduce_ncu_artifacts(
        {
            "execution_run": {
                "run_id": "run_fixture",
                "graph_mode": "warm_only",
                "wall_s": 0.01,
                "ttfr_s": 0.004,
                "steady_iter_ms": 1.2,
                "failure_detail_json": {},
            },
            "repeat_count_hint": 4,
        },
        tmp_path / "sample.ncu-rep",
        csv_path,
        imported_csv_text="Kernel Name,Kernel Time (ns)\nreport_kernel,4000\n",
        profile_mode="basic",
        metric_config={"set": "basic", "replay_mode": "kernel"},
    )
    assert summary["top_kernels_json"][0]["name"] == "report_kernel"
    assert summary["derived_signals_json"]["ncu_parse_source"] == "ncu_report_import"


def test_real_executor_graph_mode_captures_and_replays(monkeypatch):
    manifest = load_yaml("workloads/manifests/imported/qiskit_qasm2_ghz3.yaml")
    reference_result = np.asarray(1.0 + 0.0j, dtype=np.complex128)

    class FakeCapturedGraph:
        def __init__(self):
            self.launch_calls = 0

        def launch(self, stream=None):
            self.launch_calls += 1
            return np.asarray(reference_result)

    class FakeStream:
        def __init__(self):
            self.graph = FakeCapturedGraph()
            self.capture_calls = 0
            self.end_calls = 0

        def begin_capture(self, mode=None):
            self.capture_calls += 1
            return None

        def end_capture(self):
            self.end_calls += 1
            return self.graph

        def synchronize(self):
            return None

    class FakePool:
        def used_bytes(self) -> int:
            return 1024 * 1024

    class FakeCuPy:
        def __init__(self):
            self._stream = FakeStream()
            self.cuda = type("Cuda", (), {"get_current_stream": lambda _self: self._stream})()

        def get_default_memory_pool(self) -> FakePool:
            return FakePool()

    fake_cupy = FakeCuPy()

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
            self.release_workspace_flags: list[bool] = []
            FakeNetwork.instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def contract_path(self, optimize=None):
            return ([], type("Info", (), {"largest_intermediate": 4, "opt_cost": 7.0, "num_slices": 1})())

        def contract(self, release_workspace=False):
            self.release_workspace_flags.append(bool(release_workspace))
            return np.asarray(reference_result)

    monkeypatch.setattr("aqs.execution_real.maybe_load_qiskit_circuit", lambda manifest: FakeCircuit())
    monkeypatch.setattr("aqs.execution_real._import_real_stack", lambda: (fake_cupy, FakeNetwork, FakeConverter))
    monkeypatch.setattr("aqs.execution_real._reference_result_from_qiskit_circuit", lambda circuit, target: reference_result)

    bundle = execute_real_plan_candidate(
        manifest,
        {
            "plan_id": "plan_real_graph_fake",
            "mode": "exact_tn",
            "workspace_gb": 1.0,
            "hyper_samples": 4,
            "autotune": False,
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
                "graph_mode": "steady_state",
            },
        )(),
    )

    run = bundle["execution_run"]
    details = run["failure_detail_json"]
    fake_network = FakeNetwork.instances[-1]
    assert run["graph_mode"] == "steady_state"
    assert details["graph_capture_status"] == "captured"
    assert details["graph_replay_phase"] == "graph_replay_steady"
    assert details["graph_replay_launch_count"] == 3
    assert "graph_capture" in details["phase_times"]
    assert "graph_replay_steady" in details["phase_times"]
    assert fake_network.release_workspace_flags == [False, False, True]
    assert fake_cupy._stream.capture_calls == 1
    assert fake_cupy._stream.end_calls == 1
    assert fake_cupy._stream.graph.launch_calls == 3


def test_real_executor_ttfr_repeats_emits_calibration_samples(monkeypatch):
    manifest = load_yaml("workloads/manifests/imported/qiskit_qasm2_ghz3.yaml")
    reference_result = np.asarray(1.0 + 0.0j, dtype=np.complex128)

    class FakeStream:
        def synchronize(self) -> None:
            return None

    class FakePool:
        def used_bytes(self) -> int:
            return 1024 * 1024

    class FakeCuPy:
        class cuda:
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
            self.release_workspace_flags: list[bool] = []
            FakeNetwork.instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def contract_path(self, optimize=None):
            return ([], type("Info", (), {"largest_intermediate": 4, "opt_cost": 7.0, "num_slices": 1})())

        def autotune(self, iterations=None, release_workspace=None):
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
            "plan_id": "plan_real_ttfr_repeat_fake",
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
                "ttfr_repeats": 3,
            },
        )(),
    )

    details = bundle["execution_run"]["failure_detail_json"]
    calibration = details["calibration_ttfr"]
    assert calibration["mode"] == "fresh_network_cold_path"
    assert calibration["ttfr_repeats"] == 3
    assert len(calibration["ttfr_samples_s"]) == 3
    assert len(calibration["planner_time_samples_s"]) == 3
    assert len(calibration["setup_time_samples_s"]) == 3
    assert len(calibration["first_contract_samples_s"]) == 3
    assert calibration["ttfr_stats"]["count"] == 3
    assert calibration["planner_time_stats"]["count"] == 3
    assert len(FakeNetwork.instances) == 3


@pytest.mark.parametrize("prewarm_mode", ["import_context", "tiny_network"])
def test_real_executor_emits_prewarm_provenance(monkeypatch, prewarm_mode):
    manifest = load_yaml("workloads/manifests/imported/qiskit_qasm2_ghz3.yaml")
    reference_result = np.asarray(1.0 + 0.0j, dtype=np.complex128)

    class FakeStream:
        def synchronize(self) -> None:
            return None

    class FakeDevice:
        def use(self) -> None:
            return None

    class FakePool:
        def used_bytes(self) -> int:
            return 1024 * 1024

    class FakeCuPy:
        float32 = np.float32

        class cuda:
            @staticmethod
            def get_current_stream() -> FakeStream:
                return FakeStream()

            Device = FakeDevice

        @staticmethod
        def get_default_memory_pool() -> FakePool:
            return FakePool()

        @staticmethod
        def empty(shape, dtype=None):
            return np.empty(shape, dtype=dtype)

    class FakeCircuit:
        qubits = [0, 1, 2]

    class FakeConverter:
        def __init__(self, circuit, dtype, backend):
            self.circuit = circuit
            self.dtype = dtype
            self.backend = backend

        def amplitude(self, bitstring):
            return "abc->", [np.ones((1,), dtype=np.complex128)]

    class FakeNetwork:
        def __init__(self, expr, *operands, options=None):
            self.expr = expr
            self.operands = operands
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def contract_path(self, optimize=None):
            return ([], type("Info", (), {"largest_intermediate": 4, "opt_cost": 7.0, "num_slices": 1})())

        def contract(self, release_workspace=False):
            return np.asarray(reference_result)

    fake_qiskit = types.ModuleType("qiskit")

    class FakeQuantumCircuit:
        def __init__(self, qubit_count: int):
            self.qubit_count = qubit_count

        def h(self, qubit_index: int) -> None:
            return None

    fake_qiskit.QuantumCircuit = FakeQuantumCircuit
    monkeypatch.setitem(sys.modules, "qiskit", fake_qiskit)
    monkeypatch.setattr("aqs.execution_real.maybe_load_qiskit_circuit", lambda manifest: FakeCircuit())
    monkeypatch.setattr("aqs.execution_real._import_real_stack", lambda: (FakeCuPy(), FakeNetwork, FakeConverter))
    monkeypatch.setattr("aqs.execution_real._reference_result_from_qiskit_circuit", lambda circuit, target: reference_result)

    bundle = execute_real_plan_candidate(
        manifest,
        {
            "plan_id": "plan_real_prewarm_fake",
            "mode": "exact_tn",
            "workspace_gb": 1.0,
            "hyper_samples": 2,
            "autotune": False,
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
                "measurement_repeats": 2,
                "probe_strategy": "structural_real",
                "prewarm_mode": prewarm_mode,
            },
        )(),
    )

    details = bundle["execution_run"]["failure_detail_json"]
    assert details["prewarm_mode"] == prewarm_mode
    assert details["prewarm_success"] is True
    assert details["prewarm_wall_s"] >= 0.0
    assert bundle["driver_timing_json"]["pre_t_start_overhead_s"] >= details["prewarm_wall_s"]


@pytest.mark.gpu
@pytest.mark.profiler
def test_live_nsys_profile_real_slice(tmp_path):
    _require_live_profiler_opt_in()
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
    _require_live_profiler_opt_in()
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
