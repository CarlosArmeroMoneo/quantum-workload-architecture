from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import dump_json
from .utils import canonical_json, sha256_text

ARCH_ANALYSIS_VERSION = "aqs.arch.v0"


class ArchAnalysisError(RuntimeError):
    pass


def _candidate_knobs(family: str) -> list[dict[str, Any]]:
    knobs = {
        "memory_capacity": [
            {"knob_name": "gpu_mem_gb_multiplier", "suggested_sweep": [1.0, 1.25, 1.5, 2.0], "unit": "x", "hypothesis": "feasibility and slicing pressure shift with additional memory headroom"},
            {"knob_name": "workspace_gb_multiplier", "suggested_sweep": [0.5, 1.0, 1.5], "unit": "x", "hypothesis": "larger workspace reduces slicing or intermediate spill pressure"},
        ],
        "memory_bandwidth": [
            {"knob_name": "effective_bandwidth_multiplier", "suggested_sweep": [1.0, 1.25, 1.5], "unit": "x", "hypothesis": "contraction-dominated cases may move if memory service rate improves"},
        ],
        "planner_roi": [
            {"knob_name": "planner_budget_multiplier", "suggested_sweep": [0.5, 1.0, 2.0], "unit": "x", "hypothesis": "more or less path-search effort may improve TTFR/steady-state tradeoffs"},
        ],
        "communication": [
            {"knob_name": "interconnect_efficiency_multiplier", "suggested_sweep": [1.0, 1.25, 1.5], "unit": "x", "hypothesis": "distributed break-even should shift if communication overhead drops"},
            {"knob_name": "mpi_sync_overhead_multiplier", "suggested_sweep": [1.0, 0.75, 0.5], "unit": "x", "hypothesis": "collective overhead determines whether scale-out is worthwhile"},
        ],
        "launch_overhead": [
            {"knob_name": "orchestration_overhead_multiplier", "suggested_sweep": [1.0, 0.75, 0.5], "unit": "x", "hypothesis": "small jobs are sensitive to launch and setup overhead"},
        ],
        "reuse_cache": [
            {"knob_name": "cache_workspace_gb", "suggested_sweep": [0.0, 2.0, 8.0, 16.0], "unit": "GB", "hypothesis": "repeated-structure workloads may benefit from larger cache workspace"},
            {"knob_name": "repeat_count_hint", "suggested_sweep": [1, 8, 32, 128], "unit": "iterations", "hypothesis": "cache and autotune ROI depends strongly on repetition depth"},
        ],
    }
    return knobs.get(family, [])


def _make_case_id(run_id: str, family: str) -> str:
    return "case_" + sha256_text(f"{run_id}:{family}:{ARCH_ANALYSIS_VERSION}")[:16]


