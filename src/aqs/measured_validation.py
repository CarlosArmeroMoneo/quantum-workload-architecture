from __future__ import annotations

from pathlib import Path
from typing import Any

from .db import (
    insert_accuracy_eval,
    insert_execution_run,
    insert_feature_snapshot,
    insert_plan_candidate,
    insert_plan_evaluation,
    insert_probe_observation,
    insert_profile_summary,
    insert_system_profile,
    insert_validation_run,
    insert_workload_and_ir,
)
from .doctor import collect_system_profile
from .execution import ExecutionConfig, execute_plan_candidate_bundle
from .features import extract_feature_snapshot
from .io import dump_json
from .manifest import load_yaml, validate_benchmark_manifest, validate_workload_manifest
from .normalize import normalize_workload_manifest
from .paths import repo_root
from .planner import PlanConfig, generate_plan_candidates, load_system_manifest, select_top_plan
from .tnprobe import ProbeConfig, run_exact_tn_probe
from .utils import canonical_json, sha256_text
from .validation_confidence import annotate_validation_results, write_confidence_summary_artifacts

MEASURED_VALIDATION_VERSION = "aqs.tnep_measured_validation.v1"


class MeasuredValidationError(RuntimeError):
    pass


def _resolve_repo_glob(glob_expr: str) -> list[Path]:
    root = repo_root()
    paths = sorted(root.glob(glob_expr))
    return [path for path in paths if path.is_file()]


def _float_or_inf(value: Any) -> float:
    if value is None:
        return float("inf")
    return float(value)


def _objective_value(objective: str, run: dict[str, Any]) -> float:
    if objective == "steady_state":
        return _float_or_inf(run.get("steady_iter_ms"))
    if objective == "gpu_seconds":
        return _float_or_inf(run.get("gpu_seconds"))
    return _float_or_inf(run.get("ttfr_s"))


def _build_summary_warnings(results: list[dict[str, Any]]) -> list[str]:
    heldout_count = sum(1 for row in results if row.get("split_tag") == "heldout_family")
    warnings: list[str] = []
    if heldout_count < 5:
        warnings.append(
            f"heldout_workload_count={heldout_count} is below the recommended calibration minimum of 5; "
            "treat heldout_mean_regret as descriptive only"
        )
    return warnings


