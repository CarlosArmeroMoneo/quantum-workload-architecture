from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import default_schema_path
from .utils import canonical_json, sha256_file, sha256_text


def _require_duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError(
            "The DuckDB Python package is required for this command. Install with `pip install duckdb`."
        ) from exc
    return duckdb


def apply_schema(db_path: str | Path, schema_path: str | Path | None = None, schema_version: str = "aqs_schema_v0") -> Path:
    duckdb = _require_duckdb()
    db_path = Path(db_path)
    schema_path = Path(schema_path) if schema_path else default_schema_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    sql_text = schema_path.read_text(encoding="utf-8")
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(sql_text)
        conn.execute(
            "DELETE FROM meta.schema_registry WHERE schema_version = ?",
            [schema_version],
        )
        conn.execute(
            "INSERT INTO meta.schema_registry(schema_version, notes) VALUES (?, ?)",
            [schema_version, f"Applied from {schema_path}"]
        )
    finally:
        conn.close()
    return db_path


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True)


def _replace_row(conn: Any, table: str, key_col: str, row: dict[str, Any]) -> None:
    conn.execute(f"DELETE FROM {table} WHERE {key_col} = ?", [row[key_col]])
    cols = list(row.keys())
    placeholders = ", ".join(["?" for _ in cols])
    conn.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
        [row[col] for col in cols],
    )


def insert_system_profile(db_path: str | Path, profile: dict[str, Any]) -> None:
    duckdb = _require_duckdb()
    db_path = Path(db_path)
    conn = duckdb.connect(str(db_path))
    row = {
        "system_id": profile["system_id"],
        "hostname_hash": profile.get("hostname_hash"),
        "node_label": profile.get("node_label"),
        "gpu_model": profile.get("gpu_model"),
        "gpu_count": profile.get("gpu_count", 0),
        "gpu_mem_gb": profile.get("gpu_mem_gb"),
        "gpu_present": bool(profile.get("gpu_present", bool(profile.get("gpu_count", 0)))),
        "cupy_present": bool(profile.get("cupy_present", False)),
        "cuquantum_present": bool(profile.get("cuquantum_present", False)),
        "qiskit_present": bool(profile.get("qiskit_present", False)),
        "nsys_present": bool(profile.get("nsys_present", False)),
        "ncu_present": bool(profile.get("ncu_present", False)),
        "cpu_model": profile.get("cpu_model"),
        "cpu_sockets": profile.get("cpu_sockets"),
        "cpu_cores_logical": profile.get("cpu_cores_logical"),
        "ram_gb": profile.get("ram_gb"),
        "driver_version": profile.get("driver_version"),
        "cuda_version": profile.get("cuda_version"),
        "cuquantum_sdk_version": profile.get("cuquantum_sdk_version"),
        "cuquantum_python_version": profile.get("cuquantum_python_version"),
        "cudaq_version": profile.get("cudaq_version"),
        "appliance_tag": profile.get("appliance_tag"),
        "nsight_systems_version": profile.get("nsight_systems_version"),
        "nsight_compute_version": profile.get("nsight_compute_version"),
        "mpi_impl": profile.get("mpi_impl"),
        "os_release": profile.get("os_release"),
        "container_runtime": profile.get("container_runtime"),
        "notes": profile.get("notes"),
    }
    try:
        _replace_row(conn, "meta.system_profile", "system_id", row)
    finally:
        conn.close()


