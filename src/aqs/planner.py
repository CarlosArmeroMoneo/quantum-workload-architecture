from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math

from .manifest import load_yaml, validate_system_manifest
from .utils import canonical_json, sha256_text

PLANNER_VERSION = "aqs.tnep_planner.v0"


@dataclass(frozen=True)
class PlanConfig:
    objective: str = "ttfr"
    max_error: float = 0.0
    planner_budget: str = "balanced"
    allow_distributed: bool = True
    prefer_lower_memory: bool = False
    max_candidates: int | None = None
    policy_overrides: dict[str, Any] | None = None


class PlannerError(RuntimeError):
    pass


_SYSTEM_SPEED_HINTS = {
    "h100": 7.0,
    "h200": 8.0,
    "a100": 5.5,
    "l40": 3.0,
    "rtx 4090": 3.2,
    "cpu": 0.5,
}


_DEF_GRID = {
    "quick_turnaround": {
        "mode": "exact_tn",
        "workspace_fraction": 0.18,
        "hyper_samples": 1,
        "autotune": False,
        "reuse_cache": False,
        "cache_fraction": 0.0,
        "mpi_mode": "single",
    },
    "balanced": {
        "mode": "exact_tn",
        "workspace_fraction": 0.35,
        "hyper_samples": 8,
        "autotune": True,
        "reuse_cache": True,
        "cache_fraction": 0.10,
        "mpi_mode": "single",
    },
    "deep_search": {
        "mode": "exact_tn",
        "workspace_fraction": 0.60,
        "hyper_samples": 24,
        "autotune": True,
        "reuse_cache": True,
        "cache_fraction": 0.18,
        "mpi_mode": "single",
    },
    "distributed_balanced": {
        "mode": "exact_tn_distributed",
        "workspace_fraction": 0.45,
        "hyper_samples": 16,
        "autotune": True,
        "reuse_cache": True,
        "cache_fraction": 0.12,
        "mpi_mode": "all_gpus",
    },
}

DEFAULT_PLANNER_POLICY = {
    "disable_autotune_below_repeat": 6,
    "disable_reuse_cache_below_repeat": 8,
}


def resolve_planner_policy(policy_overrides: dict[str, Any] | None = None) -> dict[str, int]:
    policy = dict(DEFAULT_PLANNER_POLICY)
    for key, value in (policy_overrides or {}).items():
        if key not in policy or value is None:
            continue
        policy[key] = max(1, int(value))
    return policy


def load_system_manifest(path: str) -> dict[str, Any]:
    manifest = load_yaml(path)
    errors = validate_system_manifest(manifest)
    if errors:
        raise PlannerError(f"Invalid system manifest {path}: {errors}")
    return manifest


def _system_speed_factor(system_manifest: dict[str, Any]) -> float:
    gpu_model = str(system_manifest.get("gpu_model") or "").lower()
    system_name = str(system_manifest.get("system_name") or "").lower()
    label = f"{gpu_model} {system_name}".strip()
    for hint, factor in _SYSTEM_SPEED_HINTS.items():
        if hint in label:
            return factor
    gpu_count = int(system_manifest.get("gpu_count") or 0)
    if gpu_count <= 0:
        return _SYSTEM_SPEED_HINTS["cpu"]
    return 1.5 + gpu_count


