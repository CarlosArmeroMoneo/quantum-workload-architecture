from __future__ import annotations

from pathlib import Path
from typing import Any
import math

from .features import extract_feature_snapshot
from .io import dump_json
from .manifest import load_yaml, validate_benchmark_manifest, validate_workload_manifest
from .normalize import normalize_workload_manifest
from .paths import repo_root
from .planner import PlanConfig, generate_plan_candidates, load_system_manifest, select_top_plan
from .tnprobe import ProbeConfig, run_exact_tn_probe
from .utils import canonical_json, sha256_text
from .validation_confidence import annotate_validation_results, write_confidence_summary_artifacts

VALIDATION_VERSION = "aqs.tnep_validation.v0"


class ValidationError(RuntimeError):
    pass


def _resolve_repo_glob(glob_expr: str) -> list[Path]:
    root = repo_root()
    paths = sorted(root.glob(glob_expr))
    return [path for path in paths if path.is_file()]


def _deterministic_unit(*parts: str) -> float:
    digest = sha256_text("|".join(parts))
    raw = int(digest[:8], 16)
    return raw / 0xFFFFFFFF


def _oracle_metrics(manifest: dict[str, Any], plan: dict[str, Any], system_manifest: dict[str, Any]) -> dict[str, Any]:
    workload_id = manifest["ids"]["workload_id"]
    family = manifest["family_id"]
    split_tag = manifest["split_tag"]
    repeat_count = int(manifest.get("repeat_count_hint", 1))
    gpu_mem_gb = float(system_manifest.get("gpu_mem_gb") or 0.0)
    gpu_count = int(system_manifest.get("gpu_count") or 0)

    jitter = 0.92 + 0.22 * _deterministic_unit(workload_id, plan["template_name"], family)
    family_factor = {
        "dense_universal": 1.04,
        "qaoa_graph": 0.96,
        "trotter_1d": 0.90,
        "grid_2d_shallow": 1.16,
        "qec_clifford": 0.82,
    }.get(family, 1.0)
    holdout_penalty = 1.11 if split_tag == "heldout_family" else 1.0

    hyper = int(plan.get("hyper_samples") or 1)
    saturation = 1.0 - 0.018 * min(max(hyper - 4, 0), 16)
    if hyper <= 2:
        saturation = 1.05

    observed_ttfr = float(plan["predicted_ttfr_s"]) * jitter * family_factor * holdout_penalty
    observed_iter = float(plan["predicted_iter_ms"]) * (0.96 + 0.10 * jitter) * family_factor / max(saturation, 0.78)
    observed_peak = float(plan["predicted_peak_gb"]) * (0.98 + 0.06 * jitter)

    if bool(plan.get("autotune")) and repeat_count >= 8:
        observed_iter *= 0.94
    if bool(plan.get("reuse_cache")) and repeat_count >= 10:
        observed_iter *= 0.88
    if plan["mode"] == "exact_tn_distributed":
        ranks = max(1, int(plan.get("mpi_ranks") or 1))
        observed_ttfr *= 1.03 + 0.015 * max(ranks - 1, 0)
        observed_iter *= 0.92 + 0.06 * math.log2(ranks)
        observed_peak *= 0.93

    status = "success"
    feasible = True
    if gpu_count <= 0:
        status = "invalid"
        feasible = False
    elif gpu_mem_gb > 0 and observed_peak > 0.90 * gpu_mem_gb:
        status = "infeasible"
        feasible = False

    gpu_seconds = observed_ttfr * max(1, int(plan.get("mpi_ranks") or 1))
    if feasible and repeat_count > 1:
        gpu_seconds += ((repeat_count - 1) * observed_iter / 1000.0) * max(1, int(plan.get("mpi_ranks") or 1))

    return {
        "status": status,
        "feasible": feasible,
        "observed_ttfr_s": round(observed_ttfr, 6),
        "observed_iter_ms": round(observed_iter, 6),
        "observed_peak_gb": round(observed_peak, 6),
        "observed_gpu_seconds": round(gpu_seconds, 6),
        "observed_error": 0.0,
        "details_json": {
            "family_factor": family_factor,
            "holdout_penalty": holdout_penalty,
            "jitter": round(jitter, 6),
            "hyper_saturation": round(saturation, 6),
            "evaluation_source": "surrogate_oracle",
        },
    }