def insert_workload_and_ir(db_path: str | Path, manifest: dict[str, Any], normalized_ir: dict[str, Any]) -> None:
    duckdb = _require_duckdb()
    conn = duckdb.connect(str(Path(db_path)))
    workload_id = manifest["ids"]["workload_id"]
    try:
        workload_row = {
            "workload_id": workload_id,
            "dataset_id": manifest.get("dataset_id"),
            "family_id": manifest["family_id"],
            "family_version": manifest["family_version"],
            "source_format": manifest["source_format"],
            "semantic_target": manifest["semantic_target"],
            "generator_name": manifest["generator_name"],
            "generator_version": manifest["generator_version"],
            "seed": manifest.get("seed"),
            "parameter_json": _json(manifest["parameters"]),
            "repeat_count_hint": manifest["repeat_count_hint"],
            "reference_tier": manifest["reference_tier"],
            "split_tag": manifest["split_tag"],
            "source_hash": manifest["ids"]["source_hash"],
            "source_descriptor_json": _json(manifest.get("source")),
        }
        _replace_row(conn, "corpus.workload_spec", "workload_id", workload_row)
        ir_row = {
            "workload_id": workload_id,
            "schema_version": normalized_ir["schema_version"],
            "n_qubits": normalized_ir["n_qubits"],
            "depth": normalized_ir["depth"],
            "moments": normalized_ir["moments"],
            "gate_hist_json": _json(normalized_ir["gate_hist_json"]),
            "two_qubit_density": normalized_ir["two_qubit_density"],
            "non_clifford_fraction": normalized_ir["non_clifford_fraction"],
            "clifford_valid": normalized_ir["clifford_valid"],
            "measurement_count": normalized_ir["measurement_count"],
            "reset_count": normalized_ir["reset_count"],
            "noise_json": _json(normalized_ir.get("noise_json")),
            "observable_json": _json(normalized_ir.get("observable_json")),
            "execution_target_json": _json(normalized_ir.get("execution_target_json")),
            "interaction_graph_json": _json(normalized_ir.get("interaction_graph_json")),
            "source_summary_json": _json(normalized_ir.get("source_summary_json")),
            "ir_hash": normalized_ir["ir_hash"],
        }
        _replace_row(conn, "corpus.normalized_ir", "workload_id", ir_row)
    finally:
        conn.close()


def insert_feature_snapshot(db_path: str | Path, feature_snapshot: dict[str, Any]) -> None:
    duckdb = _require_duckdb()
    conn = duckdb.connect(str(Path(db_path)))
    try:
        row = {
            "feature_id": feature_snapshot["feature_id"],
            "workload_id": feature_snapshot["workload_id"],
            "extractor_version": feature_snapshot["extractor_version"],
            "static_features_json": _json(feature_snapshot["static_features"]),
            "graph_features_json": _json(feature_snapshot["graph_features"]),
            "statevec_mem_est_fp32_bytes": feature_snapshot["statevec_mem_est_fp32_bytes"],
            "statevec_mem_est_fp64_bytes": feature_snapshot["statevec_mem_est_fp64_bytes"],
            "family_label": feature_snapshot["family_label"],
        }
        _replace_row(conn, "features.feature_snapshot", "feature_id", row)
    finally:
        conn.close()


def insert_probe_observation(db_path: str | Path, workload_id: str, system_id: str | None, probe: dict[str, Any], project: str = "tnep") -> None:
    duckdb = _require_duckdb()
    conn = duckdb.connect(str(Path(db_path)))
    try:
        row = {
            "probe_id": probe["probe_id"],
            "workload_id": workload_id,
            "system_id": system_id,
            "project": project,
            "probe_kind": probe["probe_kind"],
            "mode": probe["mode"],
            "objective": probe.get("objective"),
            "precision": probe.get("precision"),
            "workspace_gb": probe.get("workspace_gb"),
            "cache_workspace_gb": probe.get("cache_workspace_gb"),
            "hyper_samples": probe.get("hyper_samples"),
            "autotune": probe.get("autotune"),
            "reuse_cache": probe.get("reuse_cache"),
            "mpi_ranks": probe.get("mpi_ranks"),
            "gpu_arch_target": probe.get("gpu_arch_target"),
            "predicted_peak_gb": probe.get("predicted_peak_gb"),
            "predicted_error": probe.get("predicted_error"),
            "optimizer_cost": probe.get("optimizer_cost"),
            "largest_intermediate": probe.get("largest_intermediate"),
            "num_slices": probe.get("num_slices"),
            "raw_info_json": _json(probe.get("raw_info_json")),
            "status": probe["status"],
        }
        _replace_row(conn, "planning.probe_observation", "probe_id", row)
    finally:
        conn.close()


