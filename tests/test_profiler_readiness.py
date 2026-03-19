from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import duckdb
import pytest

import aqs.profiler_tools as profiler_tools
from aqs.db import apply_schema
from aqs.profiler_tools import (
    ProfileToolError,
    _resolve_tool_command,
    collect_profiling_readiness,
    run_ncu_smoke,
    run_nsys_smoke,
)


def _system_profile() -> dict[str, object]:
    return {
        "system_id": "sys_test",
        "gpu_present": True,
        "cupy_present": True,
        "cuquantum_present": True,
        "qiskit_present": True,
    }


def _probe(path: str, version: str | None, *, version_error: str | None = None) -> dict[str, object]:
    return {
        "path": path,
        "present": True,
        "version": version,
        "version_error": version_error,
    }


def test_collect_profiling_readiness_classifies_importer_missing(monkeypatch, tmp_path):
    probes = {
        "nsys": _probe("/opt/nvidia/nsys", "NVIDIA Nsight Systems version 2025.3.1.0"),
        "QdstrmImporter": {"path": "/opt/nvidia/QdstrmImporter", "present": False, "version": None, "version_error": None},
        "ncu": {"path": "/usr/local/cuda/bin/ncu", "present": False, "version": None, "version_error": None},
    }
    monkeypatch.setattr("aqs.profiler_tools._tool_probe", lambda command, env=None: probes[command])

    readiness = collect_profiling_readiness(
        system_profile=_system_profile(),
        outdir=tmp_path,
        run_smoke=False,
    )

    assert readiness["nsys"]["present"] is True
    assert readiness["nsys"]["qdstrm_importer_present"] is False
    assert readiness["nsys"]["readiness_class"] == "importer_missing"
    assert readiness["profiling_ready"] is False


def test_collect_profiling_readiness_classifies_importer_runtime_blocked(monkeypatch, tmp_path):
    probes = {
        "nsys": _probe("/opt/nvidia/nsys", "NVIDIA Nsight Systems version 2025.3.1.0"),
        "QdstrmImporter": _probe(
            "/opt/nvidia/QdstrmImporter",
            None,
            version_error="QdstrmImporter: error while loading shared libraries: libdw.so.1",
        ),
        "ncu": {"path": "/usr/local/cuda/bin/ncu", "present": False, "version": None, "version_error": None},
    }
    monkeypatch.setattr("aqs.profiler_tools._tool_probe", lambda command, env=None: probes[command])

    readiness = collect_profiling_readiness(
        system_profile=_system_profile(),
        outdir=tmp_path,
        run_smoke=False,
    )

    assert readiness["nsys"]["qdstrm_importer_present"] is True
    assert readiness["nsys"]["qdstrm_importer_version"] is None
    assert readiness["nsys"]["readiness_class"] == "importer_runtime_blocked"
    assert any("libdw.so.1" in line for line in readiness["nsys"]["remediation"])
    assert readiness["profiling_ready"] is False


def test_collect_profiling_readiness_classifies_version_mismatch(monkeypatch, tmp_path):
    probes = {
        "nsys": _probe("/opt/nvidia/nsys", "NVIDIA Nsight Systems version 2025.3.1.0"),
        "QdstrmImporter": _probe("/opt/nvidia/QdstrmImporter", "QdstrmImporter version 2024.4.0.0"),
        "ncu": {"path": "/usr/local/cuda/bin/ncu", "present": False, "version": None, "version_error": None},
    }
    monkeypatch.setattr("aqs.profiler_tools._tool_probe", lambda command, env=None: probes[command])

    readiness = collect_profiling_readiness(
        system_profile=_system_profile(),
        outdir=tmp_path,
        run_smoke=False,
    )

    assert readiness["nsys"]["versions_match"] is False
    assert readiness["nsys"]["readiness_class"] == "version_mismatch"
    assert readiness["profiling_ready"] is False


