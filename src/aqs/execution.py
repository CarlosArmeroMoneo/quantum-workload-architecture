from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import statistics
import time
import json
from pathlib import Path
from typing import Any

import opt_einsum as oe

from .doctor import collect_system_profile
from .execution_real import (
    REAL_EXECUTION_SOURCE,
    RealExecutionError,
    execute_real_plan_candidate,
)
from .features import extract_feature_snapshot
from .graph_modes import normalize_graph_mode
from .manifest import load_yaml
from .normalize import normalize_workload_manifest
from .planner import PlanConfig, generate_plan_candidates, load_system_manifest, select_top_plan
from .profiling import PhaseRecorder, build_synthetic_profile_summary
from .repo_metadata import capture_repo_metadata
from .tnprobe import ProbeConfig, _dtype_from_precision, _select_probe_input, run_exact_tn_probe
from .utils import canonical_json, sha256_text

EXECUTION_VERSION = "aqs.execution.v2"
STRUCTURAL_EXECUTION_SOURCE = "measured_structural_cpu_hybrid"
PLAN_BUNDLE_VERSION = "aqs.plan_bundle.v1"


@dataclass(frozen=True)
class ExecutionConfig:
    objective: str = "ttfr"
    precision: str = "complex128"
    probe_strategy: str = "structural_real"
    measurement_repeats: int = 3
    ttfr_repeats: int = 1
    max_tensor_count: int = 64
    max_qubits: int = 12
    execution_intent: str = "optional_real"
    replicate_idx: int = 0
    graph_mode: str = "off"