def insert_plan_candidate(db_path: str | Path, workload_id: str, candidate: dict[str, Any]) -> None:
    duckdb = _require_duckdb()
    conn = duckdb.connect(str(Path(db_path)))
    try:
        row = {
            "plan_id": candidate["plan_id"],
            "workload_id": workload_id,
            "project": candidate.get("project", "tnep"),
            "planner_version": candidate["planner_version"],
            "objective": candidate["objective"],
            "mode": candidate["mode"],
            "precision": candidate.get("precision"),
            "workspace_gb": candidate.get("workspace_gb"),
            "cache_workspace_gb": candidate.get("cache_workspace_gb"),
            "hyper_samples": candidate.get("hyper_samples"),
            "autotune": candidate.get("autotune"),
            "reuse_cache": candidate.get("reuse_cache"),
            "mpi_ranks": candidate.get("mpi_ranks"),
            "gpu_arch_target": candidate.get("gpu_arch_target"),
            "max_error": candidate.get("max_error"),
            "predicted_ttfr_s": candidate.get("predicted_ttfr_s"),
            "predicted_iter_ms": candidate.get("predicted_iter_ms"),
            "predicted_peak_gb": candidate.get("predicted_peak_gb"),
            "predicted_error": candidate.get("predicted_error"),
            "feasibility_label": candidate.get("feasibility_label", "uncertain"),
            "explanation_json": _json(candidate.get("explanation_json", [])),
            "parent_probe_ids": _json(candidate.get("parent_probe_ids", [])),
        }
        _replace_row(conn, "planning.plan_candidate", "plan_id", row)
    finally:
        conn.close()


def insert_validation_run(db_path: str | Path, summary: dict[str, Any], project: str = "tnep", evaluation_source: str = "surrogate_oracle") -> None:
    duckdb = _require_duckdb()
    conn = duckdb.connect(str(Path(db_path)))
    try:
        row = {
            "validation_run_id": summary["validation_run_id"],
            "project": project,
            "planner_version": summary.get("planner_version", "unknown"),
            "manifest_path": summary.get("benchmark_manifest"),
            "objective": summary["objective"],
            "evaluation_source": evaluation_source,
            "workload_count": summary.get("workload_count", 0),
            "heldout_workload_count": summary.get("heldout_workload_count", 0),
            "top1_accuracy": summary.get("top1_accuracy"),
            "mean_regret": summary.get("mean_regret"),
            "heldout_mean_regret": summary.get("heldout_mean_regret"),
            "summary_json": _json(summary),
        }
        _replace_row(conn, "planning.validation_run", "validation_run_id", row)
    finally:
        conn.close()


def insert_plan_evaluation(db_path: str | Path, evaluation: dict[str, Any], validation_run_id: str, evaluation_source: str = "surrogate_oracle") -> None:
    duckdb = _require_duckdb()
    conn = duckdb.connect(str(Path(db_path)))
    try:
        eval_id = "eval_" + sha256_text(canonical_json({
            "validation_run_id": validation_run_id,
            "plan_id": evaluation["plan_id"],
            "workload_id": evaluation["workload_id"],
            "objective": evaluation["objective"],
        }))[:16]
        row = {
            "evaluation_id": eval_id,
            "validation_run_id": validation_run_id,
            "plan_id": evaluation["plan_id"],
            "workload_id": evaluation["workload_id"],
            "evaluation_source": evaluation_source,
            "split_tag": evaluation.get("split_tag"),
            "family_id": evaluation.get("family_id"),
            "objective": evaluation["objective"],
            "status": evaluation.get("status", "invalid"),
            "feasible": bool(evaluation.get("feasible", False)),
            "observed_ttfr_s": evaluation.get("observed_ttfr_s"),
            "observed_iter_ms": evaluation.get("observed_iter_ms"),
            "observed_peak_gb": evaluation.get("observed_peak_gb"),
            "observed_gpu_seconds": evaluation.get("observed_gpu_seconds"),
            "observed_error": evaluation.get("observed_error"),
            "oracle_rank": evaluation.get("oracle_rank"),
            "regret": evaluation.get("regret"),
            "normalized_regret": evaluation.get("normalized_regret"),
            "details_json": _json(evaluation.get("details_json", {})),
        }
        _replace_row(conn, "planning.plan_evaluation", "evaluation_id", row)
    finally:
        conn.close()



