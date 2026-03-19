from __future__ import annotations

import hashlib
import importlib.util
import importlib.metadata as metadata
import json
import os
import platform
import re
import socket
import shutil
from pathlib import Path
from typing import Any

from .utils import run_command


def _safe_distribution_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _read_os_release() -> str | None:
    path = Path("/etc/os-release")
    if not path.exists():
        return platform.platform()
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            entries[key] = value.strip().strip('"')
    return entries.get("PRETTY_NAME") or platform.platform()


def _cpu_summary() -> tuple[str | None, int | None, int | None]:
    cpu_model = None
    sockets = None
    logical = os.cpu_count()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        text = cpuinfo.read_text(encoding="utf-8", errors="ignore")
        model_match = re.search(r"model name\s*:\s*(.+)", text)
        if model_match:
            cpu_model = model_match.group(1).strip()
        physical_ids = set(re.findall(r"physical id\s*:\s*(\d+)", text))
        sockets = len(physical_ids) if physical_ids else None
    return cpu_model, sockets, logical


def _ram_gb() -> float | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    text = meminfo.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"MemTotal:\s*(\d+)\s*kB", text)
    if not match:
        return None
    return round(int(match.group(1)) / 1024 / 1024, 2)


def _gpu_summary() -> dict[str, Any]:
    rc, out, _ = run_command([
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ])
    if rc != 0 or not out:
        return {
            "gpu_model": None,
            "gpu_count": 0,
            "gpu_mem_gb": None,
            "driver_version": None,
        }

    rows = [line.strip() for line in out.splitlines() if line.strip()]
    parsed: list[tuple[str, float | None, str | None]] = []
    for row in rows:
        parts = [part.strip() for part in row.split(",")]
        name = parts[0] if parts else None
        mem_gb = round(float(parts[1]) / 1024, 2) if len(parts) > 1 and parts[1] else None
        driver = parts[2] if len(parts) > 2 else None
        parsed.append((name or "unknown", mem_gb, driver))

    first = parsed[0]
    return {
        "gpu_model": first[0],
        "gpu_count": len(parsed),
        "gpu_mem_gb": first[1],
        "driver_version": first[2],
    }


def _cuda_version() -> str | None:
    rc, out, _ = run_command(["nvcc", "--version"])
    if rc == 0 and out:
        match = re.search(r"release\s+([0-9]+\.[0-9]+)", out)
        if match:
            return match.group(1)
    rc, out, _ = run_command(["nvidia-smi"])
    if rc == 0 and out:
        match = re.search(r"CUDA Version:\s*([0-9]+\.[0-9]+)", out)
        if match:
            return match.group(1)
    return None


def _tool_version(command: list[str], pattern: str | None = None) -> str | None:
    rc, out, err = run_command(command)
    text = out or err
    if rc != 0 or not text:
        return None
    if not pattern:
        return text.splitlines()[0].strip()
    match = re.search(pattern, text)
    return match.group(1) if match else text.splitlines()[0].strip()


def _resolve_tool_command(command: str) -> list[str]:
    resolved = shutil.which(command)
    if resolved:
        return [resolved]
    if command == "nsys":
        for candidate in Path("/opt/nvidia").glob("nsight-compute/*/host/target-linux-x64/nsys"):
            if candidate.exists():
                return [str(candidate)]
    return [command]


def _module_present(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _container_runtime() -> str | None:
    if Path("/.dockerenv").exists():
        return "docker"
    if os.environ.get("SINGULARITY_NAME") or os.environ.get("APPTAINER_NAME"):
        return "singularity"
    return None


def collect_system_profile() -> dict[str, Any]:
    hostname = socket.gethostname()
    hostname_hash = hashlib.sha256(hostname.encode("utf-8")).hexdigest()
    gpu = _gpu_summary()
    cpu_model, cpu_sockets, cpu_cores_logical = _cpu_summary()
    nsys_version = _tool_version([*_resolve_tool_command("nsys"), "--version"])
    ncu_version = _tool_version([*_resolve_tool_command("ncu"), "--version"])
    system_id_basis = {
        "hostname_hash": hostname_hash,
        "gpu_model": gpu["gpu_model"],
        "gpu_count": gpu["gpu_count"],
        "driver_version": gpu["driver_version"],
    }
    system_id = "sys_" + hashlib.sha256(json.dumps(system_id_basis, sort_keys=True).encode("utf-8")).hexdigest()[:16]

    return {
        "system_id": system_id,
        "hostname_hash": hostname_hash,
        "node_label": os.environ.get("AQS_NODE_LABEL"),
        "gpu_model": gpu["gpu_model"],
        "gpu_count": gpu["gpu_count"],
        "gpu_mem_gb": gpu["gpu_mem_gb"],
        "gpu_present": bool(gpu["gpu_count"]),
        "cupy_present": _module_present("cupy"),
        "cuquantum_present": _module_present("cuquantum"),
        "qiskit_present": _module_present("qiskit"),
        "cpu_model": cpu_model,
        "cpu_sockets": cpu_sockets,
        "cpu_cores_logical": cpu_cores_logical,
        "ram_gb": _ram_gb(),
        "driver_version": gpu["driver_version"],
        "cuda_version": _cuda_version(),
        "cuquantum_sdk_version": os.environ.get("CUQUANTUM_SDK_VERSION"),
        "cuquantum_python_version": _safe_distribution_version("cuquantum-python") or _safe_distribution_version("cuquantum"),
        "cudaq_version": _safe_distribution_version("cudaq"),
        "appliance_tag": os.environ.get("AQS_APPLIANCE_TAG"),
        "nsys_present": nsys_version is not None,
        "ncu_present": ncu_version is not None,
        "nsight_systems_version": nsys_version,
        "nsight_compute_version": ncu_version,
        "mpi_impl": _tool_version([*_resolve_tool_command("mpirun"), "--version"]),
        "os_release": _read_os_release(),
        "container_runtime": _container_runtime(),
        "notes": None,
    }


def collect_doctor_report(
    *,
    profiling: bool = False,
    outdir: str | Path | None = None,
    run_smoke: bool = True,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    profile = collect_system_profile()
    if not profiling:
        return {"system_profile": profile}
    from .profiler_tools import collect_profiling_readiness

    readiness = collect_profiling_readiness(
        system_profile=profile,
        outdir=outdir,
        run_smoke=run_smoke,
        db_path=db_path,
    )
    return {
        "system_profile": profile,
        "profiling_readiness": readiness,
    }