def _objective_key(objective: str, row: dict[str, Any]) -> float:
    if objective == "steady_state":
        return float(row.get("observed_iter_ms") or float("inf"))
    if objective == "gpu_seconds":
        return float(row.get("observed_gpu_seconds") or float("inf"))
    return float(row.get("observed_ttfr_s") or float("inf"))


def _build_summary_warnings(results: list[dict[str, Any]]) -> list[str]:
    heldout_count = sum(1 for row in results if row.get("split_tag") == "heldout_family")
    warnings: list[str] = []
    if heldout_count < 5:
        warnings.append(
            f"heldout_workload_count={heldout_count} is below the recommended calibration minimum of 5; "
            "treat heldout_mean_regret as descriptive only"
        )
    return warnings


def validate_planner_manifest(
    benchmark_manifest_path: str | Path,
    *,
    db_path: str | Path | None = None,
    outdir: str | Path | None = None,
) -> dict[str, Any]:
    benchmark_manifest_path = Path(benchmark_manifest_path)
    benchmark = load_yaml(benchmark_manifest_path)
    errors = validate_benchmark_manifest(benchmark)
    if errors:
        raise ValidationError(f"Invalid benchmark manifest {benchmark_manifest_path}: {errors}")

    workload_paths = _resolve_repo_glob(benchmark["workload_glob"])
    if not workload_paths:
        raise ValidationError(f"No workloads matched glob {benchmark['workload_glob']!r}")

    max_workloads = benchmark.get("max_workloads")
    if isinstance(max_workloads, int):
        workload_paths = workload_paths[:max_workloads]

    system_manifest = load_system_manifest(str(repo_root() / benchmark["system_manifest"]))
    outdir = Path(outdir) if outdir else repo_root() / "artifacts" / "validation_runs" / benchmark["dataset_name"]
    outdir.mkdir(parents=True, exist_ok=True)

    objective = str(benchmark["objective"])
    probe_strategy = str(benchmark.get("probe_strategy") or "surrogate_only")
    planner_budget = str(benchmark.get("planner_budget") or "balanced")
    plan_cfg = PlanConfig(
        objective=objective,
        planner_budget=planner_budget,
        allow_distributed=bool(benchmark.get("allow_distributed", True)),
        max_candidates=benchmark.get("max_candidates"),
    )

    per_workload: list[dict[str, Any]] = []
    top1_hits = 0
    top1_count = 0
    regrets: list[float] = []
    heldout_regrets: list[float] = []

    for workload_path in workload_paths:
        manifest = load_yaml(workload_path)
        work_errors = validate_workload_manifest(manifest)
        if work_errors:
            raise ValidationError(f"Invalid workload manifest {workload_path}: {work_errors}")

        ir = normalize_workload_manifest(manifest)
        features = extract_feature_snapshot(manifest, ir)
        probe = run_exact_tn_probe(
            manifest,
            ProbeConfig(objective=objective, probe_strategy=probe_strategy),
        )
        candidates = generate_plan_candidates(manifest, features, probe, system_manifest, config=plan_cfg)

        evaluations = []
        feasible_rows = []
        for candidate in candidates:
            metrics = _oracle_metrics(manifest, candidate, system_manifest)
            row = {
                "workload_id": manifest["ids"]["workload_id"],
                "plan_id": candidate["plan_id"],
                "objective": objective,
                "split_tag": manifest["split_tag"],
                "family_id": manifest["family_id"],
                **metrics,
            }
            evaluations.append({**candidate, **row})
            if metrics["status"] == "success":
                feasible_rows.append({**candidate, **row})

        oracle_best = min(feasible_rows, key=lambda row: _objective_key(objective, row)) if feasible_rows else None
        selected = select_top_plan(candidates, objective=objective)
        selected_eval = next((row for row in feasible_rows if selected and row["plan_id"] == selected["plan_id"]), None)

        top1_count += 1
        if oracle_best and selected_eval and oracle_best["plan_id"] == selected_eval["plan_id"]:
            top1_hits += 1

        regret = None
        normalized_regret = None
        if oracle_best and selected_eval:
            best_value = _objective_key(objective, oracle_best)
            selected_value = _objective_key(objective, selected_eval)
            regret = round(selected_value - best_value, 6)
            normalized_regret = round(regret / max(best_value, 1e-9), 6)
            regrets.append(regret)
            if manifest["split_tag"] == "heldout_family":
                heldout_regrets.append(regret)
        elif oracle_best and not selected_eval:
            selected_value = float("inf")
            best_value = _objective_key(objective, oracle_best)
            regret = round(best_value, 6)
            normalized_regret = 1.0
            regrets.append(regret)
            if manifest["split_tag"] == "heldout_family":
                heldout_regrets.append(regret)

        if oracle_best:
            ranked = sorted(feasible_rows, key=lambda row: _objective_key(objective, row))
            for idx, row in enumerate(ranked, start=1):
                row["oracle_rank"] = idx
                if row["plan_id"] == selected["plan_id"] if selected else None:
                    row["selected_by_planner"] = True

        summary_row = {
            "workload_id": manifest["ids"]["workload_id"],
            "manifest_path": str(workload_path),
            "family_id": manifest["family_id"],
            "split_tag": manifest["split_tag"],
            "repeat_count_hint": manifest.get("repeat_count_hint", 1),
            "probe_id": probe["probe_id"],
            "selected_plan_id": selected["plan_id"] if selected else None,
            "oracle_best_plan_id": oracle_best["plan_id"] if oracle_best else None,
            "regret": regret,
            "normalized_regret": normalized_regret,
            "top_candidate_mode": selected["mode"] if selected else None,
            "evaluations": evaluations,
        }
        per_workload.append(summary_row)

    validation_run_id = "val_" + sha256_text(canonical_json({
        "manifest": str(benchmark_manifest_path),
        "dataset_name": benchmark["dataset_name"],
        "objective": objective,
        "workload_ids": [row["workload_id"] for row in per_workload],
    }))[:16]

    confidence = annotate_validation_results(per_workload, objective=objective)

    summary_path = outdir / "summary.json"
    summary = {
        "validation_run_id": validation_run_id,
        "planner_version": VALIDATION_VERSION,
        "benchmark_manifest": str(benchmark_manifest_path),
        "summary_path": str(summary_path),
        "dataset_name": benchmark["dataset_name"],
        "objective": objective,
        "probe_strategy": probe_strategy,
        "planner_budget": planner_budget,
        "workload_count": len(per_workload),
        "heldout_workload_count": sum(1 for row in per_workload if row["split_tag"] == "heldout_family"),
        "top1_accuracy": round(top1_hits / max(top1_count, 1), 6),
        "mean_regret": round(sum(regrets) / len(regrets), 6) if regrets else None,
        "heldout_mean_regret": round(sum(heldout_regrets) / len(heldout_regrets), 6) if heldout_regrets else None,
        "confidence_version": confidence["confidence_version"],
        "top1_within_1ms_rate": confidence["top1_within_1ms_rate"],
        "top1_within_3pct_rate": confidence["top1_within_3pct_rate"],
        "high_confidence_top1_accuracy": confidence["high_confidence_top1_accuracy"],
        "selection_confidence_counts": confidence["selection_confidence_counts"],
        "stable_selected_miss_count": confidence["stable_selected_miss_count"],
        "selected_dominated_by_top2_count": confidence["selected_dominated_by_top2_count"],
        "anchor_candidate_count": confidence["anchor_candidate_count"],
        "anchor_candidate_workloads": confidence["anchor_candidate_workloads"],
        "warnings": _build_summary_warnings(per_workload),
        "results": confidence["results"],
    }
    summary.update(write_confidence_summary_artifacts(summary, outdir))
    dump_json(summary, summary_path)
    return summary


__all__ = ["VALIDATION_VERSION", "ValidationError", "validate_planner_manifest"]
