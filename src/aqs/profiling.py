from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
import time

from .nvtx import NVTX_PHASE_VERSION, nvtx_range
from .repo_metadata import capture_repo_metadata
from .utils import canonical_json, sha256_text

PROFILE_VERSION = "aqs.profile.v0"


@dataclass
class PhaseRecorder:
    phase_times: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def phase(self, name: str, *, emit_nvtx: bool = False):
        start = time.perf_counter()
        try:
            if emit_nvtx:
                with nvtx_range(name):
                    yield
            else:
                yield
        finally:
            elapsed = max(time.perf_counter() - start, 0.0)
            self.phase_times[name] = self.phase_times.get(name, 0.0) + elapsed


def _round_dict(values: dict[str, float]) -> dict[str, float]:
    return {key: round(max(value, 0.0), 9) for key, value in values.items()}


def _scaled_phases(raw_phases: dict[str, float], target_total: float) -> dict[str, float]:
    positive_total = sum(max(value, 0.0) for value in raw_phases.values())
    if target_total <= 0.0:
        return _round_dict({key: max(value, 0.0) for key, value in raw_phases.items()})
    if positive_total <= 0.0:
        return _round_dict({"unattributed": target_total})
    scale = target_total / positive_total
    return _round_dict({key: max(value, 0.0) * scale for key, value in raw_phases.items()})