def test_collect_profiling_readiness_classifies_ncu_permission_denial(monkeypatch, tmp_path):
    probes = {
        "nsys": {"path": "/opt/nvidia/nsys", "present": False, "version": None, "version_error": None},
        "QdstrmImporter": {"path": "/opt/nvidia/QdstrmImporter", "present": False, "version": None, "version_error": None},
        "ncu": _probe("/usr/local/cuda/bin/ncu", "NVIDIA Nsight Compute Command Line Profiler 2025.3.0"),
    }
    monkeypatch.setattr("aqs.profiler_tools._tool_probe", lambda command, env=None: probes[command])

    def _blocked_smoke(*, outdir=None, db_path=None):
        raise ProfileToolError(
            "ncu could not access GPU performance counters (ERR_NVGPUCTRPERM)",
            attempt={
                "attempt_id": "attempt_ncu_blocked",
                "tool_kind": "ncu",
                "attempt_role": "smoke",
                "failure_class": "gpu_counter_permission_denied",
                "remediation": [
                    "GPU counters are blocked by host policy.",
                    "Profiling requires elevated privilege or CAP_SYS_ADMIN when counters are restricted.",
                ],
                "state_json": {
                    "launcher_started": True,
                    "target_seen": True,
                    "kernel_seen": False,
                    "metrics_collected": False,
                    "report_written": False,
                },
                "usability_state": "target_seen",
            },
        )

    monkeypatch.setattr("aqs.profiler_tools.run_ncu_smoke", _blocked_smoke)

    readiness = collect_profiling_readiness(
        system_profile=_system_profile(),
        outdir=tmp_path,
        run_smoke=True,
    )

    assert readiness["ncu"]["readiness_class"] == "gpu_counter_permission_denied"
    assert readiness["ncu"]["gpu_counters_accessible"] is False
    assert any("CAP_SYS_ADMIN" in line for line in readiness["ncu"]["remediation"])


def test_resolve_tool_command_uses_known_qdstrm_importer_fallback(monkeypatch, tmp_path):
    fake_importer = tmp_path / "QdstrmImporter"
    fake_importer.write_text("", encoding="utf-8")

    monkeypatch.setattr("aqs.profiler_tools.shutil.which", lambda command, path=None: None)
    monkeypatch.setattr(profiler_tools, "TOOL_FALLBACKS", {"QdstrmImporter": [str(fake_importer)]})

    assert _resolve_tool_command("QdstrmImporter") == [str(fake_importer)]