def validate_measured_manifest(
    benchmark_manifest_path: str | Path,
    *,
    db_path: str | Path | None = None,
    outdir: str | Path | None = None,
) -> dict[str, object]:
    benchmark_manifest_path = Path(benchmark_manifest_path)
    benchmark = load_yaml(benchmark_manifest_path)
    errors = validate_benchmark_manifest(benchmark)
    if errors:
        raise MeasuredValidationError(f"Invalid benchmark manifest {benchmark_manifest_path}: {errors}")

    workload_paths = _resolve_repo_glob(benchmark["workload_glob"])
    if not workload_paths:
        raise MeasuredValidationError(f"No workloads matched glob {benchmark['workload_glob']!r}")

    max_workloads = benchmark.get("max_workloads")
    if isinstance(max_workloads, int):
        workload_paths = workload_paths[:max_workloads]

    system_manifest = load_system_manifest(str(repo_root() / benchmark["system_manifest"]))
    system_profile = collect_system_profile()
    outdir = Path(outdir) if outdir else repo_root() / "artifacts" / "measured_validation_runs" / benchmark["dataset_name"]
    outdir.mkdir(parents=True, exist_ok=True)

    objective = str(benchmark["objective"])
    probe_strategy = str(benchmark.get("probe_strategy") or "structural_real")
    planner_budget = str(benchmark.get("planner_budget") or "balanced")
    top_k_candidates = int(benchmark.get("top_k_candidates") or 3)
    measurement_repeats = int(benchmark.get("measurement_repeats") or 3)
    ttfr_repeats = int(benchmark.get("ttfr_repeats") or 1)
    execution_intent = str(benchmark.get("execution_intent") or "optional_real")

    results: list[dict[str, Any]] = []
    top1_hits = 0
    top1_count = 0
    regrets: list[float] = []
    heldout_regrets: list[float] = []

    if db_path:
        insert_system_profile(db_path, system_profile)

    for workload_path in workload_paths:
        manifest = load_yaml(workload_path)
        work_errors = validate_workload_manifest(manifest)
        if work_errors:
            raise MeasuredValidationError(f"Invalid workload manifest {workload_path}: {work_errors}")

        ir = normalize_workload_manifest(manifest)
        features = extract_feature_snapshot(manifest, ir)
        probe = run_exact_tn_probe(manifest, ProbeConfig(objective=objective, probe_strategy=probe_strategy))
        candidates = generate_plan_candidates(
            manifest,
            features,
            probe,
            system_manifest,
            config=PlanConfig(
                objective=objective,
                planner_budget=planner_budget,
                allow_distributed=bool(benchmark.get("allow_distributed", True)),
                max_candidates=benchmark.get("max_candidates"),
            ),
        )
        measured_candidates = [candidate for candidate in candidates if int(candidate.get("recommendation_rank", 9999)) <= top_k_candidates]
        if not measured_candidates and candidates:
            measured_candidates = [candidates[0]]

        runs = []
        for candidate in measured_candidates:
            bundle = execute_plan_candidate_bundle(
                manifest,
                candidate,
                system_profile=system_profile,
                system_manifest=system_manifest,
                probe=probe,
                config=ExecutionConfig(
                    objective=objective,
                    precision=str(candidate.get("precision") or "complex128"),
                    probe_strategy=probe_strategy,
                    measurement_repeats=measurement_repeats,
                    ttfr_repeats=ttfr_repeats,
                    execution_intent=execution_intent,
                ),
            )
            run = bundle["execution_run"]
            evaluation = {
                "plan_id": candidate["plan_id"],
                "workload_id": manifest["ids"]["workload_id"],
                "objective": objective,
                "split_tag": manifest["split_tag"],
                "family_id": manifest["family_id"],
                "status": "success" if run["status"] == "success" else "invalid",
                "feasible": run["status"] == "success",
                "observed_ttfr_s": run.get("ttfr_s"),
                "observed_iter_ms": run.get("steady_iter_ms"),
                "observed_peak_gb": run.get("peak_mem_gb"),
                "observed_gpu_seconds": run.get("gpu_seconds"),
                "observed_error": 0.0,
                "details_json": run.get("failure_detail_json", {}),
                "execution_run": run,
                "profile_summary": bundle.get("profile_summary"),
                "accuracy_eval": bundle.get("accuracy_eval"),
                "candidate": candidate,
            }
            runs.append(evaluation)

        successful = [row for row in runs if row["status"] == "success"]
        oracle_best = min(successful, key=lambda row: _objective_value(objective, row["execution_run"])) if successful else None
        selected = select_top_plan(candidates, objective=objective)
        selected_eval = next((row for row in runs if selected and row["plan_id"] == selected["plan_id"]), None)
        top1_count += 1
        if oracle_best and selected_eval and oracle_best["plan_id"] == selected_eval["plan_id"]:
            top1_hits += 1

        regret = None
        normalized_regret = None
        if oracle_best and selected_eval:
            best_value = _objective_value(objective, oracle_best["execution_run"])
            selected_value = _objective_value(objective, selected_eval["execution_run"])
            regret = round(selected_value - best_value, 6)
            normalized_regret = round(regret / max(best_value, 1e-9), 6)
            regrets.append(regret)
            if manifest["split_tag"] == "heldout_family":
                heldout_regrets.append(regret)
        elif oracle_best and not selected_eval:
            best_value = _objective_value(objective, oracle_best["execution_run"])
            regret = round(best_value, 6)
            normalized_regret = 1.0
            regrets.append(regret)
            if manifest["split_tag"] == "heldout_family":
                heldout_regrets.append(regret)

        ranked_successful = sorted(successful, key=lambda row: _objective_value(objective, row["execution_run"]))
        for idx, row in enumerate(ranked_successful, start=1):
            row["oracle_rank"] = idx
            row["regret"] = regret if selected and row["plan_id"] == selected["plan_id"] else None
            row["normalized_regret"] = normalized_regret if selected and row["plan_id"] == selected["plan_id"] else None

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
            "evaluations": runs,
        }
        results.append(summary_row)

        if db_path:
            insert_workload_and_ir(db_path, manifest, ir)
            insert_feature_snapshot(db_path, features)
            insert_probe_observation(db_path, manifest["ids"]["workload_id"], system_profile["system_id"], probe, project="tnep")
            for candidate in candidates:
                insert_plan_candidate(db_path, manifest["ids"]["workload_id"], candidate)
            for row in runs:
                insert_execution_run(db_path, row["execution_run"])
                accuracy = row.get("accuracy_eval") or {}
                for eval_row in accuracy.get("rows", []):
                    insert_accuracy_eval(db_path, eval_row)
                if row.get("profile_summary"):
                    insert_profile_summary(db_path, row["profile_summary"])

    validation_run_id = "val_" + sha256_text(canonical_json({
        "manifest": str(benchmark_manifest_path),
        "dataset_name": benchmark["dataset_name"],
        "objective": objective,
        "workload_ids": [row["workload_id"] for row in results],
        "evaluation_source": "measured",
    }))[:16]

    confidence = annotate_validation_results(results, objective=objective)

    summary_path = outdir / "summary.json"
    summary = {
        "validation_run_id": validation_run_id,
        "planner_version": MEASURED_VALIDATION_VERSION,
        "benchmark_manifest": str(benchmark_manifest_path),
        "summary_path": str(summary_path),
        "dataset_name": benchmark["dataset_name"],
        "objective": objective,
        "probe_strategy": probe_strategy,
        "planner_budget": planner_budget,
        "execution_intent": execution_intent,
        "ttfr_repeats": ttfr_repeats,
        "evaluation_source": "measured",
        "system_manifest": system_manifest,
        "workload_count": len(results),
        "heldout_workload_count": sum(1 for row in results if row["split_tag"] == "heldout_family"),
        "top1_accuracy": round(top1_hits / max(top1_count, 1), 6),
        "mean_regret": round(sum(regrets) / len(regrets), 6) if regrets else None,
        "heldout_mean_regret": round(sum(heldout_regrets) / len(heldout_regrets), 6) if heldout_regrets else None,
        "confidence_version": confidence["confidence_version"],
        "top1_within_1ms_rate": confidence["top1_within_1ms_rate"],
        "top1_within_3pct_rate": confidence["top1_within_3pct_rate"],
        "high_confidence_top1_accuracy": confidence["high_confidence_top1_accuracy"],
        "selection_confidence_counts": confidence["selection_confidence_counts"],
        "warnings": _build_summary_warnings(results),
        "results": confidence["results"],
    }
    summary.update(write_confidence_summary_artifacts(summary, outdir))
    dump_json(summary, summary_path)

    if db_path:
        insert_validation_run(db_path, summary, project="tnep", evaluation_source="measured")
        for workload in results:
            for evaluation in workload["evaluations"]:
                payload = dict(evaluation)
                payload["regret"] = workload.get("regret") if evaluation["plan_id"] == workload.get("selected_plan_id") else None
                payload["normalized_regret"] = workload.get("normalized_regret") if evaluation["plan_id"] == workload.get("selected_plan_id") else None
                insert_plan_evaluation(db_path, payload, validation_run_id, evaluation_source="measured")

    return summary


__all__ = ["MEASURED_VALIDATION_VERSION", "MeasuredValidationError", "validate_measured_manifest"]
