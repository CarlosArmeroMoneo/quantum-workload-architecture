from __future__ import annotations

import csv
from io import StringIO
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
from typing import Any, NoReturn

from .db import (
    insert_accuracy_eval,
    insert_execution_run,
    insert_profile_summary,
    insert_profiler_attempt,
    link_profile_asset,
    link_run_asset,
    upsert_asset_file,
)
from .manifest import load_yaml
from .nvtx import NVTX_PHASE_VERSION
from .paths import repo_root
from .repo_metadata import capture_repo_metadata
from .utils import canonical_json, sha256_text

PROFILE_REDUCTION_VERSION = "aqs.profile.real.v1"
PROFILER_ATTEMPT_VERSION = "aqs.profiler_attempt.v1"

NSYS_ATTEMPT_STATES = (
    "collection_started",
    "qdstrm_produced",
    "rep_converted",
    "sqlite_exported",
    "stats_ingested",
)

NCU_ATTEMPT_STATES = (
    "launcher_started",
    "target_seen",
    "kernel_seen",
    "metrics_collected",
    "report_written",
)

NSYS_QDSTRM_REMEDIATION = [
    "Nsight Systems collection likely happened, but usable report conversion did not.",
    "A matching-version QdstrmImporter or host-side post-processing is required to convert .qdstrm into .nsys-rep.",
]

NCU_PERMISSION_REMEDIATION = [
    "GPU counters are blocked by host policy.",
    "Profiling requires elevated privilege or CAP_SYS_ADMIN when counters are restricted.",
    "In containers, host enablement or additional container capabilities are required.",
]

TOOL_FALLBACKS: dict[str, list[str]] = {
    # Ubuntu-packaged Nsight Systems installs QdstrmImporter here and does not place it on PATH.
    "QdstrmImporter": [
        "/usr/lib/nsight-systems/host-linux-x64/QdstrmImporter",
    ],
}

NCU_PROFILE_MODE_CONFIG = repo_root() / "configs" / "profiling" / "ncu_metric_sets.yaml"


class ProfileToolError(RuntimeError):
    def __init__(self, message: str, *, attempt: dict[str, Any] | None = None):
        super().__init__(message)
        self.attempt = attempt


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _profile_output_prefix(
    kind: str,
    manifest_path: str | Path,
    plan_rank: int,
    *,
    graph_mode: str = "off",
    variant: str | None = None,
) -> str:
    manifest_path = str(manifest_path).replace("\\", "/")
    digest = sha256_text(
        canonical_json(
            {
                "kind": kind,
                "manifest": manifest_path,
                "plan_rank": plan_rank,
                "graph_mode": graph_mode,
                "variant": variant,
            }
        )
    )[:16]
    stem = Path(manifest_path).stem
    return f"{stem}.{kind}.{digest}"


def _resolve_tool_command(command: str, *, env: dict[str, str] | None = None) -> list[str]:
    search_path = (env or {}).get("PATH")
    resolved = shutil.which(command, path=search_path)
    if resolved:
        return [resolved]

    for fallback_candidate in TOOL_FALLBACKS.get(command, []):
        fallback_path = Path(fallback_candidate)
        if fallback_path.exists() and fallback_path.is_file():
            return [str(fallback_path)]

    root = Path("/opt/nvidia")
    if root.exists():
        patterns = [
            f"nsight-compute/*/host/target-linux-x64/{command}",
            f"nsight-systems/*/bin/{command}",
            f"**/{command}",
        ]
        for pattern in patterns:
            for discovered_path in sorted(root.glob(pattern)):
                if discovered_path.exists() and discovered_path.is_file():
                    return [str(discovered_path)]
    return [command]


def _python_launch_env() -> dict[str, str]:
    env = os.environ.copy()
    src_dir = str(repo_root() / "src")
    current = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_dir if not current else os.pathsep.join([src_dir, current])

    # Auto-discover NVIDIA wheel runtime locations in the current venv so profiling and smoke
    # commands do not depend on the shell pre-sourcing helper scripts.
    venv_root = Path(sys.prefix)
    site_packages = sorted(venv_root.glob("lib/python*/site-packages"))
    cuda_runtime_root: str | None = None
    lib_dirs: list[str] = []
    candidates = [
        "nvidia/cuda_runtime",
        "nvidia/cuda_nvrtc",
        "nvidia/curand",
        "nvidia/nvjitlink",
        "nvidia/cublas",
        "nvidia/cusparse",
        "nvidia/cusolver",
        "nvidia/cufft",
    ]
    for sp in site_packages:
        for rel in candidates:
            base = sp / rel
            libdir_path = base / "lib"
            if libdir_path.exists():
                lib_dirs.append(str(libdir_path))
            if rel == "nvidia/cuda_runtime" and base.exists():
                cuda_runtime_root = str(base)
    if cuda_runtime_root and not env.get("CUDA_PATH"):
        env["CUDA_PATH"] = cuda_runtime_root
    existing_ld = [p for p in env.get("LD_LIBRARY_PATH", "").split(os.pathsep) if p]
    for lib_dir in lib_dirs:
        if lib_dir not in existing_ld:
            existing_ld.insert(0, lib_dir)
    if existing_ld:
        env["LD_LIBRARY_PATH"] = os.pathsep.join(existing_ld)

    path_entries = env.get("PATH", "").split(os.pathsep) if env.get("PATH") else []
    for tool_name in ("nsys", "QdstrmImporter", "ncu"):
        resolved = _resolve_tool_command(tool_name, env=env)[0]
        resolved_path = Path(resolved)
        parent = str(resolved_path.parent)
        if resolved_path.exists() and parent not in path_entries:
            path_entries.insert(0, parent)
    if path_entries:
        env["PATH"] = os.pathsep.join(path_entries)
    return env


def _run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=str(cwd) if cwd else None, env=env, text=True, capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise ProfileToolError(f"profiler_cli_missing: {command[0]} is not available") from exc


def _tool_probe(command: str, *, env: dict[str, str] | None = None) -> dict[str, Any]:
    resolved = _resolve_tool_command(command, env=env)
    path = Path(resolved[0])
    probe = {
        "path": str(path),
        "present": bool(path.exists()),
        "version": None,
        "version_error": None,
    }
    if not probe["present"]:
        return probe
    try:
        completed = _run([*resolved, "--version"], env=env)
    except ProfileToolError as exc:
        probe["version_error"] = str(exc)
        return probe
    text = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode == 0 and text:
        probe["version"] = text.splitlines()[0].strip()
    elif text:
        probe["version_error"] = _stderr_excerpt(text)
    return probe


def _tool_version(command: str, *, env: dict[str, str] | None = None) -> str | None:
    return _tool_probe(command, env=env)["version"]


def _version_token(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)+)", text)
    return match.group(1) if match else text.strip()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe_value(payload), indent=2, sort_keys=True), encoding="utf-8")