def _looks_like_profile_summary(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    expected = {
        "profile_id",
        "profile_version",
        "profiler_kind",
        "nvtx_phase_times_json",
        "top_kernels_json",
        "dram_util_pct",
        "sm_util_pct",
        "occupancy_pct",
        "comm_time_pct",
        "derived_signals_json",
    }
    return bool(expected.intersection(obj.keys()))



def _extract_profile_summary(obj: Any) -> dict[str, Any] | None:
    if _looks_like_profile_summary(obj):
        return obj
    if isinstance(obj, dict):
        nested = obj.get("profile_summary")
        if _looks_like_profile_summary(nested):
            return nested
    return None



def _candidate_profile_summary_paths(payload_path: Path, payload: dict[str, Any]) -> list[Path]:
    candidates: list[Path] = []

    linked_assets = payload.get("linked_assets") or []
    if isinstance(linked_assets, list):
        for item in linked_assets:
            if not isinstance(item, dict):
                continue
            raw_path = item.get("path")
            if not raw_path:
                continue
            p = Path(str(raw_path))
            if not p.is_absolute():
                p = (payload_path.parent / p).resolve()
            if "profile_summary" in p.name:
                candidates.append(p)

    name = payload_path.name
    if name.endswith(".execution.json"):
        candidates.append(payload_path.with_name(name.replace(".execution.json", ".profile_summary.json")))
    candidates.append(payload_path.with_name(payload_path.stem + ".profile_summary.json"))

    for sibling in sorted(payload_path.parent.glob("*.profile_summary.json")):
        candidates.append(sibling)

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped



def _load_adjacent_profile_summary(payload_path: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    for candidate in _candidate_profile_summary_paths(payload_path, payload):
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            import json
            loaded = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        summary = _extract_profile_summary(loaded)
        if summary:
            return summary
    return None


def analyze_execution_payload(payload: dict[str, Any], *, top_k: int = 3) -> dict[str, Any]:
    selected_plan = payload.get("selected_plan") or {}
    run = payload.get("execution_run") or {}
    probe = payload.get("probe") or {}
    profile = payload.get("profile_summary") or {}
    system_manifest = payload.get("system_manifest") or {}

    if not run:
        raise ArchAnalysisError("execution payload is missing execution_run")

    # Some real profiled execution payloads store the most useful phase timing
    # metadata in execution_run.failure_detail_json rather than embedding it
    # directly under payload["profile_summary"]. When that happens we should
    # still treat the run as profiler-backed and mine those timings before
    # falling back to synthetic analysis.
    execution_detail = run.get("failure_detail_json") or {}
    if not isinstance(profile, dict):
        profile = {}
    if not isinstance(execution_detail, dict):
        execution_detail = {}

    derived = profile.get("derived_signals_json") or execution_detail.get("derived_signals_json") or {}
    phase_times = profile.get("nvtx_phase_times_json") or execution_detail.get("phase_times") or {}
    profiler_kind = str(profile.get("profiler_kind") or "")
    repeat_count = int(payload.get("repeat_count_hint") or derived.get("repeat_count_hint") or 1)
    family_id = payload.get("family_id") or derived.get("family_id") or probe.get("raw_info_json", {}).get("family_id")
    system_gpu_mem = system_manifest.get("gpu_mem_gb")
    predicted_peak_gb = float(selected_plan.get("predicted_peak_gb") or run.get("peak_mem_gb") or 0.0)
    actual_peak_gb = float(run.get("peak_mem_gb") or 0.0)
    planner_share_pct = float(derived.get("planner_share_pct") or 0.0)
    contract_share_pct = float(derived.get("contract_share_pct") or 0.0)
    launch_share_pct = float(derived.get("launch_share_pct") or 0.0)
    comm_share_pct = float(derived.get("communication_share_pct") or profile.get("comm_time_pct") or 0.0)
    memory_pressure_pct = derived.get("memory_pressure_pct")
    planner_proxy_pct = float(derived.get("planner_proxy_pct") or 0.0)
    launch_proxy_pct = float(derived.get("launch_proxy_pct") or 0.0)
    cold_to_steady_ratio = derived.get("cold_to_steady_ratio")
    memory_bound_signal = str(derived.get("memory_bound_signal") or "")
    reuse_signal = str(derived.get("reuse_signal") or "")
    avg_kernel_time_ms = derived.get("avg_kernel_time_ms")
    kernel_count = int(derived.get("kernel_count") or len(profile.get("top_kernels_json") or []))
    mode = selected_plan.get("mode")
    mpi_ranks = max(1, int(selected_plan.get("mpi_ranks") or 1))
    wall_s = float(run.get("wall_s") or 0.0)
    predicted_ttfr = float(selected_plan.get("predicted_ttfr_s") or 0.0)
    observed_ttfr = float(run.get("ttfr_s") or 0.0)
    ttfr_residual_ratio = None
    if predicted_ttfr > 0.0 and observed_ttfr >= 0.0:
        ttfr_residual_ratio = (observed_ttfr - predicted_ttfr) / predicted_ttfr

    nominations: list[dict[str, Any]] = []

    def nominate(family: str, severity: float, reason: dict[str, Any], *, nomination_source: str = "synthetic_profile_analysis") -> None:
        severity = max(0.0, min(1.0, float(severity)))
        if severity <= 0.0:
            return
        nominations.append(
            {
                "case_id": _make_case_id(run["run_id"], family),
                "run_id": run["run_id"],
                "bottleneck_family": family,
                "severity_score": round(severity, 6),
                "nomination_reason_json": reason,
                "supporting_profile_ids": [profile["profile_id"]] if profile.get("profile_id") else [],
                "nomination_source": nomination_source,
                "counterfactual_knobs": _candidate_knobs(family),
            }
        )

    real_profile = profiler_kind in {"nsys", "ncu", "both"} or str(derived.get("profile_source") or "").startswith("real_")
    if real_profile:
        planner_time_s = float(phase_times.get("contract_path") or 0.0) + float(phase_times.get("autotune") or 0.0)
        setup_time_s = float(phase_times.get("load_circuit") or 0.0) + float(phase_times.get("convert_to_einsum") or 0.0) + float(phase_times.get("postprocess") or 0.0)
        first_contract_s = float(phase_times.get("contract_first") or 0.0)
        warm_contract_s = float(phase_times.get("contract_warm") or 0.0)
        total_profiled_s = max(sum(float(value or 0.0) for value in phase_times.values()), 1e-9)
        planner_share_pct = 100.0 * planner_time_s / total_profiled_s
        setup_share_pct = 100.0 * setup_time_s / total_profiled_s
        warm_ratio = first_contract_s / max(warm_contract_s, 1e-9) if warm_contract_s > 0.0 else None
        if not phase_times:
            planner_share_pct = max(planner_share_pct, planner_proxy_pct)
            setup_share_pct = max(setup_share_pct, launch_proxy_pct)
        elif planner_proxy_pct > 0.0 or launch_proxy_pct > 0.0:
            planner_share_pct = max(planner_share_pct, planner_proxy_pct)
            setup_share_pct = max(setup_share_pct, launch_proxy_pct)
        if warm_ratio is None and cold_to_steady_ratio is not None:
            try:
                warm_ratio = float(cold_to_steady_ratio)
            except Exception:
                warm_ratio = None

        if planner_share_pct >= 15.0:
            nominate(
                "planner_roi",
                min(1.0, planner_share_pct / 60.0),
                {
                    "reason": "real profiling shows path search/autotune or one-time orchestration taking a material share of the run",
                    "planner_share_pct": round(planner_share_pct, 6),
                    "planner_time_s": round(planner_time_s, 9),
                    "planner_proxy_pct": round(planner_proxy_pct, 6),
                    "ttfr_residual_ratio": None if ttfr_residual_ratio is None else round(ttfr_residual_ratio, 6),
                    "repeat_count_hint": repeat_count,
                },
                nomination_source="real_profiler_analysis",
            )

        if setup_share_pct >= 12.0:
            nominate(
                "launch_overhead",
                min(1.0, setup_share_pct / 55.0),
                {
                    "reason": "real profiling shows load/convert/postprocess or short-kernel launch overhead consuming a meaningful share",
                    "setup_share_pct": round(setup_share_pct, 6),
                    "setup_time_s": round(setup_time_s, 9),
                    "launch_proxy_pct": round(launch_proxy_pct, 6),
                    "avg_kernel_time_ms": avg_kernel_time_ms,
                    "kernel_count": kernel_count,
                },
                nomination_source="real_profiler_analysis",
            )

        if warm_ratio is not None and warm_ratio >= 1.15:
            nominate(
                "reuse_cache",
                min(1.0, (warm_ratio - 1.0) / 1.5),
                {
                    "reason": "real cold-vs-warm contraction timings or NCU repeat proxies show measurable amortization potential",
                    "first_contract_s": round(first_contract_s, 9),
                    "warm_contract_total_s": round(warm_contract_s, 9),
                    "cold_warm_ratio": round(warm_ratio, 6),
                    "reuse_signal": reuse_signal,
                    "repeat_count_hint": repeat_count,
                },
                nomination_source="real_profiler_analysis",
            )

        if profile.get("dram_util_pct") is not None:
            dram_util_pct = float(profile.get("dram_util_pct") or 0.0)
            sm_util_pct = float(profile.get("sm_util_pct") or 0.0)
            if dram_util_pct >= 60.0 and sm_util_pct <= 80.0:
                nominate(
                    "memory_bandwidth",
                    min(1.0, dram_util_pct / 100.0),
                    {
                        "reason": "Nsight Compute indicates elevated DRAM utilization relative to SM utilization and kernel occupancy",
                        "dram_util_pct": dram_util_pct,
                        "sm_util_pct": sm_util_pct,
                        "occupancy_pct": profile.get("occupancy_pct"),
                        "memory_bound_signal": memory_bound_signal,
                        "top_kernels": profile.get("top_kernels_json") or [],
                    },
                    nomination_source="real_profiler_analysis",
                )

        nominations = sorted(nominations, key=lambda row: row["severity_score"], reverse=True)[:max(1, top_k)]
        analysis_id = "arch_" + sha256_text(
            canonical_json(
                {
                    "run_id": run["run_id"],
                    "analysis_version": ARCH_ANALYSIS_VERSION,
                    "families": [row["bottleneck_family"] for row in nominations],
                    "profile_kind": profiler_kind,
                }
            )
        )[:16]
        return {
            "analysis_id": analysis_id,
            "analysis_version": ARCH_ANALYSIS_VERSION,
            "source_kind": "execution_payload",
            "source_run_id": run.get("run_id"),
            "source_profile_id": profile.get("profile_id"),
            "workload_id": payload.get("workload_id"),
            "family_id": family_id,
            "repeat_count_hint": repeat_count,
            "selected_mode": mode,
            "nominations": nominations,
        }

    if isinstance(system_gpu_mem, (int, float)) and float(system_gpu_mem) > 0.0:
        capacity_ratio = max(predicted_peak_gb, actual_peak_gb) / float(system_gpu_mem)
        if capacity_ratio >= 0.60:
            nominate(
                "memory_capacity",
                min(1.0, capacity_ratio),
                {
                    "reason": "peak memory is consuming a substantial fraction of system memory headroom",
                    "capacity_ratio": round(capacity_ratio, 6),
                    "system_gpu_mem_gb": float(system_gpu_mem),
                    "predicted_peak_gb": predicted_peak_gb,
                    "actual_peak_gb": actual_peak_gb,
                },
            )

    if planner_share_pct >= 20.0 and repeat_count <= 4:
        nominate(
            "planner_roi",
            min(1.0, planner_share_pct / 65.0 + (0.25 if repeat_count == 1 else 0.0)),
            {
                "reason": "planner/setup share is high relative to a low repeat count",
                "planner_share_pct": planner_share_pct,
                "repeat_count_hint": repeat_count,
                "ttfr_residual_ratio": None if ttfr_residual_ratio is None else round(ttfr_residual_ratio, 6),
            },
        )

    if mode == "exact_tn_distributed" and mpi_ranks > 1:
        nominate(
            "communication",
            min(1.0, max(comm_share_pct / 35.0, 0.15 * (mpi_ranks - 1))),
            {
                "reason": "distributed execution introduces a non-trivial communication/synchronization share",
                "communication_share_pct": comm_share_pct,
                "mpi_ranks": mpi_ranks,
                "mode": mode,
            },
        )

    if launch_share_pct >= 18.0 or (wall_s > 0.0 and wall_s <= 0.05 and planner_share_pct + launch_share_pct >= 35.0):
        nominate(
            "launch_overhead",
            min(1.0, max(launch_share_pct / 50.0, (planner_share_pct + launch_share_pct) / 100.0)),
            {
                "reason": "non-contraction setup and orchestration dominate a small or TTFR-heavy workload",
                "launch_share_pct": launch_share_pct,
                "planner_share_pct": planner_share_pct,
                "wall_s": wall_s,
            },
        )

    if repeat_count >= 8 and (bool(selected_plan.get("reuse_cache")) or planner_share_pct <= 25.0):
        nominate(
            "reuse_cache",
            min(1.0, repeat_count / 64.0 + (0.15 if bool(selected_plan.get("reuse_cache")) else 0.0)),
            {
                "reason": "repeated structure makes cache/reuse sensitivity worth studying",
                "repeat_count_hint": repeat_count,
                "reuse_cache": bool(selected_plan.get("reuse_cache")),
                "cache_workspace_gb": float(selected_plan.get("cache_workspace_gb") or 0.0),
            },
        )

    if contract_share_pct >= 65.0 and (memory_pressure_pct is None or float(memory_pressure_pct) < 70.0):
        nominate(
            "memory_bandwidth",
            min(1.0, contract_share_pct / 100.0),
            {
                "reason": "contraction dominates runtime while memory capacity does not appear to be the binding constraint",
                "contract_share_pct": contract_share_pct,
                "memory_pressure_pct": memory_pressure_pct,
                "largest_intermediate": derived.get("largest_intermediate"),
            },
        )

    nominations = sorted(nominations, key=lambda row: row["severity_score"], reverse=True)[:max(1, top_k)]

    analysis_id = "arch_" + sha256_text(
        canonical_json(
            {
                "run_id": run["run_id"],
                "analysis_version": ARCH_ANALYSIS_VERSION,
                "families": [row["bottleneck_family"] for row in nominations],
            }
        )
    )[:16]
    return {
        "analysis_id": analysis_id,
        "analysis_version": ARCH_ANALYSIS_VERSION,
        "source_kind": "execution_payload",
        "source_run_id": run.get("run_id"),
        "source_profile_id": profile.get("profile_id"),
        "workload_id": payload.get("workload_id"),
        "family_id": family_id,
        "repeat_count_hint": repeat_count,
        "selected_mode": mode,
        "nominations": nominations,
    }


def analyze_measured_validation_summary(summary: dict[str, Any], *, top_k_per_workload: int = 2) -> dict[str, Any]:
    results = summary.get("results")
    if not isinstance(results, list):
        raise ArchAnalysisError("measured validation summary is missing results")

    workload_analyses = []
    family_counts: dict[str, int] = {}
    family_severity: dict[str, float] = {}

    for workload in results:
        selected_plan_id = workload.get("selected_plan_id")
        selected_eval = None
        for evaluation in workload.get("evaluations", []):
            if evaluation.get("plan_id") == selected_plan_id:
                selected_eval = evaluation
                break
        if selected_eval is None and workload.get("evaluations"):
            selected_eval = workload["evaluations"][0]
        if selected_eval is None:
            continue

        payload = {
            "workload_id": workload.get("workload_id"),
            "family_id": workload.get("family_id"),
            "repeat_count_hint": workload.get("repeat_count_hint") or 1,
            "selected_plan": selected_eval.get("candidate") or {},
            "execution_run": selected_eval.get("execution_run") or {},
            "profile_summary": selected_eval.get("profile_summary") or (selected_eval.get("execution_run") or {}).get("profile_summary") or {},
            "probe": {"raw_info_json": {"family_id": workload.get("family_id")}},
            "system_manifest": summary.get("system_manifest") or {},
        }
        analysis = analyze_execution_payload(payload, top_k=top_k_per_workload)
        workload_analyses.append(analysis)
        for nomination in analysis.get("nominations", []):
            family = nomination["bottleneck_family"]
            family_counts[family] = family_counts.get(family, 0) + 1
            family_severity[family] = family_severity.get(family, 0.0) + float(nomination.get("severity_score") or 0.0)

    ranked_families = [
        {
            "bottleneck_family": family,
            "count": count,
            "mean_severity": round(family_severity[family] / max(count, 1), 6),
        }
        for family, count in family_counts.items()
    ]
    ranked_families.sort(key=lambda row: (row["count"], row["mean_severity"]), reverse=True)

    analysis_id = "arch_" + sha256_text(
        canonical_json(
            {
                "source": summary.get("validation_run_id") or summary.get("dataset_name"),
                "analysis_version": ARCH_ANALYSIS_VERSION,
                "families": ranked_families,
            }
        )
    )[:16]
    return {
        "analysis_id": analysis_id,
        "analysis_version": ARCH_ANALYSIS_VERSION,
        "source_kind": "measured_validation_summary",
        "source_validation_run_id": summary.get("validation_run_id"),
        "dataset_name": summary.get("dataset_name"),
        "objective": summary.get("objective"),
        "workload_count": len(workload_analyses),
        "ranked_bottleneck_families": ranked_families,
        "workload_analyses": workload_analyses,
    }


def analyze_execution_json(path: str | Path, *, out: str | Path | None = None) -> dict[str, Any]:
    import json

    payload_path = Path(path)
    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    profile = _extract_profile_summary(payload.get("profile_summary"))
    if profile is None:
        profile = _load_adjacent_profile_summary(payload_path, payload)
        if profile is not None:
            payload["profile_summary"] = profile

    analysis = analyze_execution_payload(payload)
    if out:
        dump_json(analysis, out)
    return analysis


def analyze_validation_json(path: str | Path, *, out: str | Path | None = None) -> dict[str, Any]:
    import json

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    analysis = analyze_measured_validation_summary(payload)
    if out:
        dump_json(analysis, out)
    return analysis


__all__ = [
    "ARCH_ANALYSIS_VERSION",
    "ArchAnalysisError",
    "analyze_execution_payload",
    "analyze_measured_validation_summary",
    "analyze_execution_json",
    "analyze_validation_json",
]