class ExecutionError(RuntimeError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_output_digest(result: Any) -> str:
    if hasattr(result, "tobytes"):
        payload = result.tobytes()[:256]
        return "out_" + sha256_text(payload.hex())[:16]
    return "out_" + sha256_text(repr(result))[:16]


def _normalized_path(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve()).replace("\\", "/")


def _manifest_digest(payload: dict[str, Any]) -> str:
    return sha256_text(canonical_json(payload))


def _build_plan_bundle_scope(
    workload_manifest_path: str | Path,
    system_manifest_path: str | Path,
    workload_manifest: dict[str, Any],
    system_manifest: dict[str, Any],
    system_profile: dict[str, Any],
    *,
    objective: str,
    probe_strategy: str,
    planner_budget: str,
    allow_distributed: bool,
    max_candidates: int | None,
) -> dict[str, Any]:
    scope = {
        "workload_manifest_path": _normalized_path(workload_manifest_path),
        "workload_manifest_digest": _manifest_digest(workload_manifest),
        "workload_id": workload_manifest["ids"]["workload_id"],
        "family_id": workload_manifest.get("family_id"),
        "repeat_count_hint": int(workload_manifest.get("repeat_count_hint") or 1),
        "system_manifest_path": _normalized_path(system_manifest_path),
        "system_manifest_digest": _manifest_digest(system_manifest),
        "system_name": system_manifest.get("system_name"),
        "system_id": system_profile.get("system_id"),
        "objective": objective,
        "probe_strategy": probe_strategy,
        "planner_budget": planner_budget,
        "allow_distributed": bool(allow_distributed),
        "max_candidates": int(max_candidates) if max_candidates is not None else None,
    }
    return {
        **scope,
        "compatibility_fingerprint": "pbf_" + sha256_text(canonical_json(scope))[:16],
    }


def _build_plan_bundle_payload(
    *,
    scope: dict[str, Any],
    selected_plan: dict[str, Any],
    repo_metadata: dict[str, Any],
    selection_source: str,
    plan_rank: int,
    candidate_count: int,
) -> dict[str, Any]:
    bundle_id = "bundle_" + sha256_text(
        canonical_json(
            {
                "scope": scope,
                "selected_plan": selected_plan,
            }
        )
    )[:16]
    return {
        "api_version": PLAN_BUNDLE_VERSION,
        "bundle_id": bundle_id,
        "created_at": _utc_now_iso(),
        "bundle_scope": scope,
        "compatibility_fingerprint": scope["compatibility_fingerprint"],
        "selected_plan": dict(selected_plan),
        "selection_context": {
            "selection_source": selection_source,
            "plan_rank": int(plan_rank),
            "candidate_count": int(candidate_count),
        },
        "repo_metadata": repo_metadata,
    }


def _load_plan_bundle(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise ExecutionError(f"Plan bundle at {path} could not be decoded as JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExecutionError(f"Plan bundle at {path} must decode to a JSON object")
    if payload.get("api_version") != PLAN_BUNDLE_VERSION:
        raise ExecutionError(
            f"Plan bundle at {path} must declare api_version={PLAN_BUNDLE_VERSION!r}, "
            f"got {payload.get('api_version')!r}"
        )
    if not isinstance(payload.get("bundle_scope"), dict):
        raise ExecutionError(f"Plan bundle at {path} must include a bundle_scope object")
    if not isinstance(payload.get("selected_plan"), dict):
        raise ExecutionError(f"Plan bundle at {path} must include a selected_plan object")
    return payload


def _assess_plan_bundle_compatibility(bundle: dict[str, Any], expected_scope: dict[str, Any]) -> dict[str, Any]:
    bundle_scope = dict(bundle.get("bundle_scope") or {})
    compare_keys = [
        "workload_manifest_path",
        "workload_manifest_digest",
        "workload_id",
        "family_id",
        "repeat_count_hint",
        "system_manifest_path",
        "system_manifest_digest",
        "system_name",
        "system_id",
        "objective",
        "probe_strategy",
        "planner_budget",
        "allow_distributed",
        "max_candidates",
    ]
    mismatched_fields = [
        key
        for key in compare_keys
        if bundle_scope.get(key) != expected_scope.get(key)
    ]
    stored_fingerprint = bundle.get("compatibility_fingerprint")
    scope_fingerprint = bundle_scope.get("compatibility_fingerprint")
    expected_fingerprint = expected_scope.get("compatibility_fingerprint")
    fingerprint_matches = stored_fingerprint == scope_fingerprint == expected_fingerprint
    compatible = not mismatched_fields and fingerprint_matches
    if compatible:
        reason = "bundle scope matched the current workload/system selection context exactly"
    elif mismatched_fields:
        reason = "bundle scope mismatched the current workload/system selection context"
    else:
        reason = "bundle compatibility fingerprint did not match the current scope"
    return {
        "compatible": compatible,
        "reason": reason,
        "mismatched_fields": mismatched_fields,
        "bundle_scope": bundle_scope,
        "expected_scope": expected_scope,
        "bundle_id": bundle.get("bundle_id"),
        "stored_fingerprint": stored_fingerprint,
        "expected_fingerprint": expected_fingerprint,
    }


def _write_plan_bundle(path: str | Path, payload: dict[str, Any]) -> None:
    bundle_path = Path(path)
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _guardrail_error(raw: dict[str, Any], config: ExecutionConfig) -> str | None:
    n_qubits = int(raw.get("n_qubits") or 0)
    tensor_count = int(raw.get("tensor_count") or 0)
    if n_qubits > config.max_qubits:
        return f"workload exceeds measured-executor qubit guardrail ({n_qubits} > {config.max_qubits})"
    if tensor_count > config.max_tensor_count:
        return f"workload exceeds measured-executor tensor guardrail ({tensor_count} > {config.max_tensor_count})"
    return None


def _build_execution_args(workload_manifest: dict[str, Any], config: ExecutionConfig) -> tuple[list[Any], dict[str, Any]]:
    dtype = _dtype_from_precision(config.precision)
    return _select_probe_input(
        workload_manifest,
        ProbeConfig(precision=config.precision, probe_strategy=config.probe_strategy),
        dtype,
    )


def _measure_base_contract(args: list[Any], repeats: int) -> tuple[dict[str, Any], Any]:
    t0 = time.perf_counter()
    path, path_info = oe.contract_path(*args, optimize="greedy")
    path_s = max(time.perf_counter() - t0, 0.0)

    iter_samples = []
    result = None
    for _ in range(max(1, repeats)):
        t1 = time.perf_counter()
        result = oe.contract(*args, optimize=path)
        iter_samples.append(max(time.perf_counter() - t1, 0.0))

    first_contract_s = iter_samples[0]
    steady_iter_ms = statistics.median(iter_samples[1:] or iter_samples) * 1000.0
    return {
        "path_s": round(path_s, 9),
        "first_contract_s": round(first_contract_s, 9),
        "steady_iter_ms": round(steady_iter_ms, 6),
        "repeat_samples_ms": [round(sample * 1000.0, 6) for sample in iter_samples],
        "path_length": len(path) if path is not None else None,
        "largest_intermediate": float(getattr(path_info, "largest_intermediate", 0.0)) if path_info is not None else None,
        "optimizer_cost": float(getattr(path_info, "opt_cost", 0.0)) if path_info is not None else None,
    }, result


def _apply_plan_adjustments(base: dict[str, Any], plan: dict[str, Any], repeat_count: int) -> tuple[dict[str, Any], dict[str, float]]:
    hyper = max(1, int(plan.get("hyper_samples") or 1))
    mpi_ranks = max(1, int(plan.get("mpi_ranks") or 1))
    workspace_gb = float(plan.get("workspace_gb") or 0.0)
    predicted_peak_gb = max(float(plan.get("predicted_peak_gb") or 0.0), 1e-9)

    planning_mult = 1.0 + 0.05 * math.log2(hyper)
    if bool(plan.get("autotune")):
        planning_mult *= 1.08

    iter_mult = max(0.78, 1.0 - 0.025 * math.log2(hyper))
    if repeat_count >= 8 and bool(plan.get("autotune")):
        iter_mult *= 0.93
    if repeat_count >= 8 and bool(plan.get("reuse_cache")):
        iter_mult *= 0.86
    if workspace_gb > 0:
        workspace_ratio = workspace_gb / predicted_peak_gb
        if workspace_ratio < 1.0:
            iter_mult *= 1.0 + 0.10 * (1.0 - workspace_ratio)
        elif workspace_ratio > 1.1:
            iter_mult *= 0.96
    else:
        workspace_ratio = 0.0

    distributed_iter_bonus = 1.0
    distributed_setup_penalty = 1.0
    if plan.get("mode") == "exact_tn_distributed" and mpi_ranks > 1:
        distributed_setup_penalty = 1.04 + 0.02 * max(0, mpi_ranks - 1)
        distributed_iter_bonus = min(0.92, 0.88 / math.sqrt(mpi_ranks) + 0.30)

    ttfr_s = (float(base["path_s"]) * planning_mult * distributed_setup_penalty) + float(base["first_contract_s"]) * iter_mult * distributed_iter_bonus
    steady_iter_ms = float(base["steady_iter_ms"]) * iter_mult * distributed_iter_bonus
    wall_s = ttfr_s if repeat_count <= 1 else ttfr_s + ((repeat_count - 1) * steady_iter_ms / 1000.0)
    gpu_seconds = wall_s * mpi_ranks

    adjusted = {
        "ttfr_s": round(ttfr_s, 6),
        "steady_iter_ms": round(steady_iter_ms, 6),
        "wall_s": round(wall_s, 6),
        "gpu_seconds": round(gpu_seconds, 6),
        "peak_mem_gb": round(float(plan.get("predicted_peak_gb") or 0.0) * (0.97 + 0.04 * min(math.log2(hyper), 4.0) / 4.0), 6),
        "peak_workspace_gb": round(workspace_gb, 6),
    }
    factors = {
        "planning_multiplier": round(planning_mult, 6),
        "iter_multiplier": round(iter_mult, 6),
        "distributed_iter_bonus": round(distributed_iter_bonus, 6),
        "distributed_setup_penalty": round(distributed_setup_penalty, 6),
        "workspace_ratio": round(workspace_ratio, 6),
    }
    return adjusted, factors


def _build_run_id(payload: dict[str, Any]) -> str:
    return "run_" + sha256_text(
        canonical_json(
            {
                "plan_id": payload["plan_id"],
                "system_id": payload["system_id"],
                "replicate_idx": payload["replicate_idx"],
                "graph_mode": payload.get("graph_mode") or "off",
                "status": payload["status"],
                "execution_source": payload["execution_source"],
            }
        )
    )[:16]


def _failure_run(
    plan: dict[str, Any],
    workload_manifest: dict[str, Any],
    system_profile: dict[str, Any],
    *,
    replicate_idx: int,
    execution_source: str,
    status: str,
    detail: dict[str, Any],
) -> dict[str, Any]:
    graph_mode = str(detail.get("graph_mode") or "off")
    payload = {
        "plan_id": plan["plan_id"],
        "workload_id": workload_manifest["ids"]["workload_id"],
        "system_id": system_profile["system_id"],
        "replicate_idx": replicate_idx,
        "graph_mode": graph_mode,
        "status": status,
        "started_at": _utc_now_iso(),
        "finished_at": _utc_now_iso(),
        "wall_s": None,
        "ttfr_s": None,
        "steady_iter_ms": None,
        "gpu_seconds": None,
        "peak_mem_gb": None,
        "peak_workspace_gb": None,
        "output_digest": None,
        "failure_detail_json": detail,
        "execution_source": execution_source,
    }
    payload["run_id"] = _build_run_id(payload)
    return payload


def _execute_structural_plan_candidate_bundle(
    workload_manifest: dict[str, Any],
    plan: dict[str, Any],
    *,
    system_profile: dict[str, Any],
    system_manifest: dict[str, Any] | None,
    probe: dict[str, Any] | None,
    config: ExecutionConfig,
    fallback_detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    system_manifest = system_manifest or {}
    repeat_count = int(workload_manifest.get("repeat_count_hint") or 1)
    started_at = _utc_now_iso()
    profiler = PhaseRecorder()

    status = "success"
    output_digest = None
    failure_detail_json: dict[str, Any] = {}
    measured = {
        "wall_s": None,
        "ttfr_s": None,
        "steady_iter_ms": None,
        "gpu_seconds": None,
        "peak_mem_gb": None,
        "peak_workspace_gb": None,
    }
    base: dict[str, Any] | None = None
    factors: dict[str, float] | None = None
    raw: dict[str, Any] | None = None
    profile_summary = None

    if plan.get("mode") not in {"exact_tn", "exact_tn_distributed"}:
        status = "unsupported_semantics"
        failure_detail_json = {
            "reason": f"measured executor currently supports exact TN modes only, got {plan.get('mode')!r}",
            "execution_version": EXECUTION_VERSION,
            "graph_mode": config.graph_mode,
        }
    else:
        try:
            with profiler.phase("build_inputs"):
                args, raw = _build_execution_args(workload_manifest, config)
                guardrail_error = _guardrail_error(raw, config)
            if guardrail_error:
                status = "runtime_error"
                failure_detail_json = {
                    "reason": guardrail_error,
                    "raw_probe_source": raw,
                    "execution_version": EXECUTION_VERSION,
                    "graph_mode": config.graph_mode,
                }
            else:
                base, result = _measure_base_contract(args, config.measurement_repeats)
                measured, factors = _apply_plan_adjustments(base, plan, repeat_count)
                with profiler.phase("postprocess"):
                    output_digest = _safe_output_digest(result)
                failure_detail_json = {
                    "execution_source": STRUCTURAL_EXECUTION_SOURCE,
                    "execution_version": EXECUTION_VERSION,
                    "probe_strategy": config.probe_strategy,
                    "execution_intent": config.execution_intent,
                    "graph_mode": config.graph_mode,
                    "raw_probe_source": raw,
                    "base_measurement": base,
                    "adjustment_factors": factors,
                    "measured_phase_times": profiler.phase_times,
                }
        except Exception as exc:
            status = "runtime_error"
            failure_detail_json = {
                "reason": str(exc),
                "execution_source": STRUCTURAL_EXECUTION_SOURCE,
                "execution_version": EXECUTION_VERSION,
                "execution_intent": config.execution_intent,
                "graph_mode": config.graph_mode,
                "measured_phase_times": profiler.phase_times,
            }

    finished_at = _utc_now_iso()
    payload = {
        "plan_id": plan["plan_id"],
        "workload_id": workload_manifest["ids"]["workload_id"],
        "system_id": system_profile["system_id"],
        "replicate_idx": config.replicate_idx,
        "graph_mode": config.graph_mode,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "output_digest": output_digest,
        "failure_detail_json": failure_detail_json,
        "execution_source": failure_detail_json.get("execution_source", STRUCTURAL_EXECUTION_SOURCE),
        **measured,
    }
    payload["run_id"] = _build_run_id(payload)

    if status == "success":
        profile_summary = build_synthetic_profile_summary(
            payload,
            plan,
            repeat_count=repeat_count,
            system_manifest=system_manifest,
            probe=probe,
            raw_source=raw,
            measured_phase_times=profiler.phase_times,
            base_measurement=base,
            adjustment_factors=factors,
        )
        payload["profile_summary"] = profile_summary
        payload["failure_detail_json"] = {
            **payload["failure_detail_json"],
            "profile_id": profile_summary["profile_id"],
        }

    if fallback_detail:
        payload["failure_detail_json"] = {
            **payload["failure_detail_json"],
            "real_executor_fallback": fallback_detail,
        }

    return {
        "execution_run": payload,
        "profile_summary": profile_summary,
        "accuracy_eval": None,
        "linked_assets": [],
    }


def execute_plan_candidate_bundle(
    workload_manifest: dict[str, Any],
    plan: dict[str, Any],
    *,
    system_profile: dict[str, Any] | None = None,
    system_manifest: dict[str, Any] | None = None,
    probe: dict[str, Any] | None = None,
    config: ExecutionConfig | None = None,
) -> dict[str, Any]:
    config = config or ExecutionConfig(
        objective=str(plan.get("objective") or "ttfr"),
        precision=str(plan.get("precision") or "complex128"),
        graph_mode=normalize_graph_mode(plan.get("graph_mode"), default="off"),
    )
    system_profile = system_profile or collect_system_profile()

    if config.execution_intent == "optional_real":
        bundle = _execute_structural_plan_candidate_bundle(
            workload_manifest,
            plan,
            system_profile=system_profile,
            system_manifest=system_manifest,
            probe=probe,
            config=config,
            fallback_detail={
                "fallback_code": "real_not_requested",
                "fallback_reason": "execution_intent=optional_real keeps the structural executor as the default path",
            },
        )
        return bundle

    if plan.get("mode") != "exact_tn":
        detail = {
            "reason_code": "unsupported_semantics",
            "reason": f"real cuTensorNet execution requires plan.mode='exact_tn', got {plan.get('mode')!r}",
            "execution_source": REAL_EXECUTION_SOURCE,
            "execution_version": EXECUTION_VERSION,
            "execution_intent": config.execution_intent,
            "graph_mode": config.graph_mode,
        }
        if config.execution_intent == "prefer_real":
            return _execute_structural_plan_candidate_bundle(
                workload_manifest,
                plan,
                system_profile=system_profile,
                system_manifest=system_manifest,
                probe=probe,
                config=config,
                fallback_detail={
                    "fallback_code": detail["reason_code"],
                    "fallback_reason": detail["reason"],
                },
            )
        run = _failure_run(
            plan,
            workload_manifest,
            system_profile,
            replicate_idx=config.replicate_idx,
            execution_source=REAL_EXECUTION_SOURCE,
            status="unsupported_semantics",
            detail=detail,
        )
        return {"execution_run": run, "profile_summary": None, "accuracy_eval": None, "linked_assets": []}

    try:
        real_bundle = execute_real_plan_candidate(
            workload_manifest,
            plan,
            system_profile=system_profile,
            config=config,
        )
        run = real_bundle["execution_run"]
        run["failure_detail_json"] = {
            **(run.get("failure_detail_json") or {}),
            "execution_intent": config.execution_intent,
            "graph_mode": run.get("graph_mode") or config.graph_mode,
        }
        return {
            **real_bundle,
            "linked_assets": [],
        }
    except RealExecutionError as exc:
        detail = {
            "reason_code": exc.code,
            "reason": exc.message,
            "execution_source": REAL_EXECUTION_SOURCE,
            "execution_version": EXECUTION_VERSION,
            "execution_intent": config.execution_intent,
            "graph_mode": config.graph_mode,
        }
        if config.execution_intent == "prefer_real" and exc.recoverable:
            return _execute_structural_plan_candidate_bundle(
                workload_manifest,
                plan,
                system_profile=system_profile,
                system_manifest=system_manifest,
                probe=probe,
                config=config,
                fallback_detail={
                    "fallback_code": exc.code,
                    "fallback_reason": exc.message,
                },
            )
        run = _failure_run(
            plan,
            workload_manifest,
            system_profile,
            replicate_idx=config.replicate_idx,
            execution_source=REAL_EXECUTION_SOURCE,
            status=exc.status,
            detail=detail,
        )
        return {"execution_run": run, "profile_summary": None, "accuracy_eval": None, "linked_assets": []}
    except Exception as exc:
        detail = {
            "reason_code": "runtime_error",
            "reason": str(exc),
            "execution_source": REAL_EXECUTION_SOURCE,
            "execution_version": EXECUTION_VERSION,
            "execution_intent": config.execution_intent,
            "graph_mode": config.graph_mode,
        }
        run = _failure_run(
            plan,
            workload_manifest,
            system_profile,
            replicate_idx=config.replicate_idx,
            execution_source=REAL_EXECUTION_SOURCE,
            status="runtime_error",
            detail=detail,
        )
        return {"execution_run": run, "profile_summary": None, "accuracy_eval": None, "linked_assets": []}


def execute_plan_candidate(
    workload_manifest: dict[str, Any],
    plan: dict[str, Any],
    *,
    system_profile: dict[str, Any] | None = None,
    system_manifest: dict[str, Any] | None = None,
    probe: dict[str, Any] | None = None,
    config: ExecutionConfig | None = None,
) -> dict[str, Any]:
    return execute_plan_candidate_bundle(
        workload_manifest,
        plan,
        system_profile=system_profile,
        system_manifest=system_manifest,
        probe=probe,
        config=config,
    )["execution_run"]


def _load_plan_override(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        if isinstance(payload.get("selected_plan"), dict):
            return dict(payload["selected_plan"])
        if isinstance(payload.get("plan"), dict):
            return dict(payload["plan"])
        return dict(payload)
    raise ExecutionError(f"Plan override at {path} must decode to a JSON object")


def _normalize_plan_override(plan: dict[str, Any], workload_manifest: dict[str, Any], *, objective: str) -> dict[str, Any]:
    normalized = dict(plan)
    normalized.setdefault(
        "plan_id",
        "plan_" + sha256_text(
            canonical_json(
                {
                    "workload_id": workload_manifest["ids"]["workload_id"],
                    "objective": objective,
                    "plan": normalized,
                }
            )
        )[:16],
    )
    normalized.setdefault("project", "tnep")
    normalized.setdefault("planner_version", "aqs.plan_override.v1")
    normalized.setdefault("objective", objective)
    normalized.setdefault("mode", "exact_tn")
    normalized.setdefault("precision", "complex128")
    normalized.setdefault("feasibility_label", "feasible")
    normalized.setdefault("explanation_json", [{"kind": "plan_override", "message": "explicit plan override supplied via CLI"}])
    normalized.setdefault("parent_probe_ids", [])
    return normalized


def execute_selected_plan(
    workload_manifest_path: str,
    system_manifest_path: str,
    *,
    plan_rank: int = 1,
    objective: str = "ttfr",
    probe_strategy: str = "structural_real",
    planner_budget: str = "balanced",
    allow_distributed: bool = True,
    max_candidates: int | None = None,
    measurement_repeats: int = 3,
    ttfr_repeats: int = 1,
    execution_intent: str = "optional_real",
    replicate_idx: int = 0,
    plan_json_path: str | None = None,
    plan_bundle_path: str | None = None,
    graph_mode: str | None = None,
) -> dict[str, Any]:
    if plan_json_path and plan_bundle_path:
        raise ExecutionError("Plan override JSON and reusable plan bundle are mutually exclusive")

    driver_timing: dict[str, float] = {}

    def record_timing(name: str, start: float) -> None:
        driver_timing[name] = round(max(time.perf_counter() - start, 0.0), 9)

    total_start = time.perf_counter()

    start = time.perf_counter()
    manifest = load_yaml(workload_manifest_path)
    record_timing("load_manifest_s", start)

    start = time.perf_counter()
    system_manifest = load_system_manifest(system_manifest_path)
    record_timing("load_system_manifest_s", start)

    start = time.perf_counter()
    system_profile = collect_system_profile()
    record_timing("collect_system_profile_s", start)

    start = time.perf_counter()
    repo_metadata = capture_repo_metadata()
    record_timing("capture_repo_metadata_s", start)

    plan_bundle_provenance: dict[str, Any] = {
        "requested": bool(plan_bundle_path),
        "bundle_path": _normalized_path(plan_bundle_path) if plan_bundle_path else None,
        "cache_status": "disabled",
        "cache_reason": "plan bundle reuse was not requested",
        "write_status": "disabled",
        "write_reason": "plan bundle reuse was not requested",
        "bundle_id": None,
        "compatibility": None,
    }

    bundle_scope = _build_plan_bundle_scope(
        workload_manifest_path,
        system_manifest_path,
        manifest,
        system_manifest,
        system_profile,
        objective=objective,
        probe_strategy=probe_strategy,
        planner_budget=planner_budget,
        allow_distributed=allow_distributed,
        max_candidates=max_candidates,
    )

    candidates: list[dict[str, Any]] = []
    chosen: dict[str, Any] | None = None
    ir = None
    features = None
    probe = None
    selected_by = "plan_rank"
    if plan_json_path:
        driver_timing.setdefault("plan_bundle_lookup_s", 0.0)
        driver_timing.setdefault("candidate_generation_s", 0.0)
        driver_timing.setdefault("selection_s", 0.0)

        start = time.perf_counter()
        ir = normalize_workload_manifest(manifest)
        record_timing("normalize_manifest_s", start)

        start = time.perf_counter()
        features = extract_feature_snapshot(manifest, ir)
        record_timing("extract_features_s", start)

        start = time.perf_counter()
        probe = run_exact_tn_probe(manifest, ProbeConfig(objective=objective, probe_strategy=probe_strategy))
        record_timing("probe_s", start)

        chosen = _normalize_plan_override(_load_plan_override(plan_json_path), manifest, objective=objective)
        selected_by = "plan_override"
    elif plan_bundle_path:
        lookup_start = time.perf_counter()
        bundle_path = Path(plan_bundle_path)
        if bundle_path.exists():
            bundle_payload = _load_plan_bundle(bundle_path)
            compatibility = _assess_plan_bundle_compatibility(bundle_payload, bundle_scope)
            plan_bundle_provenance["bundle_id"] = compatibility["bundle_id"]
            plan_bundle_provenance["compatibility"] = compatibility
            if compatibility["compatible"]:
                chosen = _normalize_plan_override(bundle_payload["selected_plan"], manifest, objective=objective)
                selected_by = "plan_bundle_reuse"
                plan_bundle_provenance["cache_status"] = "hit"
                plan_bundle_provenance["cache_reason"] = compatibility["reason"]
                plan_bundle_provenance["write_status"] = "skipped_hit"
                plan_bundle_provenance["write_reason"] = "existing compatible bundle was reused without rewriting"
            else:
                plan_bundle_provenance["cache_status"] = "rejected"
                plan_bundle_provenance["cache_reason"] = compatibility["reason"]
                plan_bundle_provenance["write_status"] = "skipped_rejected"
                plan_bundle_provenance["write_reason"] = "existing bundle was incompatible and was left untouched"
        else:
            plan_bundle_provenance["cache_status"] = "miss"
            plan_bundle_provenance["cache_reason"] = "bundle file was not present, so the planner selected a fresh plan"
            plan_bundle_provenance["write_status"] = "pending"
            plan_bundle_provenance["write_reason"] = "fresh planning path will write a reusable bundle after a successful run"
        record_timing("plan_bundle_lookup_s", lookup_start)

    if chosen is None:
        start = time.perf_counter()
        ir = normalize_workload_manifest(manifest)
        record_timing("normalize_manifest_s", start)

        start = time.perf_counter()
        features = extract_feature_snapshot(manifest, ir)
        record_timing("extract_features_s", start)

        start = time.perf_counter()
        probe = run_exact_tn_probe(manifest, ProbeConfig(objective=objective, probe_strategy=probe_strategy))
        record_timing("probe_s", start)

        start = time.perf_counter()
        candidates = generate_plan_candidates(
            manifest,
            features,
            probe,
            system_manifest,
            config=PlanConfig(
                objective=objective,
                planner_budget=planner_budget,
                allow_distributed=allow_distributed,
                max_candidates=max_candidates,
            ),
        )
        record_timing("candidate_generation_s", start)

        selection_start = time.perf_counter()
        chosen = next((candidate for candidate in candidates if int(candidate.get("recommendation_rank", 9999)) == plan_rank), None)
        if chosen is None:
            chosen = select_top_plan(candidates, objective=objective)
            selected_by = "planner_top_pick"
        if chosen is None:
            raise ExecutionError("No plan candidate available for execution")
        record_timing("selection_s", selection_start)
    else:
        driver_timing.setdefault("normalize_manifest_s", 0.0)
        driver_timing.setdefault("extract_features_s", 0.0)
        driver_timing.setdefault("probe_s", 0.0)
        driver_timing.setdefault("candidate_generation_s", 0.0)
        driver_timing.setdefault("selection_s", 0.0)
        driver_timing.setdefault("plan_bundle_lookup_s", 0.0)
    resolved_graph_mode = normalize_graph_mode(graph_mode if graph_mode is not None else chosen.get("graph_mode"), default="off")
    execution_start = time.perf_counter()
    bundle = execute_plan_candidate_bundle(
        manifest,
        chosen,
        system_profile=system_profile,
        system_manifest=system_manifest,
        probe=probe,
        config=ExecutionConfig(
            objective=objective,
            precision=str(chosen.get("precision") or "complex128"),
            probe_strategy=probe_strategy,
            measurement_repeats=measurement_repeats,
            ttfr_repeats=ttfr_repeats,
            execution_intent=execution_intent,
            replicate_idx=replicate_idx,
            graph_mode=resolved_graph_mode,
        ),
    )
    record_timing("execute_plan_bundle_s", execution_start)

    if plan_bundle_path and plan_bundle_provenance["cache_status"] == "miss" and bundle["execution_run"].get("status") == "success":
        bundle_payload = _build_plan_bundle_payload(
            scope=bundle_scope,
            selected_plan=chosen,
            repo_metadata=repo_metadata,
            selection_source=selected_by,
            plan_rank=plan_rank,
            candidate_count=len(candidates),
        )
        write_start = time.perf_counter()
        _write_plan_bundle(plan_bundle_path, bundle_payload)
        record_timing("plan_bundle_write_s", write_start)
        plan_bundle_provenance["bundle_id"] = bundle_payload["bundle_id"]
        plan_bundle_provenance["write_status"] = "written"
        plan_bundle_provenance["write_reason"] = "freshly selected plan was serialized into a reusable bundle"
    else:
        driver_timing.setdefault("plan_bundle_write_s", 0.0)
        if plan_bundle_path and plan_bundle_provenance["cache_status"] == "miss":
            plan_bundle_provenance["write_status"] = "skipped_no_success"
            plan_bundle_provenance["write_reason"] = "execution did not succeed, so no reusable bundle was written"

    total_s = round(max(time.perf_counter() - total_start, 0.0), 9)
    driver_timing["total_s"] = total_s
    driver_timing["pre_execution_s"] = round(
        max(
            total_s
            - float(driver_timing.get("execute_plan_bundle_s") or 0.0)
            - float(driver_timing.get("plan_bundle_write_s") or 0.0),
            0.0,
        ),
        9,
    )
    outer_driver_overhead_s = round(
        max(total_s - float(bundle["execution_run"].get("wall_s") or 0.0), 0.0),
        9,
    )
    return {
        "workload_id": manifest["ids"]["workload_id"],
        "family_id": manifest["family_id"],
        "repeat_count_hint": manifest.get("repeat_count_hint", 1),
        "system_name": system_manifest["system_name"],
        "system_manifest": system_manifest,
        "repo_metadata": repo_metadata,
        "probe": probe,
        "selected_plan": chosen,
        "selection_source": selected_by,
        "plan_override_path": str(plan_json_path).replace("\\", "/") if plan_json_path else None,
        "plan_bundle_path": _normalized_path(plan_bundle_path) if plan_bundle_path else None,
        "plan_bundle_provenance": plan_bundle_provenance,
        "driver_timing_json": driver_timing,
        "driver_total_s": total_s,
        "outer_driver_overhead_s": outer_driver_overhead_s,
        "profile_summary": bundle.get("profile_summary"),
        "accuracy_eval": bundle.get("accuracy_eval"),
        "execution_run": bundle["execution_run"],
        "linked_assets": bundle.get("linked_assets", []),
        "candidate_count": len(candidates),
    }


__all__ = [
    "EXECUTION_VERSION",
    "STRUCTURAL_EXECUTION_SOURCE",
    "ExecutionConfig",
    "ExecutionError",
    "execute_plan_candidate",
    "execute_plan_candidate_bundle",
    "execute_selected_plan",
]