def build_synthetic_profile_summary(
    run: dict[str, Any],
    plan: dict[str, Any],
    *,
    repeat_count: int,
    system_manifest: dict[str, Any] | None,
    probe: dict[str, Any] | None,
    raw_source: dict[str, Any] | None,
    measured_phase_times: dict[str, float] | None,
    base_measurement: dict[str, Any] | None,
    adjustment_factors: dict[str, float] | None,
) -> dict[str, Any]:
    measured_phase_times = measured_phase_times or {}
    base_measurement = base_measurement or {}
    adjustment_factors = adjustment_factors or {}
    raw_source = raw_source or {}
    system_manifest = system_manifest or {}
    wall_s = float(run.get("wall_s") or 0.0)
    execution_detail = run.get("failure_detail_json") or {}

    build_inputs_s = float(measured_phase_times.get("build_inputs") or 0.0)
    postprocess_s = float(measured_phase_times.get("postprocess") or 0.0)

    planning_multiplier = float(adjustment_factors.get("planning_multiplier") or 1.0)
    iter_multiplier = float(adjustment_factors.get("iter_multiplier") or 1.0)
    distributed_iter_bonus = float(adjustment_factors.get("distributed_iter_bonus") or 1.0)
    distributed_setup_penalty = float(adjustment_factors.get("distributed_setup_penalty") or 1.0)

    base_path_s = float(base_measurement.get("path_s") or 0.0)
    base_first_contract_s = float(base_measurement.get("first_contract_s") or 0.0)
    steady_iter_ms = float(run.get("steady_iter_ms") or 0.0)
    mpi_ranks = max(1, int(plan.get("mpi_ranks") or 1))

    planner_total_s = base_path_s * planning_multiplier * distributed_setup_penalty
    autotune_s = 0.0
    if bool(plan.get("autotune")):
        autotune_s = max(planner_total_s - base_path_s, 0.0)
    path_search_s = max(planner_total_s - autotune_s, 0.0)

    first_contract_s = base_first_contract_s * iter_multiplier * distributed_iter_bonus
    steady_contract_s = max((max(repeat_count, 1) - 1) * (steady_iter_ms / 1000.0), 0.0)

    mpi_sync_s = 0.0
    if plan.get("mode") == "exact_tn_distributed" and mpi_ranks > 1:
        mpi_sync_s = wall_s * min(0.45, 0.06 * (mpi_ranks - 1))

    kernel_overhead_s = 0.0
    if bool(plan.get("reuse_cache")) and repeat_count > 1:
        kernel_overhead_s += wall_s * 0.02
    if bool(plan.get("autotune")) and repeat_count > 1:
        kernel_overhead_s += wall_s * 0.015

    raw_phases = {
        "build_inputs": build_inputs_s,
        "path_search": path_search_s,
        "autotune": autotune_s,
        "first_contract": first_contract_s,
        "steady_contract": steady_contract_s,
        "mpi_sync": mpi_sync_s,
        "cache_orchestration": kernel_overhead_s,
        "postprocess": postprocess_s,
    }
    scaled_phases = _scaled_phases(raw_phases, wall_s)

    contract_time_s = scaled_phases.get("first_contract", 0.0) + scaled_phases.get("steady_contract", 0.0)
    planner_time_s = scaled_phases.get("path_search", 0.0) + scaled_phases.get("autotune", 0.0)
    launch_time_s = scaled_phases.get("build_inputs", 0.0) + scaled_phases.get("postprocess", 0.0) + scaled_phases.get("cache_orchestration", 0.0)
    comm_time_s = scaled_phases.get("mpi_sync", 0.0)

    def pct(value: float) -> float:
        return round((100.0 * value / wall_s), 3) if wall_s > 0.0 else 0.0

    system_gpu_mem_gb = system_manifest.get("gpu_mem_gb")
    predicted_peak_gb = float(plan.get("predicted_peak_gb") or run.get("peak_mem_gb") or 0.0)
    if isinstance(system_gpu_mem_gb, (int, float)) and float(system_gpu_mem_gb) > 0.0:
        memory_pressure_pct = round(min(100.0, 100.0 * predicted_peak_gb / float(system_gpu_mem_gb)), 3)
    else:
        memory_pressure_pct = None

    contract_share_pct = pct(contract_time_s)
    planner_share_pct = pct(planner_time_s)
    launch_share_pct = pct(launch_time_s)
    comm_share_pct = pct(comm_time_s)

    top_kernels = [
        {
            "name": "contract_execute_proxy",
            "time_s": round(contract_time_s, 9),
            "time_pct": contract_share_pct,
            "kind": "compute_proxy",
        },
        {
            "name": "contract_path_proxy",
            "time_s": round(planner_time_s, 9),
            "time_pct": planner_share_pct,
            "kind": "planner_proxy",
        },
    ]
    if comm_time_s > 0.0:
        top_kernels.append(
            {
                "name": "mpi_sync_proxy",
                "time_s": round(comm_time_s, 9),
                "time_pct": comm_share_pct,
                "kind": "communication_proxy",
            }
        )
    if launch_time_s > 0.0:
        top_kernels.append(
            {
                "name": "launch_postprocess_proxy",
                "time_s": round(launch_time_s, 9),
                "time_pct": launch_share_pct,
                "kind": "overhead_proxy",
            }
        )

    derived_signals = {
        "profile_source": "synthetic_phase_profile",
        "profile_notes": "phase times are measured/model-scaled on the structural executor and are not Nsight traces",
        "repeat_count_hint": repeat_count,
        "family_id": raw_source.get("family_id") or (probe or {}).get("raw_info_json", {}).get("family_id"),
        "tensor_count": raw_source.get("tensor_count"),
        "layer_count": raw_source.get("layer_count"),
        "planner_share_pct": planner_share_pct,
        "contract_share_pct": contract_share_pct,
        "launch_share_pct": launch_share_pct,
        "communication_share_pct": comm_share_pct,
        "memory_pressure_pct": memory_pressure_pct,
        "probe_input_kind": raw_source.get("probe_input_kind"),
        "largest_intermediate": base_measurement.get("largest_intermediate"),
        "optimizer_cost": base_measurement.get("optimizer_cost"),
        "graph_mode": run.get("graph_mode") or execution_detail.get("graph_mode") or plan.get("graph_mode") or "off",
    }

    profile_id = "prof_" + sha256_text(
        canonical_json(
            {
                "run_id": run["run_id"],
                "profile_version": PROFILE_VERSION,
                "profiler_kind": "synthetic",
                "phase_times": scaled_phases,
            }
        )
    )[:16]
    repo_metadata = capture_repo_metadata()
    return {
        "profile_id": profile_id,
        "run_id": run["run_id"],
        "profiler_kind": "synthetic",
        "nvtx_phase_times_json": scaled_phases,
        "top_kernels_json": top_kernels,
        "dram_util_pct": None if memory_pressure_pct is None else round(min(95.0, 0.35 * memory_pressure_pct + 0.45 * contract_share_pct), 3),
        "sm_util_pct": round(min(95.0, 0.60 * contract_share_pct + 0.10 * max(0.0, 100.0 - (memory_pressure_pct or 0.0))), 3),
        "occupancy_pct": round(min(95.0, 30.0 + min(float(raw_source.get("tensor_count") or 0.0), 64.0)), 3),
        "comm_time_pct": comm_share_pct,
        "nsys_asset_id": None,
        "ncu_asset_id": None,
        "profile_version": PROFILE_VERSION,
        "repo_metadata": repo_metadata,
        "derived_signals_json": {
            **derived_signals,
            "nvtx_phase_version": NVTX_PHASE_VERSION,
            "repo_metadata": repo_metadata,
        },
    }


__all__ = [
    "PROFILE_VERSION",
    "PhaseRecorder",
    "build_synthetic_profile_summary",
]