def _bounded(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _base_terms(manifest: dict[str, Any], features: dict[str, Any], probe: dict[str, Any], system_manifest: dict[str, Any]) -> dict[str, float]:
    static = features["static_features"]
    graph = features["graph_features"]
    repeat_count = int(static.get("repeat_count_hint", manifest.get("repeat_count_hint", 1)))
    n_qubits = int(static["n_qubits"])
    depth = int(static["depth"])
    edge_count = int(graph.get("edge_count") or 0)
    base_cost = float(probe.get("optimizer_cost") or max(2.0, (n_qubits + 1) * (depth + 1) * max(edge_count, 1)))
    log_cost = max(0.5, math.log10(base_cost + 1.0))
    structural_peak_gb = max(0.02, (n_qubits * max(depth, 1) * max(edge_count, 1)) / 1536.0)
    raw_probe_peak_gb = float(probe.get("predicted_peak_gb") or 0.0)
    if raw_probe_peak_gb > 0.0:
        peak_gb = min(raw_probe_peak_gb, structural_peak_gb * 4.0)
    else:
        peak_gb = structural_peak_gb
    speed = _system_speed_factor(system_manifest)
    graph_density = float(graph.get("density") or 0.0)
    treewidth_proxy = float(graph.get("treewidth_proxy") or max(1, graph.get("max_degree") or 1))
    return {
        "repeat_count": float(repeat_count),
        "n_qubits": float(n_qubits),
        "depth": float(depth),
        "edge_count": float(edge_count),
        "base_cost": base_cost,
        "log_cost": log_cost,
        "peak_gb": peak_gb,
        "speed": speed,
        "graph_density": graph_density,
        "treewidth_proxy": treewidth_proxy,
    }


def _candidate_templates(config: PlanConfig, system_manifest: dict[str, Any], repeat_count: int) -> list[dict[str, Any]]:
    policy = resolve_planner_policy(config.policy_overrides)
    names = ["quick_turnaround", "balanced", "deep_search"]
    if config.planner_budget == "quick":
        names = ["quick_turnaround", "balanced"]
    elif config.planner_budget == "deep":
        names = ["balanced", "deep_search"]
    if config.allow_distributed and int(system_manifest.get("gpu_count") or 0) >= 2:
        names.append("distributed_balanced")
    templates = []
    for name in names:
        base = dict(_DEF_GRID[name])
        policy_notes: list[str] = []
        if repeat_count <= 1:
            if name == "balanced":
                base["autotune"] = False
                base["reuse_cache"] = False
                base["cache_fraction"] = 0.0
            if name == "deep_search":
                base["hyper_samples"] = 12
                base["cache_fraction"] = 0.0
        if repeat_count < 6 and name == "quick_turnaround":
            base["hyper_samples"] = 2
        if base["autotune"] and repeat_count < policy["disable_autotune_below_repeat"]:
            base["autotune"] = False
            policy_notes.append(
                f"planner policy disables autotune below repeat_count_hint={policy['disable_autotune_below_repeat']}"
            )
        if base["reuse_cache"] and repeat_count < policy["disable_reuse_cache_below_repeat"]:
            base["reuse_cache"] = False
            base["cache_fraction"] = 0.0
            policy_notes.append(
                f"planner policy disables reuse_cache below repeat_count_hint={policy['disable_reuse_cache_below_repeat']}"
            )
        base["template_name"] = name
        base["policy_notes"] = policy_notes
        templates.append(base)
    if config.max_candidates is not None:
        templates = templates[: max(1, int(config.max_candidates))]
    return templates


def _explanation_list(*, template_name: str, repeat_count: int, workspace_gb: float, predicted_peak_gb: float, gpu_mem_gb: float, hyper_samples: int, mpi_ranks: int, feasibility_label: str, mode: str) -> list[str]:
    reasons: list[str] = []
    if hyper_samples >= 16:
        reasons.append("higher hyper-sampling spends more planning time to reduce contraction-path regret")
    elif hyper_samples <= 2:
        reasons.append("small planner budget prioritizes time-to-first-result over path optimality")
    if gpu_mem_gb > 0 and predicted_peak_gb > 0:
        ratio = workspace_gb / max(predicted_peak_gb, 1e-6)
        if ratio < 0.7:
            reasons.append("workspace is tight relative to largest intermediate, so extra slicing is likely")
        elif ratio > 1.2:
            reasons.append("workspace comfortably covers the current peak estimate, limiting slicing pressure")
    if repeat_count >= 8 and template_name != "quick_turnaround":
        reasons.append("repeat count makes autotune and reuse worth amortizing")
    if mode == "exact_tn_distributed" and mpi_ranks > 1:
        reasons.append("distributed exact TN lowers per-rank memory pressure but adds communication overhead")
    if feasibility_label == "infeasible":
        reasons.append("predicted peak memory exceeds the per-rank memory budget")
    if feasibility_label == "uncertain":
        reasons.append("system manifest lacks GPU capacity information, so feasibility remains uncertain")
    return reasons


def _predict_candidate_metrics(template: dict[str, Any], *, manifest: dict[str, Any], features: dict[str, Any], probe: dict[str, Any], system_manifest: dict[str, Any], config: PlanConfig) -> dict[str, Any]:
    terms = _base_terms(manifest, features, probe, system_manifest)
    repeat_count = int(terms["repeat_count"])
    gpu_count = int(system_manifest.get("gpu_count") or 0)
    gpu_mem_gb = float(system_manifest.get("gpu_mem_gb") or 0.0)
    speed = terms["speed"]
    precision = str(probe.get("precision") or "complex128")
    precision_penalty = 1.0 if precision in {"fp32", "complex64"} else 1.25

    mode = template["mode"]
    mpi_ranks = gpu_count if template["mpi_mode"] == "all_gpus" and gpu_count > 0 else 1
    workspace_gb = round(max(0.0, gpu_mem_gb * float(template["workspace_fraction"])), 3) if gpu_mem_gb > 0 else 0.0
    cache_workspace_gb = round(workspace_gb * float(template["cache_fraction"]), 3)
    hyper_samples = int(template["hyper_samples"])
    autotune = bool(template["autotune"])
    reuse_cache = bool(template["reuse_cache"])

    effective_peak_gb = terms["peak_gb"]
    if mode == "exact_tn_distributed" and mpi_ranks > 1:
        effective_peak_gb = effective_peak_gb / (mpi_ranks ** 0.65)

    workspace_factor = 1.0
    if workspace_gb > 0 and effective_peak_gb > 0:
        workspace_ratio = workspace_gb / max(effective_peak_gb, 1e-6)
        workspace_factor = _bounded(1.25 - 0.30 * min(workspace_ratio, 1.0), 0.72, 1.25)
    elif gpu_mem_gb > 0:
        workspace_factor = 1.10

    path_quality = max(0.72, 1.0 - 0.04 * math.log2(max(hyper_samples, 1)))
    planning_s = (0.18 + 0.075 * hyper_samples * terms["log_cost"] / max(speed, 0.5)) * precision_penalty
    if autotune:
        planning_s *= 1.18
    if mode == "exact_tn_distributed" and mpi_ranks > 1:
        planning_s *= 1.08

    iter_ms = 12.0 * (terms["log_cost"] ** 1.35) * path_quality * workspace_factor * precision_penalty / max(speed, 0.35)
    iter_ms *= 1.0 + 0.04 * max(0.0, terms["treewidth_proxy"] - 2.0)
    if autotune and repeat_count >= 6:
        iter_ms *= 0.90
    if reuse_cache and repeat_count >= 8:
        iter_ms *= 0.82
    if config.prefer_lower_memory:
        iter_ms *= 1.04
    if mode == "exact_tn_distributed" and mpi_ranks > 1:
        iter_ms *= (0.78 / math.sqrt(mpi_ranks)) + 0.36
        iter_ms *= 1.0 + 0.05 * max(0, mpi_ranks - 1)

    setup_s = 0.20 + 0.05 * terms["graph_density"] * terms["n_qubits"] / max(speed, 0.5)
    ttfr_s = round(setup_s + planning_s + (iter_ms / 1000.0), 6)
    iter_ms = round(iter_ms, 6)

    if repeat_count <= 1:
        gpu_seconds = ttfr_s * max(mpi_ranks, 1)
    else:
        gpu_seconds = (ttfr_s + ((repeat_count - 1) * iter_ms / 1000.0)) * max(mpi_ranks, 1)

    predicted_error = 0.0
    feasible = True
    feasibility_label = "feasible"
    if gpu_count <= 0:
        feasibility_label = "uncertain"
        feasible = False
    elif mode == "exact_tn_distributed" and mpi_ranks <= 1:
        feasibility_label = "infeasible"
        feasible = False
    else:
        mem_budget = 0.85 * gpu_mem_gb if gpu_mem_gb > 0 else 0.0
        if effective_peak_gb > mem_budget > 0:
            feasibility_label = "infeasible"
            feasible = False
        elif effective_peak_gb > 0.92 * mem_budget > 0:
            feasibility_label = "uncertain"
            feasible = False

    explanation = _explanation_list(
        template_name=str(template["template_name"]),
        repeat_count=repeat_count,
        workspace_gb=workspace_gb,
        predicted_peak_gb=effective_peak_gb,
        gpu_mem_gb=gpu_mem_gb,
        hyper_samples=hyper_samples,
        mpi_ranks=mpi_ranks,
        feasibility_label=feasibility_label,
        mode=mode,
    )
    explanation.extend(template.get("policy_notes") or [])

    candidate = {
        "project": "tnep",
        "planner_version": PLANNER_VERSION,
        "objective": config.objective,
        "mode": mode,
        "precision": precision,
        "workspace_gb": workspace_gb,
        "cache_workspace_gb": cache_workspace_gb,
        "hyper_samples": hyper_samples,
        "autotune": autotune,
        "reuse_cache": reuse_cache,
        "mpi_ranks": mpi_ranks,
        "gpu_arch_target": system_manifest.get("gpu_arch_target") or probe.get("gpu_arch_target"),
        "max_error": float(config.max_error),
        "predicted_ttfr_s": ttfr_s,
        "predicted_iter_ms": iter_ms,
        "predicted_peak_gb": round(effective_peak_gb, 6),
        "predicted_error": predicted_error,
        "predicted_gpu_seconds": round(gpu_seconds, 6),
        "predicted_planning_s": round(planning_s, 6),
        "predicted_setup_s": round(setup_s, 6),
        "speed_factor_used": round(speed, 6),
        "path_quality_factor": round(path_quality, 6),
        "workspace_factor": round(workspace_factor, 6),
        "repeat_count_used": repeat_count,
        "feasibility_label": feasibility_label,
        "explanation_json": explanation,
        "parent_probe_ids": [probe["probe_id"]],
        "template_name": template["template_name"],
        "is_feasible": feasible,
        "policy_summary_json": resolve_planner_policy(config.policy_overrides),
        "prediction_breakdown_json": {
            "predicted_planning_s": round(planning_s, 6),
            "predicted_setup_s": round(setup_s, 6),
            "speed_factor_used": round(speed, 6),
            "path_quality_factor": round(path_quality, 6),
            "workspace_factor": round(workspace_factor, 6),
            "repeat_count_used": repeat_count,
            "treewidth_proxy": round(float(terms["treewidth_proxy"]), 6),
            "graph_density": round(float(terms["graph_density"]), 6),
        },
    }
    payload = {
        "workload_id": manifest["ids"]["workload_id"],
        "candidate": candidate,
    }
    candidate["plan_id"] = "plan_" + sha256_text(canonical_json(payload))[:16]
    return candidate


def generate_plan_candidates(
    manifest: dict[str, Any],
    features: dict[str, Any],
    probe: dict[str, Any],
    system_manifest: dict[str, Any],
    config: PlanConfig | None = None,
) -> list[dict[str, Any]]:
    config = config or PlanConfig(objective=str(probe.get("objective") or "ttfr"))
    repeat_count = int(features["static_features"].get("repeat_count_hint", manifest.get("repeat_count_hint", 1)))
    templates = _candidate_templates(config, system_manifest, repeat_count)
    candidates = [
        _predict_candidate_metrics(
            template,
            manifest=manifest,
            features=features,
            probe=probe,
            system_manifest=system_manifest,
            config=config,
        )
        for template in templates
    ]
    return rank_plan_candidates(candidates, objective=config.objective)


def rank_plan_candidates(candidates: list[dict[str, Any]], objective: str = "ttfr") -> list[dict[str, Any]]:
    def objective_value(candidate: dict[str, Any]) -> float:
        if objective == "steady_state":
            return float(candidate.get("predicted_iter_ms") or float("inf"))
        if objective == "gpu_seconds":
            return float(candidate.get("predicted_gpu_seconds") or float("inf"))
        return float(candidate.get("predicted_ttfr_s") or float("inf"))

    feasibility_rank = {"feasible": 0, "uncertain": 1, "abstain": 2, "infeasible": 3}
    ordered = sorted(
        candidates,
        key=lambda cand: (
            feasibility_rank.get(str(cand.get("feasibility_label")), 99),
            objective_value(cand),
            float(cand.get("predicted_peak_gb") or 0.0),
        ),
    )
    for idx, cand in enumerate(ordered, start=1):
        cand["recommendation_rank"] = idx
    return ordered


def select_top_plan(candidates: list[dict[str, Any]], objective: str = "ttfr") -> dict[str, Any] | None:
    ranked = rank_plan_candidates(list(candidates), objective=objective)
    for candidate in ranked:
        if candidate.get("feasibility_label") in {"feasible", "uncertain"}:
            return candidate
    return ranked[0] if ranked else None


__all__ = [
    "DEFAULT_PLANNER_POLICY",
    "PLANNER_VERSION",
    "PlanConfig",
    "PlannerError",
    "generate_plan_candidates",
    "load_system_manifest",
    "rank_plan_candidates",
    "resolve_planner_policy",
    "select_top_plan",
]