def insert_execution_run(db_path: str | Path, run: dict[str, Any]) -> None:
    duckdb = _require_duckdb()
    conn = duckdb.connect(str(Path(db_path)))
    try:
        row = {
            "run_id": run["run_id"],
            "plan_id": run["plan_id"],
            "workload_id": run["workload_id"],
            "system_id": run["system_id"],
            "replicate_idx": int(run.get("replicate_idx", 0)),
            "status": run["status"],
            "started_at": run.get("started_at"),
            "finished_at": run.get("finished_at"),
            "wall_s": run.get("wall_s"),
            "ttfr_s": run.get("ttfr_s"),
            "steady_iter_ms": run.get("steady_iter_ms"),
            "gpu_seconds": run.get("gpu_seconds"),
            "peak_mem_gb": run.get("peak_mem_gb"),
            "peak_workspace_gb": run.get("peak_workspace_gb"),
            "output_digest": run.get("output_digest"),
            "execution_source": run.get("execution_source"),
            "failure_detail_json": _json({
                **(run.get("failure_detail_json") or {}),
                "execution_source": run.get("execution_source"),
            }),
        }
        _replace_row(conn, "execution.execution_run", "run_id", row)
    finally:
        conn.close()


def insert_accuracy_eval(db_path: str | Path, evaluation: dict[str, Any]) -> None:
    duckdb = _require_duckdb()
    conn = duckdb.connect(str(Path(db_path)))
    try:
        row = {
            "eval_id": evaluation["eval_id"],
            "run_id": evaluation["run_id"],
            "reference_run_id": evaluation.get("reference_run_id"),
            "metric_name": evaluation["metric_name"],
            "metric_value": evaluation["metric_value"],
            "threshold": evaluation.get("threshold"),
            "pass": evaluation.get("pass"),
            "evaluation_version": evaluation.get("evaluation_version", "unknown"),
        }
        _replace_row(conn, "execution.accuracy_eval", "eval_id", row)
    finally:
        conn.close()


def insert_profile_summary(db_path: str | Path, profile: dict[str, Any]) -> None:
    duckdb = _require_duckdb()
    conn = duckdb.connect(str(Path(db_path)))
    try:
        row = {
            "profile_id": profile["profile_id"],
            "run_id": profile["run_id"],
            "profiler_kind": profile.get("profiler_kind", "synthetic"),
            "nvtx_phase_times_json": _json(profile.get("nvtx_phase_times_json") or {}),
            "top_kernels_json": _json(profile.get("top_kernels_json") or []),
            "dram_util_pct": profile.get("dram_util_pct"),
            "sm_util_pct": profile.get("sm_util_pct"),
            "occupancy_pct": profile.get("occupancy_pct"),
            "comm_time_pct": profile.get("comm_time_pct"),
            "nsys_asset_id": profile.get("nsys_asset_id"),
            "ncu_asset_id": profile.get("ncu_asset_id"),
            "profile_version": profile.get("profile_version", "unknown"),
            "derived_signals_json": _json(profile.get("derived_signals_json") or {}),
        }
        _replace_row(conn, "profiling.profile_summary", "profile_id", row)
    finally:
        conn.close()


def insert_asset_index(
    db_path: str | Path,
    *,
    asset_id: str,
    asset_type: str,
    relative_path: str,
    sha256: str | None,
    size_bytes: int | None,
    tracked_in_git: bool = False,
    notes: str | None = None,
) -> None:
    duckdb = _require_duckdb()
    conn = duckdb.connect(str(Path(db_path)))
    try:
        row = {
            "asset_id": asset_id,
            "asset_type": asset_type,
            "relative_path": relative_path,
            "sha256": sha256,
            "size_bytes": size_bytes,
            "tracked_in_git": bool(tracked_in_git),
            "notes": notes,
        }
        _replace_row(conn, "profiling.asset_index", "asset_id", row)
    finally:
        conn.close()