def _json_safe_value(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj).replace("\\", "/")
    if isinstance(obj, dict):
        return {str(k): _json_safe_value(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe_value(v) for v in obj]
    if isinstance(obj, tuple):
        return [_json_safe_value(v) for v in obj]
    if isinstance(obj, set):
        return sorted(_json_safe_value(v) for v in obj)
    return obj


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _str_list_or_empty(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _sha_or_none(text: str) -> str | None:
    return sha256_text(text) if text else None


def _stderr_excerpt(text: str, limit: int = 1200) -> str | None:
    text = text.strip()
    return text[:limit] if text else None


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _load_csv_text_rows(text: str | None) -> list[dict[str, str]]:
    payload = (text or "").strip()
    if not payload:
        return []
    handle = StringIO(payload)
    reader = csv.DictReader(handle)
    return [dict(row) for row in reader]


def _load_ncu_profile_mode(profile_mode: str) -> dict[str, Any]:
    config = load_yaml(NCU_PROFILE_MODE_CONFIG)
    modes = config.get("profile_modes")
    if not isinstance(modes, dict):
        raise ProfileToolError(f"invalid NCU profile mode config at {NCU_PROFILE_MODE_CONFIG}")
    selected = modes.get(profile_mode)
    if not isinstance(selected, dict):
        raise ProfileToolError(f"unsupported NCU profile mode {profile_mode!r}")
    return {
        "profile_mode": profile_mode,
        "set": str(selected.get("set") or "basic"),
        "target_processes": str(selected.get("target_processes") or "all"),
        "replay_mode": str(selected.get("replay_mode") or "kernel"),
        "import_page": str(selected.get("import_page") or "raw"),
        "notes": str(selected.get("notes") or ""),
        "config_path": str(NCU_PROFILE_MODE_CONFIG).replace("\\", "/"),
    }


def _try_locate_artifact(preferred_path: Path) -> Path | None:
    if preferred_path.exists():
        return preferred_path
    parent = preferred_path.parent
    stem = preferred_path.stem
    suffix = preferred_path.suffix
    candidates = sorted(parent.glob(f"{stem}*{suffix}"))
    return candidates[0] if candidates else None


def _locate_artifact(preferred_path: Path) -> Path:
    located = _try_locate_artifact(preferred_path)
    if located is not None:
        return located
    raise ProfileToolError(f"expected profiler artifact was not created: {preferred_path}")


def _csv_float(row: dict[str, str], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except Exception:
            continue
    return None


def _csv_time_s(row: dict[str, str]) -> float | None:
    mappings = (
        ("Total Time (ns)", 1.0e-9),
        ("Kernel Time (ns)", 1.0e-9),
        ("gpu__time_duration.sum", 1.0e-9),
        ("gpu__time_duration.avg", 1.0e-9),
        ("gpu__time_duration.max", 1.0e-9),
        ("Total Time (us)", 1.0e-6),
        ("Kernel Time (us)", 1.0e-6),
        ("Total Time (ms)", 1.0e-3),
        ("Kernel Time (ms)", 1.0e-3),
        ("Time", 1.0),
        ("Kernel Time", 1.0),
        ("Duration", 1.0),
    )
    for key, multiplier in mappings:
        value = _csv_float(row, key)
        if value is not None:
            return value * multiplier
    return None


def _csv_name(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value:
            return value
    return None


def _read_sqlite_tables(path: Path) -> list[str]:
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    try:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
        return [str(row[0]) for row in cursor.fetchall()]
    finally:
        conn.close()


def reduce_nsys_artifacts(execution_payload: dict[str, Any], sqlite_path: Path, stats_csv: dict[str, Path], nsys_rep: Path) -> dict[str, Any]:
    nvtx_rows = _load_csv_rows(stats_csv.get("nvtxsum", Path()))
    kernel_rows = _load_csv_rows(stats_csv.get("gpukernsum", Path()))
    api_rows = _load_csv_rows(stats_csv.get("cudaapisum", Path()))
    nvtx_phase_times: dict[str, float] = {}
    for row in nvtx_rows:
        phase_name = _csv_name(row, "Range Name", "Name", "NVTX Range")
        total_time = _csv_time_s(row)
        if not phase_name or total_time is None:
            continue
        if phase_name.startswith("aqs@"):
            phase_name = phase_name.split("@", 1)[1]
        nvtx_phase_times[phase_name] = total_time
    if not nvtx_phase_times:
        nvtx_phase_times = dict((execution_payload.get("execution_run") or {}).get("failure_detail_json", {}).get("phase_times") or {})

    top_kernels = []
    for row in kernel_rows[:5]:
        name = _csv_name(row, "Kernel Name", "Name")
        time_s = _csv_time_s(row)
        if name is None or time_s is None:
            continue
        top_kernels.append({"name": name, "time_s": time_s, "kind": "gpu_kernel"})

    cuda_api_total = sum(_csv_time_s(row) or 0.0 for row in api_rows)
    run = execution_payload["execution_run"]
    execution_detail = _dict_or_empty(run.get("failure_detail_json"))
    repo_metadata = execution_payload.get("repo_metadata") or capture_repo_metadata()
    profile_id = "prof_" + sha256_text(canonical_json({"run_id": run["run_id"], "kind": "nsys", "version": PROFILE_REDUCTION_VERSION}))[:16]
    return {
        "profile_id": profile_id,
        "run_id": run["run_id"],
        "profiler_kind": "nsys",
        "nvtx_phase_times_json": nvtx_phase_times,
        "top_kernels_json": top_kernels,
        "dram_util_pct": None,
        "sm_util_pct": None,
        "occupancy_pct": None,
        "comm_time_pct": 0.0,
        "nsys_asset_id": None,
        "ncu_asset_id": None,
        "profile_version": PROFILE_REDUCTION_VERSION,
        "repo_metadata": repo_metadata,
        "derived_signals_json": {
            "profile_source": "real_nsys_profile",
            "nvtx_phase_version": NVTX_PHASE_VERSION,
            "nsys_rep_path": str(nsys_rep).replace("\\", "/"),
            "nsys_sqlite_tables": _read_sqlite_tables(sqlite_path),
            "cuda_api_total_time": cuda_api_total,
            "stats_csv": {name: str(path).replace("\\", "/") for name, path in stats_csv.items()},
            "graph_mode": run.get("graph_mode") or execution_detail.get("graph_mode") or "off",
            "repo_metadata": repo_metadata,
        },
    }


def reduce_ncu_artifacts(
    execution_payload: dict[str, Any],
    ncu_rep: Path,
    ncu_csv_path: Path | None = None,
    *,
    imported_csv_text: str | None = None,
    profile_mode: str = "basic",
    metric_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = _load_csv_text_rows(imported_csv_text)
    parse_source = "ncu_report_import" if rows else "csv_fallback"
    if not rows and ncu_csv_path is not None:
        rows = _load_csv_rows(ncu_csv_path)
    if not rows and imported_csv_text:
        parse_source = "report_import_empty"
    top_kernels = []
    dram_util = None
    sm_util = None
    occupancy = None
    kernel_times: list[float] = []
    for idx, row in enumerate(rows):
        name = _csv_name(row, "Kernel Name", "Name", "ID")
        time_s = _csv_time_s(row)
        if time_s is not None:
            kernel_times.append(time_s)
        if name is not None and idx < 5:
            entry: dict[str, Any] = {"name": name, "kind": "gpu_kernel"}
            if time_s is not None:
                entry["time_s"] = time_s
            top_kernels.append(entry)
        dram_util = dram_util if dram_util is not None else _csv_float(row, "DRAM Throughput %", "dram__throughput.avg.pct_of_peak_sustained_elapsed")
        sm_util = sm_util if sm_util is not None else _csv_float(row, "SM Throughput %", "sm__throughput.avg.pct_of_peak_sustained_elapsed")
        occupancy = occupancy if occupancy is not None else _csv_float(row, "Achieved Occupancy %", "sm__warps_active.avg.pct_of_peak_sustained_active")

    total_kernel_time_s = round(sum(kernel_times), 9) if kernel_times else None
    for entry in top_kernels:
        if total_kernel_time_s and entry.get("time_s") is not None:
            entry["time_pct"] = round((float(entry["time_s"]) / total_kernel_time_s) * 100.0, 6)

    run = execution_payload["execution_run"]
    execution_detail = _dict_or_empty(run.get("failure_detail_json"))
    nvtx_phase_times = _dict_or_empty(execution_detail.get("phase_times"))
    wall_s = float(run.get("wall_s") or 0.0)
    ttfr_s = float(run.get("ttfr_s") or 0.0)
    steady_iter_ms = float(run.get("steady_iter_ms") or 0.0)
    repeat_count = int(execution_payload.get("repeat_count_hint") or 1)
    launch_proxy_pct = round(max(0.0, ((wall_s - float(total_kernel_time_s or 0.0)) / wall_s) * 100.0), 6) if wall_s > 0.0 else None
    planner_proxy_pct = round(max(0.0, ((ttfr_s - float(total_kernel_time_s or 0.0)) / ttfr_s) * 100.0), 6) if ttfr_s > 0.0 else None
    avg_kernel_time_ms = round((sum(kernel_times) / len(kernel_times)) * 1000.0, 6) if kernel_times else None
    cold_to_steady_ratio = round((ttfr_s * 1000.0) / steady_iter_ms, 6) if ttfr_s > 0.0 and steady_iter_ms > 0.0 else None
    memory_bound_signal = "low"
    if dram_util is not None and sm_util is not None:
        if float(dram_util) >= 70.0 and float(sm_util) <= float(dram_util) - 10.0:
            memory_bound_signal = "high"
        elif float(dram_util) >= 55.0:
            memory_bound_signal = "medium"
    launch_bound_signal = "high" if launch_proxy_pct is not None and avg_kernel_time_ms is not None and launch_proxy_pct >= 30.0 and avg_kernel_time_ms <= 0.75 else "low"
    reuse_signal = "likely" if cold_to_steady_ratio is not None and repeat_count >= 8 and cold_to_steady_ratio >= 1.2 else "unlikely"

    repo_metadata = execution_payload.get("repo_metadata") or capture_repo_metadata()
    profile_id = "prof_" + sha256_text(canonical_json({"run_id": run["run_id"], "kind": "ncu", "version": PROFILE_REDUCTION_VERSION}))[:16]
    header_fields = list(rows[0].keys()) if rows else []
    mode_config = metric_config or _load_ncu_profile_mode(profile_mode)
    return {
        "profile_id": profile_id,
        "run_id": run["run_id"],
        "profiler_kind": "ncu",
        "nvtx_phase_times_json": nvtx_phase_times,
        "top_kernels_json": top_kernels,
        "dram_util_pct": dram_util,
        "sm_util_pct": sm_util,
        "occupancy_pct": occupancy,
        "comm_time_pct": 0.0,
        "nsys_asset_id": None,
        "ncu_asset_id": None,
        "profile_version": PROFILE_REDUCTION_VERSION,
        "repo_metadata": repo_metadata,
        "derived_signals_json": {
            "profile_source": "real_ncu_profile",
            "nvtx_phase_version": NVTX_PHASE_VERSION,
            "ncu_rep_path": str(ncu_rep).replace("\\", "/"),
            "ncu_csv_path": str(ncu_csv_path).replace("\\", "/") if ncu_csv_path is not None else None,
            "ncu_parse_source": parse_source,
            "profile_mode": profile_mode,
            "ncu_metric_set": mode_config.get("set"),
            "ncu_replay_mode": mode_config.get("replay_mode"),
            "graph_mode": run.get("graph_mode") or execution_detail.get("graph_mode") or "off",
            "csv_row_count": len(rows),
            "csv_header_fields": header_fields[:64],
            "csv_nonempty": bool(rows),
            "kernel_count": len(kernel_times),
            "kernel_time_total_s": total_kernel_time_s,
            "avg_kernel_time_ms": avg_kernel_time_ms,
            "planner_proxy_pct": planner_proxy_pct,
            "launch_proxy_pct": launch_proxy_pct,
            "cold_to_steady_ratio": cold_to_steady_ratio,
            "memory_bound_signal": memory_bound_signal,
            "launch_bound_signal": launch_bound_signal,
            "reuse_signal": reuse_signal,
            "repo_metadata": repo_metadata,
        },
    }


def _artifact_presence(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    return {
        name: {"path": str(path).replace("\\", "/"), "exists": bool(path.exists())}
        for name, path in paths.items()
    }


def _attempt_id(tool_kind: str, attempt_role: str, command: list[str], stem: str) -> str:
    payload = {"tool_kind": tool_kind, "attempt_role": attempt_role, "command": command, "stem": stem, "version": PROFILER_ATTEMPT_VERSION}
    return "attempt_" + sha256_text(canonical_json(payload))[:16]


def _new_attempt(*, tool_kind: str, attempt_role: str, command: list[str], stem: str, tool_version: str | None, importer_version: str | None = None) -> dict[str, Any]:
    states = NSYS_ATTEMPT_STATES if tool_kind == "nsys" else NCU_ATTEMPT_STATES
    repo_metadata = capture_repo_metadata()
    return {
        "attempt_id": _attempt_id(tool_kind, attempt_role, command, stem),
        "attempt_version": PROFILER_ATTEMPT_VERSION,
        "tool_kind": tool_kind,
        "attempt_role": attempt_role,
        "command": list(command),
        "tool_version": tool_version,
        "importer_version": importer_version,
        "exit_code": None,
        "stdout_digest": None,
        "stderr_digest": None,
        "stderr_excerpt": None,
        "failure_class": None,
        "usability_state": "not_started",
        "state_json": {state: False for state in states},
        "artifact_presence_json": {},
        "remediation": [],
        "repo_metadata": repo_metadata,
        "notes": None,
        "run_id": None,
        "attempt_asset_id": None,
    }


def _record_completed_process(
    attempt: dict[str, Any],
    completed: subprocess.CompletedProcess[str],
    *,
    append: bool = False,
    label: str | None = None,
) -> str:
    combined = "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()
    if not append or attempt.get("exit_code") is None:
        attempt["exit_code"] = completed.returncode
        attempt["stdout_digest"] = _sha_or_none((completed.stdout or "").strip())
        attempt["stderr_digest"] = _sha_or_none((completed.stderr or "").strip())
        attempt["stderr_excerpt"] = _stderr_excerpt(combined)
        return combined
    note = {
        "step": label or "secondary",
        "exit_code": completed.returncode,
        "stdout_digest": _sha_or_none((completed.stdout or "").strip()),
        "stderr_digest": _sha_or_none((completed.stderr or "").strip()),
        "stderr_excerpt": _stderr_excerpt(combined),
    }
    existing = attempt.get("notes")
    payload = [existing] if existing else []
    payload.append(json.dumps(note, sort_keys=True))
    attempt["notes"] = "\n".join(payload)
    return combined


def _highest_state(tool_kind: str, state_json: dict[str, bool]) -> str:
    ordered = NSYS_ATTEMPT_STATES if tool_kind == "nsys" else NCU_ATTEMPT_STATES
    reached = [state for state in ordered if state_json.get(state)]
    return reached[-1] if reached else "not_started"


def classify_nsys_failure(report_path: Path, qdstrm_path: Path, output_text: str) -> tuple[str, list[str], str]:
    if qdstrm_path.exists() and not report_path.exists():
        message = f"nsys did not produce {report_path.name}; only {qdstrm_path.name} was created and importer/export could not proceed"
        return "report_conversion_blocked", list(NSYS_QDSTRM_REMEDIATION), message
    if "profiler_cli_missing" in output_text:
        return "tool_missing", ["Nsight Systems is not available on PATH or in the known bundled tool locations."], output_text
    if "Traceback" in output_text or "ModuleNotFoundError" in output_text or "ImportError" in output_text:
        return "target_launch_failed", ["The profiled target failed before Nsight Systems could produce a usable report. Verify runtime dependencies for the smoke or execution target."], "the profiled target failed before Nsight Systems produced a usable report"
    return "collection_failed", ["Nsight Systems did not produce a usable report artifact."], output_text or "nsys profile failed"


def classify_ncu_failure(output_text: str, *, report_written: bool = False) -> tuple[str, list[str], str]:
    if "ERR_NVGPUCTRPERM" in output_text:
        return "gpu_counter_permission_denied", list(NCU_PERMISSION_REMEDIATION), "ncu could not access GPU performance counters (ERR_NVGPUCTRPERM)"
    if "No kernels were profiled" in output_text:
        return "no_kernel_captured", ["No kernels were captured for the requested NVTX-filtered range."], "ncu did not capture any kernels for the requested NVTX-filtered range"
    if "Traceback" in output_text or "ModuleNotFoundError" in output_text or "ImportError" in output_text:
        return "target_launch_failed", ["The profiled target failed before Nsight Compute could produce a usable report. Verify runtime dependencies for the smoke or execution target."], "the profiled target failed before Nsight Compute produced a usable report"
    if report_written:
        return "report_import_failed", ["Nsight Compute wrote a report but CSV import or reduction failed."], output_text or "ncu import failed"
    if "profiler_cli_missing" in output_text:
        return "tool_missing", ["Nsight Compute is not available on PATH."], output_text
    return "report_not_written", ["Nsight Compute did not write a usable .ncu-rep artifact."], output_text or "ncu profile failed"


def _write_attempt(outdir: Path, stem: str, attempt: dict[str, Any]) -> Path:
    attempt_path = outdir / f"{stem}.attempt.json"
    _write_json(attempt_path, attempt)
    return attempt_path


def _store_attempt(db_path: str | Path | None, attempt_path: Path, attempt: dict[str, Any], *, run_payload: dict[str, Any] | None = None) -> None:
    if not db_path:
        return
    if run_payload:
        insert_execution_run(db_path, run_payload["execution_run"])
        accuracy = run_payload.get("accuracy_eval") or {}
        for row in accuracy.get("rows", []):
            insert_accuracy_eval(db_path, row)
        execution_artifact = (((attempt.get("artifact_presence_json") or {}).get("execution_payload")) or {}).get("path")
        if execution_artifact and Path(execution_artifact).exists():
            indexed_execution = upsert_asset_file(
                db_path,
                execution_artifact,
                asset_type="json",
                notes="raw execution payload captured during profiler attempt",
            )
            link_run_asset(db_path, run_payload["execution_run"]["run_id"], "raw_execution_json", indexed_execution["asset_id"])
    indexed = upsert_asset_file(db_path, attempt_path, asset_type="json", notes=f"{attempt['tool_kind']} {attempt['attempt_role']} profiler attempt")
    attempt["attempt_asset_id"] = indexed["asset_id"]
    if run_payload:
        link_run_asset(db_path, run_payload["execution_run"]["run_id"], "profiler_attempt_json", indexed["asset_id"])
    insert_profiler_attempt(db_path, attempt)


def _raise_with_attempt(
    message: str,
    attempt: dict[str, Any],
    outdir: Path,
    stem: str,
    *,
    db_path: str | Path | None = None,
    run_payload: dict[str, Any] | None = None,
) -> NoReturn:
    attempt_path = _write_attempt(outdir, stem, attempt)
    _store_attempt(db_path, attempt_path, attempt, run_payload=run_payload)
    raise ProfileToolError(message, attempt=attempt)


def _store_profile_assets(db_path: str | Path | None, run_payload: dict[str, Any], profile_summary: dict[str, Any], assets: list[dict[str, Any]]) -> None:
    if not db_path:
        return
    insert_execution_run(db_path, run_payload["execution_run"])
    accuracy = run_payload.get("accuracy_eval") or {}
    for row in accuracy.get("rows", []):
        insert_accuracy_eval(db_path, row)
    insert_profile_summary(db_path, profile_summary)
    for asset in assets:
        indexed = upsert_asset_file(db_path, asset["path"], asset_type=asset["asset_type"], tracked_in_git=asset.get("tracked_in_git", False), notes=asset.get("notes"))
        if asset.get("run_role"):
            link_run_asset(db_path, run_payload["execution_run"]["run_id"], asset["run_role"], indexed["asset_id"])
        if asset.get("profile_role"):
            link_profile_asset(db_path, profile_summary["profile_id"], asset["profile_role"], indexed["asset_id"])
        if asset.get("profile_role") == "nsys_report":
            profile_summary["nsys_asset_id"] = indexed["asset_id"]
        if asset.get("profile_role") == "ncu_report":
            profile_summary["ncu_asset_id"] = indexed["asset_id"]
    insert_profile_summary(db_path, profile_summary)


def _smoke_runner_command(out_json: Path) -> list[str]:
    return [sys.executable, "-m", "aqs.profiler_smoke_runner", "--out", str(out_json)]


def _execution_entrypoint_command(
    *,
    manifest_path: str | Path,
    system_manifest_path: str | Path,
    plan_rank: int,
    objective: str,
    probe_strategy: str,
    planner_budget: str,
    allow_distributed: bool,
    measurement_repeats: int,
    execution_intent: str,
    graph_mode: str | None,
    out_path: Path,
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "aqs",
        "tnep",
        "execute",
        "--manifest",
        str(manifest_path),
        "--system-manifest",
        str(system_manifest_path),
        "--plan-rank",
        str(plan_rank),
        "--objective",
        objective,
        "--probe-strategy",
        probe_strategy,
        "--planner-budget",
        planner_budget,
        "--measurement-repeats",
        str(measurement_repeats),
        "--execution-intent",
        execution_intent,
        "--out",
        str(out_path),
        "--allow-distributed" if allow_distributed else "--no-allow-distributed",
    ]
    if graph_mode is not None:
        command.extend(["--graph-mode", str(graph_mode)])
    return command


def _maybe_load_execution_payload(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return _load_json(path)
    except Exception:
        return None


def _maybe_convert_qdstrm(
    *,
    qdstrm_path: Path,
    report_path: Path,
    profiler_env: dict[str, str],
    attempt: dict[str, Any],
) -> None:
    if report_path.exists() or not qdstrm_path.exists():
        return
    importer = _resolve_tool_command("QdstrmImporter", env=profiler_env)
    importer_path = Path(importer[0])
    if not importer_path.exists():
        return

    # First try the explicit output-file form.
    completed = _run(
        [*importer, "--input-file", str(qdstrm_path), "--output-file", str(report_path)],
        cwd=repo_root(),
        env=profiler_env,
    )
    _record_completed_process(attempt, completed, append=True, label="qdstrm_import")
    if report_path.exists():
        return

    # Ubuntu-packaged importers may ignore --output-file but still convert successfully.
    completed_retry = _run(
        [*importer, "--input-file", str(qdstrm_path)],
        cwd=repo_root(),
        env=profiler_env,
    )
    _record_completed_process(attempt, completed_retry, append=True, label="qdstrm_import_retry")


def _locate_stats_csv(output_prefix: Path, report_name: str) -> Path | None:
    expected = output_prefix.parent / f"{output_prefix.name}_{report_name}.csv"
    if expected.exists():
        return expected
    candidates = sorted(output_prefix.parent.glob(f"{output_prefix.name}*{report_name}*.csv"))
    return candidates[0] if candidates else None


def _nsys_summary_non_empty(summary: dict[str, Any]) -> bool:
    derived = summary.get("derived_signals_json") or {}
    return bool(summary.get("nvtx_phase_times_json") or summary.get("top_kernels_json") or derived.get("nsys_sqlite_tables"))


def _ncu_summary_non_empty(summary: dict[str, Any]) -> bool:
    derived = summary.get("derived_signals_json") or {}
    return bool(
        summary.get("top_kernels_json")
        or summary.get("dram_util_pct") is not None
        or summary.get("sm_util_pct") is not None
        or summary.get("occupancy_pct") is not None
        or derived.get("csv_nonempty")
        or derived.get("csv_row_count")
    )


def _smoke_execution_payload(kind: str) -> dict[str, Any]:
    return {
        "execution_run": {
            "run_id": f"smoke_{kind}",
            "failure_detail_json": {},
        }
    }


def _summarize_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
    if not attempt:
        return {}
    return {
        "attempt_id": attempt["attempt_id"],
        "tool_kind": attempt["tool_kind"],
        "attempt_role": attempt["attempt_role"],
        "tool_version": attempt.get("tool_version"),
        "importer_version": attempt.get("importer_version"),
        "exit_code": attempt.get("exit_code"),
        "failure_class": attempt.get("failure_class"),
        "usability_state": attempt.get("usability_state"),
        "state_json": attempt.get("state_json") or {},
        "artifact_presence_json": attempt.get("artifact_presence_json") or {},
        "remediation": attempt.get("remediation") or [],
    }

def run_nsys_smoke(*, outdir: str | Path | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    outdir = _ensure_dir(Path(outdir) if outdir else repo_root() / "artifacts" / "profiler_smoke" / "nsys")
    profiler_env = _python_launch_env()
    tool_version = _tool_version("nsys", env=profiler_env)
    importer_version = _tool_version("QdstrmImporter", env=profiler_env)
    stem = "profiler_smoke.nsys"
    smoke_payload_path = outdir / f"{stem}.smoke.json"
    report_prefix = outdir / stem
    report_path = outdir / f"{stem}.nsys-rep"
    qdstrm_path = outdir / f"{stem}.qdstrm"
    sqlite_path = outdir / f"{stem}.sqlite"
    stats_prefix = outdir / f"{stem}.stats"
    summary_json_path = outdir / f"{stem}.summary.json"
    stats_expected = {
        "nvtxsum": outdir / f"{stats_prefix.name}_nvtxsum.csv",
        "cudaapisum": outdir / f"{stats_prefix.name}_cudaapisum.csv",
        "gpukernsum": outdir / f"{stats_prefix.name}_gpukernsum.csv",
    }
    command = [*_resolve_tool_command("nsys", env=profiler_env), "profile", "--trace=cuda,nvtx,osrt", "--sample=none", "--force-overwrite=true", f"--output={report_prefix}", *_smoke_runner_command(smoke_payload_path)]
    attempt = _new_attempt(tool_kind="nsys", attempt_role="smoke", command=command, stem=stem, tool_version=tool_version, importer_version=importer_version)
    attempt["state_json"]["collection_started"] = True
    try:
        completed = _run(command, cwd=repo_root(), env=profiler_env)
    except ProfileToolError as exc:
        attempt["failure_class"] = "tool_missing"
        attempt["remediation"] = ["Nsight Systems is not available on PATH or in the known bundled tool locations."]
        attempt["notes"] = str(exc)
        _raise_with_attempt(str(exc), attempt, outdir, stem, db_path=db_path)
    output_text = _record_completed_process(attempt, completed)
    attempt["artifact_presence_json"] = _artifact_presence({"smoke_payload": smoke_payload_path, "qdstrm": qdstrm_path, "report": report_path, "sqlite": sqlite_path, "summary": summary_json_path, **{f"stats_{name}": path for name, path in stats_expected.items()}})
    attempt["state_json"]["qdstrm_produced"] = qdstrm_path.exists()
    _maybe_convert_qdstrm(qdstrm_path=qdstrm_path, report_path=report_path, profiler_env=profiler_env, attempt=attempt)
    located_rep = _try_locate_artifact(report_path)
    if located_rep is not None:
        report_path = located_rep
        attempt["state_json"]["rep_converted"] = True
    if not attempt["state_json"]["rep_converted"]:
        attempt["artifact_presence_json"] = _artifact_presence({"smoke_payload": smoke_payload_path, "qdstrm": qdstrm_path, "report": report_path, "sqlite": sqlite_path, "summary": summary_json_path, **{f"stats_{name}": path for name, path in stats_expected.items()}})
        attempt["usability_state"] = _highest_state("nsys", attempt["state_json"])
        failure_class, remediation, message = classify_nsys_failure(report_path, qdstrm_path, output_text)
        attempt["failure_class"] = failure_class
        attempt["remediation"] = remediation
        _raise_with_attempt(message, attempt, outdir, stem, db_path=db_path)

    export_completed = _run(
        [*_resolve_tool_command("nsys", env=profiler_env), "export", "--force-overwrite=true", "--type", "sqlite", "--output", str(sqlite_path), str(report_path)],
        cwd=repo_root(),
        env=profiler_env,
    )
    _record_completed_process(attempt, export_completed, append=True, label="nsys_export_sqlite")
    located_sqlite = _try_locate_artifact(sqlite_path)
    if located_sqlite is not None:
        sqlite_path = located_sqlite
        attempt["state_json"]["sqlite_exported"] = True

    stats_completed = _run(
        [
            *_resolve_tool_command("nsys", env=profiler_env),
            "stats",
            "--report",
            "nvtxsum",
            "--report",
            "cudaapisum",
            "--report",
            "gpukernsum",
            "--format",
            "csv",
            "--output",
            str(stats_prefix),
            str(report_path),
        ],
        cwd=repo_root(),
        env=profiler_env,
    )
    _record_completed_process(attempt, stats_completed, append=True, label="nsys_stats")
    stats_paths: dict[str, Path] = {}
    for report_name in ("nvtxsum", "cudaapisum", "gpukernsum"):
        located = _locate_stats_csv(stats_prefix, report_name)
        if located is not None:
            stats_paths[report_name] = located

    smoke_summary = None
    if attempt["state_json"]["sqlite_exported"] and len(stats_paths) == 3:
        smoke_summary = reduce_nsys_artifacts(_smoke_execution_payload("nsys"), sqlite_path, stats_paths, report_path)
        if _nsys_summary_non_empty(smoke_summary):
            _write_json(summary_json_path, smoke_summary)
            attempt["state_json"]["stats_ingested"] = True
    attempt["artifact_presence_json"] = _artifact_presence({"smoke_payload": smoke_payload_path, "qdstrm": qdstrm_path, "report": report_path, "sqlite": sqlite_path, "summary": summary_json_path, **{f"stats_{name}": stats_paths.get(name, path) for name, path in stats_expected.items()}})
    attempt["usability_state"] = _highest_state("nsys", attempt["state_json"])
    if not attempt["state_json"]["sqlite_exported"] or not attempt["state_json"]["stats_ingested"]:
        attempt["failure_class"] = "ingestion_incomplete"
        attempt["remediation"] = ["Nsight Systems produced a report, but SQLite export, stats export, or parsed summary generation did not complete."]
        _raise_with_attempt("nsys smoke report was collected but usable summary generation did not complete", attempt, outdir, stem, db_path=db_path)
    attempt_path = _write_attempt(outdir, stem, attempt)
    _store_attempt(db_path, attempt_path, attempt)
    return {
        "status": "success",
        "profiler_attempt": attempt,
        "smoke_payload": _load_json(smoke_payload_path) if smoke_payload_path.exists() else None,
        "smoke_summary": smoke_summary,
    }


def run_ncu_smoke(*, outdir: str | Path | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    outdir = _ensure_dir(Path(outdir) if outdir else repo_root() / "artifacts" / "profiler_smoke" / "ncu")
    profiler_env = _python_launch_env()
    tool_version = _tool_version("ncu", env=profiler_env)
    mode_config = _load_ncu_profile_mode("basic")
    stem = "profiler_smoke.ncu"
    smoke_payload_path = outdir / f"{stem}.smoke.json"
    report_path = outdir / f"{stem}.ncu-rep"
    csv_path = outdir / f"{stem}.ncu.csv"
    summary_json_path = outdir / f"{stem}.summary.json"

    # Keep smoke unfiltered. Older ncu builds are noticeably more brittle with NVTX filtering,
    # and smoke should prove host capability rather than exact range syntax.
    command = [
        *_resolve_tool_command("ncu", env=profiler_env),
        "--set", mode_config["set"],
        "--target-processes", mode_config["target_processes"],
        "--replay-mode", mode_config["replay_mode"],
        "--export", str(report_path),
        *_smoke_runner_command(smoke_payload_path),
    ]
    attempt = _new_attempt(tool_kind="ncu", attempt_role="smoke", command=command, stem=stem, tool_version=tool_version)
    attempt["state_json"]["launcher_started"] = True
    try:
        completed = _run(command, cwd=repo_root(), env=profiler_env)
    except ProfileToolError as exc:
        attempt["failure_class"] = "tool_missing"
        attempt["remediation"] = ["Nsight Compute is not available on PATH."]
        attempt["notes"] = str(exc)
        _raise_with_attempt(str(exc), attempt, outdir, stem, db_path=db_path)
    output_text = _record_completed_process(attempt, completed)
    located_rep = _try_locate_artifact(report_path)
    if located_rep is not None:
        report_path = located_rep
        attempt["state_json"]["report_written"] = True
    attempt["state_json"]["target_seen"] = "Connected to process" in output_text or "==PROF==" in output_text
    attempt["state_json"]["kernel_seen"] = attempt["state_json"]["report_written"] and "No kernels were profiled" not in output_text and "ERR_NVGPUCTRPERM" not in output_text
    attempt["artifact_presence_json"] = _artifact_presence({"smoke_payload": smoke_payload_path, "report": report_path, "csv": csv_path, "summary": summary_json_path})
    smoke_summary = None
    if attempt["state_json"]["report_written"]:
        import_completed = _run(
            [*_resolve_tool_command("ncu", env=profiler_env), "--import", str(report_path), "--csv", "--page", mode_config["import_page"]],
            cwd=repo_root(),
            env=profiler_env,
        )
        import_text = _record_completed_process(attempt, import_completed, append=True, label="ncu_import")
        if import_completed.returncode == 0 and import_text.strip():
            csv_path.write_text(import_text, encoding="utf-8")
            attempt["state_json"]["metrics_collected"] = True
            smoke_summary = reduce_ncu_artifacts(
                _smoke_execution_payload("ncu"),
                report_path,
                csv_path,
                imported_csv_text=import_text,
                profile_mode="basic",
                metric_config=mode_config,
            )
            _write_json(summary_json_path, smoke_summary)
    attempt["artifact_presence_json"] = _artifact_presence({"smoke_payload": smoke_payload_path, "report": report_path, "csv": csv_path, "summary": summary_json_path})
    attempt["usability_state"] = _highest_state("ncu", attempt["state_json"])
    if not attempt["state_json"]["report_written"] or not attempt["state_json"]["kernel_seen"] or not attempt["state_json"]["metrics_collected"]:
        failure_class, remediation, message = classify_ncu_failure(output_text, report_written=attempt["state_json"]["report_written"])
        attempt["failure_class"] = failure_class
        attempt["remediation"] = remediation
        _raise_with_attempt(message, attempt, outdir, stem, db_path=db_path)
    attempt_path = _write_attempt(outdir, stem, attempt)
    _store_attempt(db_path, attempt_path, attempt)
    return {
        "status": "success",
        "profiler_attempt": attempt,
        "smoke_payload": _load_json(smoke_payload_path) if smoke_payload_path.exists() else None,
        "smoke_summary": smoke_summary,
    }


def collect_profiling_readiness(*, system_profile: dict[str, Any], outdir: str | Path | None = None, run_smoke: bool = True, db_path: str | Path | None = None) -> dict[str, Any]:
    outdir = _ensure_dir(Path(outdir) if outdir else repo_root() / "artifacts" / "profiling_readiness")
    profiler_env = _python_launch_env()
    permissions = {"is_root": bool(hasattr(os, "geteuid") and os.geteuid() == 0), "cap_sys_admin_effective": None}
    cap_status = Path("/proc/self/status")
    if cap_status.exists():
        text = cap_status.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if line.startswith("CapEff:"):
                try:
                    cap_eff = int(line.split(":", 1)[1].strip(), 16)
                    permissions["cap_sys_admin_effective"] = bool(cap_eff & (1 << 21))
                except Exception:
                    permissions["cap_sys_admin_effective"] = None
                break
    nsys_probe = _tool_probe("nsys", env=profiler_env)
    importer_probe = _tool_probe("QdstrmImporter", env=profiler_env)
    ncu_probe = _tool_probe("ncu", env=profiler_env)
    nsys_version = nsys_probe["version"]
    importer_version = importer_probe["version"]
    ncu_version = ncu_probe["version"]
    nsys_smoke: dict[str, Any] | None = None
    ncu_smoke: dict[str, Any] | None = None
    if run_smoke and system_profile.get("gpu_present"):
        if nsys_probe["present"]:
            try:
                nsys_smoke = run_nsys_smoke(outdir=outdir / "nsys", db_path=db_path)
            except ProfileToolError as exc:
                nsys_smoke = {"status": "blocked", "profiler_attempt": exc.attempt}
        if ncu_probe["present"]:
            try:
                ncu_smoke = run_ncu_smoke(outdir=outdir / "ncu", db_path=db_path)
            except ProfileToolError as exc:
                ncu_smoke = {"status": "blocked", "profiler_attempt": exc.attempt}

    nsys_version_token = _version_token(nsys_version)
    importer_version_token = _version_token(importer_version)
    versions_match = bool(nsys_version_token and importer_version_token and nsys_version_token == importer_version_token)
    nsys_smoke_attempt: dict[str, Any] = _dict_or_empty((nsys_smoke or {}).get("profiler_attempt")) if nsys_smoke else {}
    ncu_smoke_attempt: dict[str, Any] = _dict_or_empty((ncu_smoke or {}).get("profiler_attempt")) if ncu_smoke else {}
    nsys_smoke_state = _dict_or_empty(nsys_smoke_attempt.get("state_json"))
    ncu_smoke_state = _dict_or_empty(ncu_smoke_attempt.get("state_json"))

    if not nsys_probe["present"]:
        nsys_readiness_class = "tool_missing"
        nsys_remediation = ["Nsight Systems is not available on PATH or in the known bundled tool locations."]
    elif not importer_probe["present"]:
        nsys_readiness_class = "importer_missing"
        nsys_remediation = ["QdstrmImporter is not available, so .qdstrm traces cannot be converted into usable .nsys-rep reports."]
    elif not importer_version:
        nsys_readiness_class = "importer_runtime_blocked"
        nsys_remediation = [
            "QdstrmImporter was found but could not be executed successfully, so .qdstrm traces cannot be converted into usable .nsys-rep reports.",
        ]
        if importer_probe["version_error"]:
            nsys_remediation.append(str(importer_probe["version_error"]))
    elif not versions_match:
        nsys_readiness_class = "version_mismatch"
        nsys_remediation = ["Nsight Systems CLI and QdstrmImporter versions do not match. Matching versions are required to convert .qdstrm into .nsys-rep."]
    elif nsys_smoke_attempt and nsys_smoke_attempt.get("failure_class"):
        nsys_readiness_class = str(nsys_smoke_attempt.get("failure_class"))
        nsys_remediation = _str_list_or_empty(nsys_smoke_attempt.get("remediation"))
    elif run_smoke and system_profile.get("gpu_present"):
        ready = bool(
            nsys_smoke_state.get("rep_converted")
            and nsys_smoke_state.get("sqlite_exported")
            and nsys_smoke_state.get("stats_ingested")
        )
        nsys_readiness_class = "ready" if ready else "collection_incomplete"
        nsys_remediation = [] if ready else ["Nsight Systems did not complete report conversion, SQLite export, and non-empty summary generation for the smoke target."]
    else:
        nsys_readiness_class = "tool_ready_unverified"
        nsys_remediation = []

    if not ncu_probe["present"]:
        ncu_readiness_class = "tool_missing"
        ncu_remediation = ["Nsight Compute is not available on PATH."]
    elif ncu_smoke_attempt and ncu_smoke_attempt.get("failure_class"):
        ncu_readiness_class = str(ncu_smoke_attempt.get("failure_class"))
        ncu_remediation = _str_list_or_empty(ncu_smoke_attempt.get("remediation"))
    elif run_smoke and system_profile.get("gpu_present"):
        ready = bool(
            ncu_smoke_state.get("report_written")
            and ncu_smoke_state.get("kernel_seen")
            and ncu_smoke_state.get("metrics_collected")
        )
        ncu_readiness_class = "ready" if ready else "collection_incomplete"
        ncu_remediation = [] if ready else ["Nsight Compute did not complete a narrow kernel capture and non-empty metrics summary for the smoke target."]
    else:
        ncu_readiness_class = "tool_ready_unverified"
        ncu_remediation = []

    readiness: dict[str, Any] = {
        "profiling_readiness_version": "aqs.profiling_readiness.v1",
        "system_id": system_profile.get("system_id"),
        "permissions": permissions,
        "nsys": {
            "path": nsys_probe["path"],
            "present": bool(nsys_probe["present"]),
            "version": nsys_version,
            "version_probe_error": nsys_probe["version_error"],
            "qdstrm_importer_path": importer_probe["path"],
            "qdstrm_importer_present": bool(importer_probe["present"]),
            "qdstrm_importer_version": importer_version,
            "qdstrm_importer_version_probe_error": importer_probe["version_error"],
            "versions_match": versions_match,
            "readiness_class": nsys_readiness_class,
            "remediation": nsys_remediation,
            "smoke_attempt": _summarize_attempt(nsys_smoke_attempt) if nsys_smoke else None,
        },
        "ncu": {
            "path": ncu_probe["path"],
            "present": bool(ncu_probe["present"]),
            "version": ncu_version,
            "version_probe_error": ncu_probe["version_error"],
            "minimal_kernel_capture_possible": bool(ncu_smoke_state.get("kernel_seen")) if ncu_smoke else None,
            "gpu_counters_accessible": not (ncu_smoke_attempt.get("failure_class") == "gpu_counter_permission_denied") if ncu_smoke else None,
            "permissions_sufficient": bool(permissions["is_root"] or permissions["cap_sys_admin_effective"]),
            "readiness_class": ncu_readiness_class,
            "remediation": ncu_remediation,
            "smoke_attempt": _summarize_attempt(ncu_smoke_attempt) if ncu_smoke else None,
        },
    }
    readiness["profiling_ready"] = bool(
        readiness["nsys"]["present"]
        and readiness["nsys"]["qdstrm_importer_present"]
        and readiness["nsys"]["versions_match"]
        and bool((readiness["nsys"]["smoke_attempt"] or {}).get("state_json", {}).get("rep_converted"))
        and bool((readiness["nsys"]["smoke_attempt"] or {}).get("state_json", {}).get("sqlite_exported"))
        and bool((readiness["nsys"]["smoke_attempt"] or {}).get("state_json", {}).get("stats_ingested"))
        and readiness["ncu"]["present"]
        and bool((readiness["ncu"]["smoke_attempt"] or {}).get("state_json", {}).get("report_written"))
        and bool((readiness["ncu"]["smoke_attempt"] or {}).get("state_json", {}).get("kernel_seen"))
        and bool((readiness["ncu"]["smoke_attempt"] or {}).get("state_json", {}).get("metrics_collected"))
        and bool(readiness["ncu"]["gpu_counters_accessible"])
    )
    readiness_path = outdir / "profiling_readiness.json"
    _write_json(readiness_path, readiness)
    return readiness


def run_nsys_profile(
    *,
    manifest_path: str | Path,
    system_manifest_path: str | Path,
    outdir: str | Path | None = None,
    plan_rank: int = 1,
    objective: str = "ttfr",
    probe_strategy: str = "structural_real",
    planner_budget: str = "balanced",
    allow_distributed: bool = False,
    measurement_repeats: int = 3,
    execution_intent: str = "require_real",
    graph_mode: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    outdir = _ensure_dir(Path(outdir) if outdir else repo_root() / "artifacts" / "profiles" / "nsys")
    profiler_env = _python_launch_env()
    tool_version = _tool_version("nsys", env=profiler_env)
    importer_version = _tool_version("QdstrmImporter", env=profiler_env)
    stem = _profile_output_prefix("nsys", manifest_path, plan_rank, graph_mode=graph_mode or "off")
    execution_payload_path = outdir / f"{stem}.execution.json"
    profile_json_path = outdir / f"{stem}.profile_summary.json"
    report_prefix = outdir / stem
    report_path = outdir / f"{stem}.nsys-rep"
    qdstrm_path = outdir / f"{stem}.qdstrm"
    sqlite_path = outdir / f"{stem}.sqlite"
    stats_prefix = outdir / f"{stem}.stats"
    stats_expected = {
        "nvtxsum": outdir / f"{stats_prefix.name}_nvtxsum.csv",
        "cudaapisum": outdir / f"{stats_prefix.name}_cudaapisum.csv",
        "gpukernsum": outdir / f"{stats_prefix.name}_gpukernsum.csv",
    }
    execute_command = _execution_entrypoint_command(
        manifest_path=manifest_path,
        system_manifest_path=system_manifest_path,
        plan_rank=plan_rank,
        objective=objective,
        probe_strategy=probe_strategy,
        planner_budget=planner_budget,
        allow_distributed=allow_distributed,
        measurement_repeats=measurement_repeats,
        execution_intent=execution_intent,
        graph_mode=graph_mode,
        out_path=execution_payload_path,
    )
    command = [
        *_resolve_tool_command("nsys", env=profiler_env),
        "profile",
        "--trace=cuda,nvtx,osrt",
        "--sample=none",
        "--force-overwrite=true",
        "--output",
        str(report_prefix),
        *execute_command,
    ]
    attempt = _new_attempt(tool_kind="nsys", attempt_role="profile", command=command, stem=stem, tool_version=tool_version, importer_version=importer_version)
    attempt["state_json"]["collection_started"] = True
    try:
        completed = _run(command, cwd=repo_root(), env=profiler_env)
    except ProfileToolError as exc:
        attempt["failure_class"] = "tool_missing"
        attempt["remediation"] = ["Nsight Systems is not available on PATH or in the known bundled tool locations."]
        attempt["notes"] = str(exc)
        _raise_with_attempt(str(exc), attempt, outdir, stem, db_path=db_path)
    output_text = _record_completed_process(attempt, completed)
    run_payload = _maybe_load_execution_payload(execution_payload_path)
    if run_payload:
        attempt["run_id"] = (run_payload.get("execution_run") or {}).get("run_id")
    attempt["state_json"]["qdstrm_produced"] = qdstrm_path.exists()
    _maybe_convert_qdstrm(qdstrm_path=qdstrm_path, report_path=report_path, profiler_env=profiler_env, attempt=attempt)
    located_rep = _try_locate_artifact(report_path)
    if located_rep is not None:
        report_path = located_rep
        attempt["state_json"]["rep_converted"] = True
    attempt["artifact_presence_json"] = _artifact_presence(
        {
            "execution_payload": execution_payload_path,
            "qdstrm": qdstrm_path,
            "report": report_path,
            "sqlite": sqlite_path,
            **{f"stats_{name}": path for name, path in stats_expected.items()},
        }
    )
    if not attempt["state_json"]["rep_converted"]:
        failure_class, remediation, message = classify_nsys_failure(report_path, qdstrm_path, output_text)
        attempt["failure_class"] = failure_class
        attempt["remediation"] = remediation
        attempt["usability_state"] = _highest_state("nsys", attempt["state_json"])
        _raise_with_attempt(message, attempt, outdir, stem, db_path=db_path, run_payload=run_payload)

    export_completed = _run(
        [*_resolve_tool_command("nsys", env=profiler_env), "export", "--force-overwrite=true", "--type", "sqlite", "--output", str(sqlite_path), str(report_path)],
        cwd=repo_root(),
        env=profiler_env,
    )
    _record_completed_process(attempt, export_completed, append=True, label="nsys_export_sqlite")
    located_sqlite = _try_locate_artifact(sqlite_path)
    if located_sqlite is not None:
        sqlite_path = located_sqlite
        attempt["state_json"]["sqlite_exported"] = True

    stats_completed = _run(
        [
            *_resolve_tool_command("nsys", env=profiler_env),
            "stats",
            "--report",
            "nvtxsum",
            "--report",
            "cudaapisum",
            "--report",
            "gpukernsum",
            "--format",
            "csv",
            "--output",
            str(stats_prefix),
            str(report_path),
        ],
        cwd=repo_root(),
        env=profiler_env,
    )
    _record_completed_process(attempt, stats_completed, append=True, label="nsys_stats")
    stats_paths: dict[str, Path] = {}
    for report_name in ("nvtxsum", "cudaapisum", "gpukernsum"):
        located = _locate_stats_csv(stats_prefix, report_name)
        if located is not None:
            stats_paths[report_name] = located
    if len(stats_paths) == 3:
        attempt["state_json"]["stats_ingested"] = True
    attempt["artifact_presence_json"] = _artifact_presence(
        {
            "execution_payload": execution_payload_path,
            "qdstrm": qdstrm_path,
            "report": report_path,
            "sqlite": sqlite_path,
            **{f"stats_{name}": stats_paths.get(name, path) for name, path in stats_expected.items()},
        }
    )
    attempt["usability_state"] = _highest_state("nsys", attempt["state_json"])
    if not run_payload:
        attempt["failure_class"] = "execution_payload_missing"
        attempt["remediation"] = ["The shared execution entrypoint did not write its JSON payload, so profiler ingestion cannot continue."]
        _raise_with_attempt("shared execution payload was not written during Nsight Systems profiling", attempt, outdir, stem, db_path=db_path)
    if not attempt["state_json"]["sqlite_exported"] or not attempt["state_json"]["stats_ingested"]:
        attempt["failure_class"] = "ingestion_incomplete"
        attempt["remediation"] = ["Nsight Systems produced a report, but SQLite export or CSV stats generation did not complete."]
        _raise_with_attempt("nsys report was collected but SQLite export or stats ingestion did not complete", attempt, outdir, stem, db_path=db_path, run_payload=run_payload)

    profile_summary = reduce_nsys_artifacts(run_payload, sqlite_path, stats_paths, report_path)
    if not _nsys_summary_non_empty(profile_summary):
        attempt["failure_class"] = "summary_empty"
        attempt["remediation"] = ["Nsight Systems produced artifacts, but the parsed summary was empty. A usable .nsys-rep for this milestone requires a non-empty summary."]
        _raise_with_attempt("nsys artifacts were created but the parsed summary was empty", attempt, outdir, stem, db_path=db_path, run_payload=run_payload)
    _write_json(profile_json_path, profile_summary)
    attempt_path = _write_attempt(outdir, stem, attempt)
    _store_attempt(db_path, attempt_path, attempt, run_payload=run_payload)
    linked_assets = [
        {"role": "raw_execution_json", "path": execution_payload_path, "asset_type": "json", "run_role": "raw_execution_json"},
        {"role": "raw_profile_json", "path": profile_json_path, "asset_type": "json", "run_role": "profile_summary_json", "profile_role": "raw_profile_json"},
        {"role": "nsys_report", "path": report_path, "asset_type": "nsys-rep", "profile_role": "nsys_report"},
        {"role": "nsys_sqlite", "path": sqlite_path, "asset_type": "sqlite", "profile_role": "nsys_sqlite"},
    ]
    for report_name, path in stats_paths.items():
        linked_assets.append({"role": f"nsys_stats_csv:{report_name}", "path": path, "asset_type": "csv", "profile_role": "nsys_stats_csv"})
    _store_profile_assets(db_path, run_payload, profile_summary, linked_assets)
    payload = dict(run_payload)
    payload["profile_summary"] = profile_summary
    payload["linked_assets"] = _json_safe_value(linked_assets)
    payload["profiler_attempt"] = attempt
    return payload


def run_ncu_profile(
    *,
    manifest_path: str | Path,
    system_manifest_path: str | Path,
    outdir: str | Path | None = None,
    plan_rank: int = 1,
    objective: str = "ttfr",
    probe_strategy: str = "structural_real",
    planner_budget: str = "balanced",
    allow_distributed: bool = False,
    measurement_repeats: int = 3,
    execution_intent: str = "require_real",
    profile_mode: str = "basic",
    graph_mode: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    outdir = _ensure_dir(Path(outdir) if outdir else repo_root() / "artifacts" / "profiles" / "ncu")
    profiler_env = _python_launch_env()
    tool_version = _tool_version("ncu", env=profiler_env)
    mode_config = _load_ncu_profile_mode(profile_mode)
    stem = _profile_output_prefix("ncu", manifest_path, plan_rank, graph_mode=graph_mode or "off", variant=profile_mode)
    execution_payload_path = outdir / f"{stem}.execution.json"
    profile_json_path = outdir / f"{stem}.profile_summary.json"
    report_prefix = outdir / stem
    report_path = outdir / f"{stem}.ncu-rep"
    csv_path = outdir / f"{stem}.ncu.csv"
    execute_command = _execution_entrypoint_command(
        manifest_path=manifest_path,
        system_manifest_path=system_manifest_path,
        plan_rank=plan_rank,
        objective=objective,
        probe_strategy=probe_strategy,
        planner_budget=planner_budget,
        allow_distributed=allow_distributed,
        measurement_repeats=measurement_repeats,
        execution_intent=execution_intent,
        graph_mode=graph_mode,
        out_path=execution_payload_path,
    )
    # Keep the first real ncu slice unfiltered by default. This host/toolchain combination
    # has already shown that broad capture works while tighter NVTX filtering is brittle.
    command = [
        *_resolve_tool_command("ncu", env=profiler_env),
        "--set",
        mode_config["set"],
        "--target-processes",
        mode_config["target_processes"],
        "--replay-mode",
        mode_config["replay_mode"],
        "--export",
        str(report_prefix),
        *execute_command,
    ]
    attempt = _new_attempt(tool_kind="ncu", attempt_role="profile", command=command, stem=stem, tool_version=tool_version)
    attempt["state_json"]["launcher_started"] = True
    try:
        completed = _run(command, cwd=repo_root(), env=profiler_env)
    except ProfileToolError as exc:
        attempt["failure_class"] = "tool_missing"
        attempt["remediation"] = ["Nsight Compute is not available on PATH."]
        attempt["notes"] = str(exc)
        _raise_with_attempt(str(exc), attempt, outdir, stem, db_path=db_path)
    output_text = _record_completed_process(attempt, completed)
    run_payload = _maybe_load_execution_payload(execution_payload_path)
    if run_payload:
        attempt["run_id"] = (run_payload.get("execution_run") or {}).get("run_id")
    attempt["state_json"]["target_seen"] = "Connected to process" in output_text or "==PROF==" in output_text
    located_rep = _try_locate_artifact(report_path)
    if located_rep is not None:
        report_path = located_rep
        attempt["state_json"]["report_written"] = True
    attempt["state_json"]["kernel_seen"] = attempt["state_json"]["report_written"] and "No kernels were profiled" not in output_text and "ERR_NVGPUCTRPERM" not in output_text
    attempt["artifact_presence_json"] = _artifact_presence({"execution_payload": execution_payload_path, "report": report_path, "csv": csv_path})
    if attempt["state_json"]["report_written"]:
        import_completed = _run(
            [*_resolve_tool_command("ncu", env=profiler_env), "--import", str(report_path), "--csv", "--page", mode_config["import_page"]],
            cwd=repo_root(),
            env=profiler_env,
        )
        import_text = _record_completed_process(attempt, import_completed, append=True, label="ncu_import")
        if import_completed.returncode == 0 and import_text.strip():
            csv_path.write_text(import_text, encoding="utf-8")
            attempt["state_json"]["metrics_collected"] = True
    attempt["artifact_presence_json"] = _artifact_presence({"execution_payload": execution_payload_path, "report": report_path, "csv": csv_path})
    attempt["usability_state"] = _highest_state("ncu", attempt["state_json"])
    if not run_payload:
        attempt["failure_class"] = "execution_payload_missing"
        attempt["remediation"] = ["The shared execution entrypoint did not write its JSON payload, so profiler ingestion cannot continue."]
        _raise_with_attempt("shared execution payload was not written during Nsight Compute profiling", attempt, outdir, stem, db_path=db_path)
    if not attempt["state_json"]["report_written"] or not attempt["state_json"]["kernel_seen"] or not attempt["state_json"]["metrics_collected"]:
        failure_class, remediation, message = classify_ncu_failure(output_text, report_written=attempt["state_json"]["report_written"])
        attempt["failure_class"] = failure_class
        attempt["remediation"] = remediation
        _raise_with_attempt(message, attempt, outdir, stem, db_path=db_path, run_payload=run_payload)

    profile_summary = reduce_ncu_artifacts(
        run_payload,
        report_path,
        csv_path,
        imported_csv_text=import_text if 'import_text' in locals() else None,
        profile_mode=profile_mode,
        metric_config=mode_config,
    )
    if not _ncu_summary_non_empty(profile_summary):
        attempt["failure_class"] = "summary_empty"
        attempt["remediation"] = ["Nsight Compute produced artifacts, but the parsed metrics summary was empty. A usable .ncu-rep for this milestone requires a non-empty summary."]
        _raise_with_attempt("ncu artifacts were created but the parsed metrics summary was empty", attempt, outdir, stem, db_path=db_path, run_payload=run_payload)
    _write_json(profile_json_path, profile_summary)
    attempt_path = _write_attempt(outdir, stem, attempt)
    _store_attempt(db_path, attempt_path, attempt, run_payload=run_payload)
    linked_assets = [
        {"role": "raw_execution_json", "path": execution_payload_path, "asset_type": "json", "run_role": "raw_execution_json"},
        {"role": "raw_profile_json", "path": profile_json_path, "asset_type": "json", "run_role": "profile_summary_json", "profile_role": "raw_profile_json"},
        {"role": "ncu_report", "path": report_path, "asset_type": "ncu-rep", "profile_role": "ncu_report"},
        {"role": "ncu_csv", "path": csv_path, "asset_type": "csv", "profile_role": "ncu_csv"},
    ]
    _store_profile_assets(db_path, run_payload, profile_summary, linked_assets)
    payload = dict(run_payload)
    payload["profile_summary"] = profile_summary
    payload["linked_assets"] = _json_safe_value(linked_assets)
    payload["profiler_attempt"] = attempt
    return payload


def run_profile_smoke(
    *,
    tool: str,
    outdir: str | Path | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if tool == "nsys":
        return run_nsys_smoke(outdir=outdir, db_path=db_path)
    if tool == "ncu":
        return run_ncu_smoke(outdir=outdir, db_path=db_path)
    if tool == "all":
        base = Path(outdir) if outdir else None
        payload: dict[str, Any] = {}
        blocked = False
        for name, runner in (("nsys", run_nsys_smoke), ("ncu", run_ncu_smoke)):
            try:
                payload[name] = runner(outdir=(base / name) if base else None, db_path=db_path)
            except ProfileToolError as exc:
                blocked = True
                payload[name] = {"status": "blocked", "error": str(exc), "profiler_attempt": exc.attempt}
        if blocked:
            raise ProfileToolError("one or more profiler smoke targets were blocked", attempt={"tool_kind": "composite", "attempt_role": "smoke", "results": payload})
        return payload
    raise ValueError(f"Unsupported smoke tool {tool!r}")


__all__ = [
    "NCU_ATTEMPT_STATES",
    "NSYS_ATTEMPT_STATES",
    "PROFILER_ATTEMPT_VERSION",
    "PROFILE_REDUCTION_VERSION",
    "ProfileToolError",
    "classify_ncu_failure",
    "classify_nsys_failure",
    "collect_profiling_readiness",
    "reduce_ncu_artifacts",
    "reduce_nsys_artifacts",
    "run_ncu_profile",
    "run_ncu_smoke",
    "run_nsys_profile",
    "run_nsys_smoke",
    "run_profile_smoke",
]