def test_run_nsys_smoke_records_state_progression(monkeypatch, tmp_path):
    monkeypatch.setattr("aqs.profiler_tools._python_launch_env", lambda: {})
    fake_nsys = tmp_path / "nsys"
    fake_nsys.write_text("", encoding="utf-8")
    fake_importer = tmp_path / "QdstrmImporter"
    fake_importer.write_text("", encoding="utf-8")
    versions = {
        "nsys": "NVIDIA Nsight Systems version 2025.3.1.0",
        "QdstrmImporter": "QdstrmImporter version 2025.3.1.0",
    }
    monkeypatch.setattr("aqs.profiler_tools._tool_version", lambda command, env=None: versions.get(command))
    monkeypatch.setattr(
        "aqs.profiler_tools._resolve_tool_command",
        lambda command, env=None: [str(fake_importer if command == "QdstrmImporter" else fake_nsys)],
    )

    def _fake_run(command, cwd=None, env=None):
        if Path(command[0]).name == "nsys" and "profile" in command:
            smoke_payload = tmp_path / "profiler_smoke.nsys.smoke.json"
            smoke_payload.write_text(json.dumps({"checksum": 1.0}), encoding="utf-8")
            (tmp_path / "profiler_smoke.nsys.qdstrm").write_text("trace", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="collection complete", stderr="")
        if Path(command[0]).name == "QdstrmImporter":
            Path(command[command.index("--output-file") + 1]).write_text("rep", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="import complete", stderr="")
        if Path(command[0]).name == "nsys" and "export" in command:
            sqlite_path = Path(command[command.index("--output") + 1])
            conn = sqlite3.connect(str(sqlite_path))
            conn.execute("CREATE TABLE sample(value INTEGER)")
            conn.commit()
            conn.close()
            return subprocess.CompletedProcess(command, 0, stdout="sqlite export complete", stderr="")
        if Path(command[0]).name == "nsys" and "stats" in command:
            prefix = Path(command[command.index("--output") + 1])
            (prefix.parent / f"{prefix.name}_nvtxsum.csv").write_text("Range Name,Total Time (ns)\naqx@noop,1\n", encoding="utf-8")
            (prefix.parent / f"{prefix.name}_cudaapisum.csv").write_text("Name,Total Time (ns)\ncudaLaunchKernel,2\n", encoding="utf-8")
            (prefix.parent / f"{prefix.name}_gpukernsum.csv").write_text("Kernel Name,Total Time (ns)\nsmoke_kernel,3\n", encoding="utf-8")
            (prefix.parent / f"{prefix.name}_nvtxsum.csv").write_text("Range Name,Total Time (ns)\naqs_smoke@smoke_kernel,1\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="stats export complete", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("aqs.profiler_tools._run", _fake_run)

    payload = run_nsys_smoke(outdir=tmp_path)
    attempt = payload["profiler_attempt"]

    assert attempt["state_json"]["collection_started"] is True
    assert attempt["state_json"]["qdstrm_produced"] is True
    assert attempt["state_json"]["rep_converted"] is True
    assert attempt["state_json"]["sqlite_exported"] is True
    assert attempt["state_json"]["stats_ingested"] is True
    assert attempt["usability_state"] == "stats_ingested"
    assert payload["smoke_summary"]["top_kernels_json"]


def test_run_nsys_smoke_retries_qdstrm_conversion_without_output_file(monkeypatch, tmp_path):
    monkeypatch.setattr("aqs.profiler_tools._python_launch_env", lambda: {})
    fake_nsys = tmp_path / "nsys"
    fake_nsys.write_text("", encoding="utf-8")
    fake_importer = tmp_path / "QdstrmImporter"
    fake_importer.write_text("", encoding="utf-8")
    versions = {
        "nsys": "NVIDIA Nsight Systems version 2025.3.1.0",
        "QdstrmImporter": "QdstrmImporter version 2025.3.1.0",
    }
    monkeypatch.setattr("aqs.profiler_tools._tool_version", lambda command, env=None: versions.get(command))
    monkeypatch.setattr(
        "aqs.profiler_tools._resolve_tool_command",
        lambda command, env=None: [str(fake_importer if command == "QdstrmImporter" else fake_nsys)],
    )

    def _fake_run(command, cwd=None, env=None):
        tool = Path(command[0]).name
        if tool == "nsys" and "profile" in command:
            smoke_payload = tmp_path / "profiler_smoke.nsys.smoke.json"
            smoke_payload.write_text(json.dumps({"checksum": 1.0}), encoding="utf-8")
            (tmp_path / "profiler_smoke.nsys.qdstrm").write_text("trace", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="collection complete", stderr="")
        if tool == "QdstrmImporter" and "--output-file" in command:
            return subprocess.CompletedProcess(command, 0, stdout="retry needed", stderr="")
        if tool == "QdstrmImporter":
            input_path = Path(command[command.index("--input-file") + 1])
            input_path.with_suffix(".nsys-rep").write_text("rep", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="import complete", stderr="")
        if tool == "nsys" and "export" in command:
            sqlite_path = Path(command[command.index("--output") + 1])
            conn = sqlite3.connect(str(sqlite_path))
            conn.execute("CREATE TABLE sample(value INTEGER)")
            conn.commit()
            conn.close()
            return subprocess.CompletedProcess(command, 0, stdout="sqlite export complete", stderr="")
        if tool == "nsys" and "stats" in command:
            prefix = Path(command[command.index("--output") + 1])
            (prefix.parent / f"{prefix.name}_nvtxsum.csv").write_text("Range Name,Total Time (ns)\naqs@contract_first,1\n", encoding="utf-8")
            (prefix.parent / f"{prefix.name}_cudaapisum.csv").write_text("Name,Total Time (ns)\ncudaLaunchKernel,2\n", encoding="utf-8")
            (prefix.parent / f"{prefix.name}_gpukernsum.csv").write_text("Kernel Name,Total Time (ns)\nsmoke_kernel,3\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="stats export complete", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("aqs.profiler_tools._run", _fake_run)

    payload = run_nsys_smoke(outdir=tmp_path)

    assert payload["profiler_attempt"]["state_json"]["rep_converted"] is True
    assert payload["smoke_summary"]["derived_signals_json"]["nsys_rep_path"].endswith(".nsys-rep")


def test_run_ncu_smoke_records_kernel_and_summary(monkeypatch, tmp_path):
    monkeypatch.setattr("aqs.profiler_tools._python_launch_env", lambda: {})
    fake_ncu = tmp_path / "ncu"
    fake_ncu.write_text("", encoding="utf-8")
    monkeypatch.setattr("aqs.profiler_tools._tool_version", lambda command, env=None: "NVIDIA Nsight Compute Command Line Profiler 2025.3.0" if command == "ncu" else None)
    monkeypatch.setattr("aqs.profiler_tools._resolve_tool_command", lambda command, env=None: [str(fake_ncu)])

    def _fake_run(command, cwd=None, env=None):
        if Path(command[0]).name == "ncu" and "--import" not in command:
            Path(command[command.index("--export") + 1]).write_text("rep", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="==PROF== Connected to process 1234", stderr="")
        if Path(command[0]).name == "ncu" and "--import" in command:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="Kernel Name,Kernel Time (ns),DRAM Throughput %,SM Throughput %,Achieved Occupancy %\nsmoke_kernel,4,70,50,45\n",
                stderr="",
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("aqs.profiler_tools._run", _fake_run)

    payload = run_ncu_smoke(outdir=tmp_path)
    attempt = payload["profiler_attempt"]

    assert attempt["state_json"]["launcher_started"] is True
    assert attempt["state_json"]["target_seen"] is True
    assert attempt["state_json"]["kernel_seen"] is True
    assert attempt["state_json"]["report_written"] is True
    assert attempt["state_json"]["metrics_collected"] is True
    assert payload["smoke_summary"]["top_kernels_json"][0]["name"] == "smoke_kernel"


def test_run_ncu_smoke_accepts_nonempty_imported_csv_without_metric_columns(monkeypatch, tmp_path):
    monkeypatch.setattr("aqs.profiler_tools._python_launch_env", lambda: {})
    fake_ncu = tmp_path / "ncu"
    fake_ncu.write_text("", encoding="utf-8")
    monkeypatch.setattr("aqs.profiler_tools._tool_version", lambda command, env=None: "NVIDIA Nsight Compute Command Line Profiler 2025.3.0" if command == "ncu" else None)
    monkeypatch.setattr("aqs.profiler_tools._resolve_tool_command", lambda command, env=None: [str(fake_ncu)])

    def _fake_run(command, cwd=None, env=None):
        if Path(command[0]).name == "ncu" and "--import" not in command:
            Path(command[command.index("--export") + 1]).write_text("rep", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="==PROF== Connected to process 1234", stderr="")
        if Path(command[0]).name == "ncu" and "--import" in command:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="ID\ncontract_kernel\n",
                stderr="",
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("aqs.profiler_tools._run", _fake_run)

    payload = run_ncu_smoke(outdir=tmp_path)

    assert payload["profiler_attempt"]["state_json"]["metrics_collected"] is True
    assert payload["smoke_summary"]["top_kernels_json"][0]["name"] == "contract_kernel"


def test_run_ncu_smoke_permission_denial_is_persisted(monkeypatch, tmp_path):
    db_path = tmp_path / "warehouse.duckdb"
    apply_schema(db_path)
    monkeypatch.setattr("aqs.profiler_tools._python_launch_env", lambda: {})
    monkeypatch.setattr("aqs.profiler_tools._tool_version", lambda command, env=None: "NVIDIA Nsight Compute Command Line Profiler 2025.3.0" if command == "ncu" else None)
    monkeypatch.setattr("aqs.profiler_tools._resolve_tool_command", lambda command, env=None: [command])

    def _fake_run(command, cwd=None, env=None):
        if command[0] == "ncu":
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="==PROF== Connected to process 1234",
                stderr="==ERROR== ERR_NVGPUCTRPERM",
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("aqs.profiler_tools._run", _fake_run)

    with pytest.raises(ProfileToolError) as error:
        run_ncu_smoke(outdir=tmp_path, db_path=db_path)

    attempt = error.value.attempt
    assert attempt["failure_class"] == "gpu_counter_permission_denied"
    assert attempt["state_json"]["launcher_started"] is True
    assert attempt["state_json"]["target_seen"] is True
    assert attempt["state_json"]["kernel_seen"] is False
    assert attempt["state_json"]["report_written"] is False

    conn = duckdb.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT failure_class, usability_state FROM profiling.profiler_attempt WHERE attempt_id = ?",
            [attempt["attempt_id"]],
        ).fetchone()
    finally:
        conn.close()

    assert row == ("gpu_counter_permission_denied", "target_seen")
