from __future__ import annotations

from pathlib import Path
from typing import Any

from .db import insert_feature_snapshot, insert_probe_observation, insert_system_profile, insert_workload_and_ir
from .doctor import collect_system_profile
from .features import extract_feature_snapshot
from .io import dump_json
from .manifest import load_yaml, validate_benchmark_manifest, validate_workload_manifest
from .normalize import normalize_workload_manifest
from .paths import repo_root
from .tnprobe import ProbeConfig, run_exact_tn_probe


class BenchmarkRunError(RuntimeError):
    pass


def _resolve_repo_glob(glob_expr: str) -> list[Path]:
    root = repo_root()
    paths = sorted(root.glob(glob_expr))
    return [path for path in paths if path.is_file()]


def run_benchmark_manifest(
    benchmark_manifest_path: str | Path,
    *,
    db_path: str | Path | None = None,
    outdir: str | Path | None = None,
) -> dict[str, Any]:
    benchmark_manifest_path = Path(benchmark_manifest_path)
    benchmark = load_yaml(benchmark_manifest_path)
    errors = validate_benchmark_manifest(benchmark)
    if errors:
        raise BenchmarkRunError(f"Invalid benchmark manifest {benchmark_manifest_path}: {errors}")

    workload_paths = _resolve_repo_glob(benchmark["workload_glob"])
    if not workload_paths:
        raise BenchmarkRunError(f"No workloads matched glob {benchmark['workload_glob']!r}")

    max_workloads = benchmark.get("max_workloads")
    if isinstance(max_workloads, int):
        workload_paths = workload_paths[:max_workloads]

    effective_outdir = Path(outdir) if outdir else repo_root() / "artifacts" / "benchmark_runs" / benchmark["dataset_name"]
    effective_outdir.mkdir(parents=True, exist_ok=True)

    system_profile = collect_system_profile()
    if db_path:
        insert_system_profile(db_path, system_profile)

    run_results: list[dict[str, Any]] = []
    allowed_modes = set(benchmark["allowed_modes"])
    objective = benchmark["objective"]
    probe_strategy = benchmark.get("probe_strategy", "surrogate_only")
    precision = benchmark.get("precision", "complex128")
    execution_intent = benchmark.get("execution_intent", "optional_real")

    for workload_path in workload_paths:
        manifest = load_yaml(workload_path)
        work_errors = validate_workload_manifest(manifest)
        if work_errors:
            raise BenchmarkRunError(f"Invalid workload manifest {workload_path}: {work_errors}")

        ir = normalize_workload_manifest(manifest)
        features = extract_feature_snapshot(manifest, ir)
        probe = None
        if "exact_tn" in allowed_modes:
            probe = run_exact_tn_probe(
                manifest,
                ProbeConfig(objective=objective, precision=precision, probe_strategy=probe_strategy),
            )

        run_dir = effective_outdir / manifest["ids"]["workload_id"]
        run_dir.mkdir(parents=True, exist_ok=True)
        dump_json(ir, run_dir / "normalized_ir.json")
        dump_json(features, run_dir / "features.json")
        if probe is not None:
            dump_json(probe, run_dir / "probe.json")

        if db_path:
            insert_workload_and_ir(db_path, manifest, ir)
            insert_feature_snapshot(db_path, features)
            if probe is not None:
                insert_probe_observation(
                    db_path,
                    manifest["ids"]["workload_id"],
                    system_profile["system_id"],
                    probe,
                    project=str(benchmark["project"]),
                )

        run_results.append(
            {
                "workload_id": manifest["ids"]["workload_id"],
                "manifest_path": str(workload_path),
                "normalized_ir_path": str(run_dir / "normalized_ir.json"),
                "feature_path": str(run_dir / "features.json"),
                "probe_path": str(run_dir / "probe.json") if probe is not None else None,
                "probe_status": probe.get("status") if probe else None,
                "probe_source": probe.get("raw_info_json", {}).get("probe_source") if probe else None,
            }
        )

    summary = {
        "benchmark_manifest": str(benchmark_manifest_path),
        "dataset_name": benchmark["dataset_name"],
        "project": benchmark["project"],
        "objective": objective,
        "probe_strategy": probe_strategy,
        "execution_intent": execution_intent,
        "workload_count": len(run_results),
        "outdir": str(effective_outdir),
        "system_id": system_profile["system_id"],
        "results": run_results,
    }
    dump_json(summary, effective_outdir / "summary.json")
    return summary


__all__ = ["BenchmarkRunError", "run_benchmark_manifest"]