def upsert_asset_file(
    db_path: str | Path,
    asset_path: str | Path,
    *,
    asset_type: str,
    asset_id: str | None = None,
    tracked_in_git: bool = False,
    notes: str | None = None,
) -> dict[str, Any]:
    path = Path(asset_path)
    relative_path = str(path).replace("\\", "/")
    sha256 = sha256_file(path) if path.exists() else None
    size_bytes = path.stat().st_size if path.exists() else None
    resolved_asset_id = asset_id or (
        "asset_"
        + sha256_text(
            canonical_json(
                {
                    "asset_type": asset_type,
                    "relative_path": relative_path,
                    "sha256": sha256,
                    "size_bytes": size_bytes,
                }
            )
        )[:16]
    )
    payload: dict[str, Any] = {
        "asset_id": resolved_asset_id,
        "asset_type": asset_type,
        "relative_path": relative_path,
        "sha256": sha256,
        "size_bytes": size_bytes,
    }
    insert_asset_index(
        db_path,
        asset_id=resolved_asset_id,
        asset_type=asset_type,
        relative_path=relative_path,
        sha256=sha256,
        size_bytes=size_bytes,
        tracked_in_git=tracked_in_git,
        notes=notes,
    )
    return payload


def link_run_asset(db_path: str | Path, run_id: str, asset_role: str, asset_id: str) -> None:
    duckdb = _require_duckdb()
    conn = duckdb.connect(str(Path(db_path)))
    try:
        conn.execute(
            "DELETE FROM execution.run_asset WHERE run_id = ? AND asset_role = ? AND asset_id = ?",
            [run_id, asset_role, asset_id],
        )
        conn.execute(
            "INSERT INTO execution.run_asset (run_id, asset_role, asset_id) VALUES (?, ?, ?)",
            [run_id, asset_role, asset_id],
        )
    finally:
        conn.close()


def link_profile_asset(db_path: str | Path, profile_id: str, asset_role: str, asset_id: str) -> None:
    duckdb = _require_duckdb()
    conn = duckdb.connect(str(Path(db_path)))
    try:
        conn.execute(
            "DELETE FROM profiling.profile_asset WHERE profile_id = ? AND asset_role = ? AND asset_id = ?",
            [profile_id, asset_role, asset_id],
        )
        conn.execute(
            "INSERT INTO profiling.profile_asset (profile_id, asset_role, asset_id) VALUES (?, ?, ?)",
            [profile_id, asset_role, asset_id],
        )
    finally:
        conn.close()


def insert_profiler_attempt(db_path: str | Path, attempt: dict[str, Any]) -> None:
    duckdb = _require_duckdb()
    conn = duckdb.connect(str(Path(db_path)))
    try:
        row = {
            "attempt_id": attempt["attempt_id"],
            "run_id": attempt.get("run_id"),
            "tool_kind": attempt["tool_kind"],
            "attempt_role": attempt.get("attempt_role", "profile"),
            "tool_version": attempt.get("tool_version"),
            "importer_version": attempt.get("importer_version"),
            "command_json": _json(attempt.get("command") or []),
            "exit_code": attempt.get("exit_code"),
            "stdout_digest": attempt.get("stdout_digest"),
            "stderr_digest": attempt.get("stderr_digest"),
            "stderr_excerpt": attempt.get("stderr_excerpt"),
            "failure_class": attempt.get("failure_class"),
            "usability_state": attempt.get("usability_state", "not_started"),
            "state_json": _json(attempt.get("state_json") or {}),
            "artifact_presence_json": _json(attempt.get("artifact_presence_json") or {}),
            "remediation_json": _json(attempt.get("remediation") or []),
            "notes": attempt.get("notes"),
            "attempt_asset_id": attempt.get("attempt_asset_id"),
        }
        _replace_row(conn, "profiling.profiler_attempt", "attempt_id", row)
    finally:
        conn.close()


def insert_bottleneck_case(db_path: str | Path, case: dict[str, Any]) -> None:
    duckdb = _require_duckdb()
    conn = duckdb.connect(str(Path(db_path)))
    try:
        row = {
            "case_id": case["case_id"],
            "run_id": case["run_id"],
            "bottleneck_family": case["bottleneck_family"],
            "nomination_reason_json": _json(case.get("nomination_reason_json") or {}),
            "supporting_profile_ids": _json(case.get("supporting_profile_ids") or []),
            "accepted_for_study": bool(case.get("accepted_for_study", False)),
            "severity_score": case.get("severity_score"),
            "nomination_source": case.get("nomination_source", "synthetic_profile_analysis"),
            "counterfactual_hypotheses_json": _json(case.get("counterfactual_knobs") or []),
        }
        _replace_row(conn, "arch.bottleneck_case", "case_id", row)
    finally:
        conn.close()
