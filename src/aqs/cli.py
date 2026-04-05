from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .arch import analyze_execution_json, analyze_validation_json
from .benchmark import run_benchmark_manifest
from .campaigns import CampaignError, run_campaign_manifest, summarize_campaign_manifest, validate_campaign
from .db import (
    apply_schema,
    insert_accuracy_eval,
    insert_bottleneck_case,
    insert_feature_snapshot,
    insert_execution_run,
    insert_plan_candidate,
    insert_plan_evaluation,
    insert_probe_observation,
    insert_profile_summary,
    insert_system_profile,
    insert_validation_run,
    insert_workload_and_ir,
)
from .doctor import collect_doctor_report, collect_system_profile
from .execution import execute_selected_plan
from .features import extract_feature_snapshot
from .generators import PRESETS, generate_workload_manifest
from .graph_modes import GRAPH_MODES
from .io import dump_json
from .manifest import dump_yaml, finalize_workload_manifest, load_yaml, validate_manifest
from .normalize import normalize_workload_manifest
from .paths import default_schema_path
from .planner import PlanConfig, generate_plan_candidates, load_system_manifest, select_top_plan
from .profiler_tools import ProfileToolError, run_ncu_profile, run_nsys_profile, run_profile_smoke
from .tnprobe import ProbeConfig, run_exact_tn_probe
from .validation import validate_planner_manifest
from .measured_validation import validate_measured_manifest


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj).replace("\\", "/")
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, set):
        return sorted(_json_safe(v) for v in obj)
    return obj


def _print_json(payload: Any) -> None:
    print(json.dumps(_json_safe(payload), indent=2, sort_keys=True))


def _dump_json_safe(payload: Any, path: str | Path) -> None:
    dump_json(_json_safe(payload), path)


def _cmd_init_db(args: argparse.Namespace) -> int:
    db_path = apply_schema(args.db, args.schema, args.schema_version)
    print(f"Initialized warehouse at {db_path}")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    report = collect_doctor_report(
        profiling=bool(args.profiling),
        outdir=args.outdir,
        run_smoke=not bool(args.no_smoke),
        db_path=args.db,
    )
    payload = report["system_profile"] if not args.profiling else report
    _print_json(payload)
    if args.out:
        _dump_json_safe(payload, args.out)
        print(f"Wrote doctor report to {args.out}")
    if args.db:
        insert_system_profile(args.db, report["system_profile"])
        print(f"Inserted system profile into {args.db}")
    return 0


def _cmd_manifest_validate(args: argparse.Namespace) -> int:
    exit_code = 0
    expanded_paths: list[Path] = []
    for manifest_path in args.paths:
        matches = [Path(match) for match in glob.glob(manifest_path)]
        if matches:
            expanded_paths.extend(matches)
        else:
            expanded_paths.append(Path(manifest_path))
    for path in expanded_paths:
        manifest = load_yaml(path)
        errors = validate_manifest(manifest, mode=args.mode)
        if errors:
            exit_code = 1
            print(f"[FAIL] {path}")
            for error in errors:
                print(f"  - {error}")
            continue
        print(f"[OK] {path}")
        if args.fix_workload_ids and manifest.get("api_version") == "aqs.workload.v1":
            fixed = finalize_workload_manifest(manifest)
            dump_yaml(fixed, path)
            print(f"  fixed canonical workload IDs in {path}")
    return exit_code


def _cmd_workload_generate(args: argparse.Namespace) -> int:
    manifest = generate_workload_manifest(args.family, args.preset, args.seed, notes=args.notes)
    path = Path(args.out)
    dump_yaml(manifest, path)
    print(f"Generated workload manifest at {path}")
    _print_json(manifest["ids"])
    return 0


def _cmd_workload_normalize(args: argparse.Namespace) -> int:
    manifest = load_yaml(args.manifest)
    ir = normalize_workload_manifest(manifest)
    _print_json(ir)
    if args.out:
        _dump_json_safe(ir, args.out)
        print(f"Wrote normalized IR to {args.out}")
    if args.db:
        insert_workload_and_ir(args.db, manifest, ir)
        print(f"Inserted workload + normalized IR into {args.db}")
    return 0


def _cmd_features_extract(args: argparse.Namespace) -> int:
    manifest = load_yaml(args.manifest)
    ir = normalize_workload_manifest(manifest)
    feature_snapshot = extract_feature_snapshot(manifest, ir)
    _print_json(feature_snapshot)
    if args.out:
        _dump_json_safe(feature_snapshot, args.out)
        print(f"Wrote feature snapshot to {args.out}")
    if args.db:
        insert_workload_and_ir(args.db, manifest, ir)
        insert_feature_snapshot(args.db, feature_snapshot)
        print(f"Inserted workload, IR, and features into {args.db}")
    return 0


def _cmd_tnep_probe(args: argparse.Namespace) -> int:
    manifest = load_yaml(args.manifest)
    config = ProbeConfig(
        objective=args.objective,
        precision=args.precision,
        workspace_gb=args.workspace_gb,
        cache_workspace_gb=args.cache_workspace_gb,
        hyper_samples=args.hyper_samples,
        autotune=args.autotune,
        reuse_cache=args.reuse_cache,
        mpi_ranks=args.mpi_ranks,
        gpu_arch_target=args.gpu_arch_target,
        probe_strategy=args.probe_strategy,
    )
    probe = run_exact_tn_probe(manifest, config=config)
    _print_json(probe)
    if args.out:
        _dump_json_safe(probe, args.out)
        print(f"Wrote probe observation to {args.out}")
    if args.db:
        profile = collect_system_profile()
        insert_system_profile(args.db, profile)
        ir = normalize_workload_manifest(manifest)
        features = extract_feature_snapshot(manifest, ir)
        insert_workload_and_ir(args.db, manifest, ir)
        insert_feature_snapshot(args.db, features)
        insert_probe_observation(args.db, manifest["ids"]["workload_id"], profile["system_id"], probe, project="tnep")
        print(f"Inserted workload lineage and probe observation into {args.db}")
    return 0 if probe["status"] == "success" else 1


def _cmd_tnep_plan(args: argparse.Namespace) -> int:
    manifest = load_yaml(args.manifest)
    system_manifest = load_system_manifest(args.system_manifest)
    ir = normalize_workload_manifest(manifest)
    features = extract_feature_snapshot(manifest, ir)
    probe = run_exact_tn_probe(
        manifest,
        ProbeConfig(
            objective=args.objective,
            precision=args.precision,
            probe_strategy=args.probe_strategy,
            gpu_arch_target=system_manifest.get("gpu_arch_target"),
        ),
    )
    candidates = generate_plan_candidates(
        manifest,
        features,
        probe,
        system_manifest,
        config=PlanConfig(
            objective=args.objective,
            max_error=args.max_error,
            planner_budget=args.planner_budget,
            allow_distributed=args.allow_distributed,
            max_candidates=args.max_candidates,
        ),
    )
    selected = select_top_plan(candidates, objective=args.objective)
    payload = {
        "system_name": system_manifest["system_name"],
        "probe_id": probe["probe_id"],
        "selected_plan": selected,
        "candidates": candidates,
    }
    _print_json(payload)
    if args.out:
        _dump_json_safe(payload, args.out)
        print(f"Wrote plan candidates to {args.out}")
    if args.db:
        profile = collect_system_profile()
        insert_system_profile(args.db, profile)
        insert_workload_and_ir(args.db, manifest, ir)
        insert_feature_snapshot(args.db, features)
        insert_probe_observation(args.db, manifest["ids"]["workload_id"], profile["system_id"], probe, project="tnep")
        for candidate in candidates:
            insert_plan_candidate(args.db, manifest["ids"]["workload_id"], candidate)
        print(f"Inserted planning lineage and {len(candidates)} plan candidates into {args.db}")
    return 0


def _cmd_tnep_execute(args: argparse.Namespace) -> int:
    if args.plan_json and args.plan_bundle:
        _print_json({"error": "--plan-json and --plan-bundle are mutually exclusive"})
        return 1
    payload = execute_selected_plan(
        args.manifest,
        args.system_manifest,
        plan_rank=args.plan_rank,
        objective=args.objective,
        probe_strategy=args.probe_strategy,
        planner_budget=args.planner_budget,
        allow_distributed=args.allow_distributed,
        max_candidates=args.max_candidates,
        measurement_repeats=args.measurement_repeats,
        ttfr_repeats=args.ttfr_repeats,
        execution_intent=args.execution_intent,
        replicate_idx=args.replicate_idx,
        plan_json_path=args.plan_json,
        plan_bundle_path=args.plan_bundle,
        graph_mode=args.graph_mode,
    )
    _print_json(payload)
    if args.out:
        _dump_json_safe(payload, args.out)
        print(f"Wrote execution payload to {args.out}")
    if args.db:
        manifest = load_yaml(args.manifest)
        ir = normalize_workload_manifest(manifest)
        features = extract_feature_snapshot(manifest, ir)
        profile = collect_system_profile()
        insert_system_profile(args.db, profile)
        insert_workload_and_ir(args.db, manifest, ir)
        insert_feature_snapshot(args.db, features)
        if payload.get("probe"):
            insert_probe_observation(args.db, manifest["ids"]["workload_id"], profile["system_id"], payload["probe"], project="tnep")
        insert_plan_candidate(args.db, manifest["ids"]["workload_id"], payload["selected_plan"])
        insert_execution_run(args.db, payload["execution_run"])
        accuracy = payload.get("accuracy_eval") or {}
        for row in accuracy.get("rows", []):
            insert_accuracy_eval(args.db, row)
        if payload.get("profile_summary"):
            insert_profile_summary(args.db, payload["profile_summary"])
        print(f"Inserted execution lineage into {args.db}")
    return 0 if payload["execution_run"]["status"] == "success" else 1


def _cmd_profile_nsys(args: argparse.Namespace) -> int:
    try:
        payload = run_nsys_profile(
            manifest_path=args.manifest,
            system_manifest_path=args.system_manifest,
            outdir=args.outdir,
            plan_rank=args.plan_rank,
            objective=args.objective,
            probe_strategy=args.probe_strategy,
            planner_budget=args.planner_budget,
            allow_distributed=args.allow_distributed,
            measurement_repeats=args.measurement_repeats,
            execution_intent=args.execution_intent,
            graph_mode=args.graph_mode,
            db_path=args.db,
        )
        _print_json(payload)
        return 0
    except ProfileToolError as exc:
        _print_json({"error": str(exc), "profiler_attempt": exc.attempt})
        return 1


def _cmd_profile_ncu(args: argparse.Namespace) -> int:
    try:
        payload = run_ncu_profile(
            manifest_path=args.manifest,
            system_manifest_path=args.system_manifest,
            outdir=args.outdir,
            plan_rank=args.plan_rank,
            objective=args.objective,
            probe_strategy=args.probe_strategy,
            planner_budget=args.planner_budget,
            allow_distributed=args.allow_distributed,
            measurement_repeats=args.measurement_repeats,
            execution_intent=args.execution_intent,
            profile_mode=args.profile_mode,
            graph_mode=args.graph_mode,
            db_path=args.db,
        )
        _print_json(payload)
        return 0
    except ProfileToolError as exc:
        _print_json({"error": str(exc), "profiler_attempt": exc.attempt})
        return 1


def _cmd_profile_smoke(args: argparse.Namespace) -> int:
    try:
        payload = run_profile_smoke(tool=args.tool, outdir=args.outdir, db_path=args.db)
        _print_json(payload)
        return 0
    except ProfileToolError as exc:
        _print_json({"error": str(exc), "profiler_attempt": exc.attempt})
        return 1


def _cmd_tnep_validate_measured(args: argparse.Namespace) -> int:
    summary = validate_measured_manifest(args.manifest, db_path=args.db, outdir=args.outdir)
    _print_json(summary)
    return 0


def _cmd_tnep_validate(args: argparse.Namespace) -> int:
    summary = validate_planner_manifest(args.manifest, db_path=args.db, outdir=args.outdir)
    _print_json(summary)
    if args.db:
        insert_validation_run(args.db, summary, project="tnep")
        for workload in summary["results"]:
            for evaluation in workload["evaluations"]:
                evaluation = dict(evaluation)
                evaluation["regret"] = workload.get("regret") if evaluation["plan_id"] == workload.get("selected_plan_id") else None
                evaluation["normalized_regret"] = workload.get("normalized_regret") if evaluation["plan_id"] == workload.get("selected_plan_id") else None
                insert_plan_evaluation(args.db, evaluation, summary["validation_run_id"])
        print(f"Inserted validation summary into {args.db}")
    return 0


def _cmd_arch_analyze_execution(args: argparse.Namespace) -> int:
    analysis = analyze_execution_json(args.payload, out=args.out)
    _print_json(analysis)
    if args.db:
        for case in analysis.get("nominations", []):
            insert_bottleneck_case(args.db, case)
        print(f"Inserted {len(analysis.get('nominations', []))} bottleneck nominations into {args.db}")
    return 0


def _cmd_arch_analyze_validation(args: argparse.Namespace) -> int:
    analysis = analyze_validation_json(args.summary, out=args.out)
    _print_json(analysis)
    if args.db:
        inserted = 0
        for workload in analysis.get("workload_analyses", []):
            for case in workload.get("nominations", []):
                insert_bottleneck_case(args.db, case)
                inserted += 1
        print(f"Inserted {inserted} bottleneck nominations into {args.db}")
    return 0


def _cmd_benchmark_run(args: argparse.Namespace) -> int:
    summary = run_benchmark_manifest(args.manifest, db_path=args.db, outdir=args.outdir)
    _print_json(summary)
    return 0


def _cmd_campaign_validate(args: argparse.Namespace) -> int:
    try:
        summary = validate_campaign(args.manifest)
    except CampaignError as exc:
        _print_json({"error": str(exc)})
        return 1
    _print_json(summary)
    return 0


def _cmd_campaign_run(args: argparse.Namespace) -> int:
    try:
        summary = run_campaign_manifest(args.manifest, db_path=args.db, outdir=args.outdir)
    except CampaignError as exc:
        _print_json({"error": str(exc)})
        return 1
    _print_json(summary)
    return 0


def _cmd_campaign_summarize(args: argparse.Namespace) -> int:
    try:
        summary = summarize_campaign_manifest(args.manifest, outdir=args.outdir)
    except CampaignError as exc:
        _print_json({"error": str(exc)})
        return 1
    _print_json(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aqs", description="Quantum Workload Architecture CLI")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    init_db = sub.add_parser("init-db", help="Apply the warehouse schema to a DuckDB file")
    init_db.add_argument("--db", required=True, help="Path to the DuckDB file")
    init_db.add_argument("--schema", default=str(default_schema_path()), help="Path to schema.sql")
    init_db.add_argument("--schema-version", default="aqs_schema_v0")
    init_db.set_defaults(func=_cmd_init_db)

    doctor = sub.add_parser("doctor", help="Capture machine metadata and optionally insert into the warehouse")
    doctor.add_argument("--db", help="Optional DuckDB path for insertion")
    doctor.add_argument("--profiling", action="store_true", help="Run profiling-capability readiness checks and smoke targets")
    doctor.add_argument("--no-smoke", action="store_true", help="Skip smoke profiling commands in profiling readiness mode")
    doctor.add_argument("--outdir", help="Optional output directory for profiling readiness artifacts")
    doctor.add_argument("--out", help="Optional JSON output path for the doctor report")
    doctor.set_defaults(func=_cmd_doctor)

    manifest = sub.add_parser("manifest", help="Manifest utilities")
    manifest_sub = manifest.add_subparsers(dest="manifest_command", required=True)

    validate = manifest_sub.add_parser("validate", help="Validate one or more manifests")
    validate.add_argument("paths", nargs="+", help="YAML manifest paths")
    validate.add_argument("--mode", default="schema", choices=["schema", "implemented", "real"], help="Validation strictness")
    validate.add_argument("--fix-workload-ids", action="store_true", help="Rewrite canonical workload IDs for valid workload manifests")
    validate.set_defaults(func=_cmd_manifest_validate)

    workload = sub.add_parser("workload", help="Workload generators and normalization")
    workload_sub = workload.add_subparsers(dest="workload_command", required=True)

    generate = workload_sub.add_parser("generate", help="Generate a deterministic starter workload manifest")
    generate.add_argument("--family", choices=sorted(PRESETS.keys()), required=True)
    generate.add_argument("--preset", required=True, help="Preset name for the selected family")
    generate.add_argument("--seed", type=int, required=True)
    generate.add_argument("--out", required=True)
    generate.add_argument("--notes")
    generate.set_defaults(func=_cmd_workload_generate)

    normalize = workload_sub.add_parser("normalize", help="Normalize a workload manifest into the shared IR")
    normalize.add_argument("--manifest", required=True)
    normalize.add_argument("--db")
    normalize.add_argument("--out")
    normalize.set_defaults(func=_cmd_workload_normalize)

    features = sub.add_parser("features", help="Feature extraction utilities")
    features_sub = features.add_subparsers(dest="features_command", required=True)
    extract = features_sub.add_parser("extract", help="Extract static features from a workload manifest")
    extract.add_argument("--manifest", required=True)
    extract.add_argument("--db")
    extract.add_argument("--out")
    extract.set_defaults(func=_cmd_features_extract)

    tnep = sub.add_parser("tnep", help="Tensor-network execution planner scaffolding")
    tnep_sub = tnep.add_subparsers(dest="tnep_command", required=True)

    probe = tnep_sub.add_parser("probe", help="Run an exact-TN probe path on either a surrogate or imported real-circuit structure")
    probe.add_argument("--manifest", required=True)
    probe.add_argument("--db")
    probe.add_argument("--out")
    probe.add_argument("--objective", default="ttfr", choices=["ttfr", "steady_state", "gpu_seconds"])
    probe.add_argument("--precision", default="complex128", choices=["fp32", "fp64", "complex64", "complex128"])
    probe.add_argument("--workspace-gb", type=float)
    probe.add_argument("--cache-workspace-gb", type=float)
    probe.add_argument("--hyper-samples", type=int)
    probe.add_argument("--autotune", action=argparse.BooleanOptionalAction, default=None)
    probe.add_argument("--reuse-cache", action=argparse.BooleanOptionalAction, default=None)
    probe.add_argument("--mpi-ranks", type=int)
    probe.add_argument("--gpu-arch-target")
    probe.add_argument("--probe-strategy", default="surrogate_only", choices=["surrogate_only", "structural_real", "real_if_available", "cuquantum_if_available", "cuquantum_required"])
    probe.set_defaults(func=_cmd_tnep_probe)

    plan = tnep_sub.add_parser("plan", help="Generate ranked exact-TN plan candidates from a probe and system profile")
    plan.add_argument("--manifest", required=True)
    plan.add_argument("--system-manifest", required=True)
    plan.add_argument("--db")
    plan.add_argument("--out")
    plan.add_argument("--objective", default="ttfr", choices=["ttfr", "steady_state", "gpu_seconds"])
    plan.add_argument("--precision", default="complex128", choices=["fp32", "fp64", "complex64", "complex128"])
    plan.add_argument("--max-error", type=float, default=0.0)
    plan.add_argument("--planner-budget", default="balanced", choices=["quick", "balanced", "deep"])
    plan.add_argument("--allow-distributed", action=argparse.BooleanOptionalAction, default=True)
    plan.add_argument("--max-candidates", type=int)
    plan.add_argument("--probe-strategy", default="surrogate_only", choices=["surrogate_only", "structural_real", "real_if_available", "cuquantum_if_available", "cuquantum_required"])
    plan.set_defaults(func=_cmd_tnep_plan)

    execute_tnep = tnep_sub.add_parser("execute", help="Execute the selected exact-TN plan on the measured structural executor")
    execute_tnep.add_argument("--manifest", required=True, help="Path to the workload manifest")
    execute_tnep.add_argument("--system-manifest", required=True, help="Path to the system manifest")
    execute_tnep.add_argument("--plan-rank", type=int, default=1, help="Recommendation rank to execute")
    execute_tnep.add_argument("--objective", choices=["ttfr", "steady_state", "gpu_seconds"], default="ttfr")
    execute_tnep.add_argument("--plan-json", help="Optional JSON file containing an explicit plan object to execute")
    execute_tnep.add_argument(
        "--plan-bundle",
        help=(
            "Optional reusable plan bundle path. If the bundle exists and matches the current workload/system context exactly, "
            "the selected plan is reused. If the path is missing, the planner runs normally and writes a compatible bundle after success."
        ),
    )
    execute_tnep.add_argument("--probe-strategy", choices=["surrogate_only", "structural_real", "real_if_available", "cuquantum_if_available", "cuquantum_required"], default="structural_real")
    execute_tnep.add_argument("--planner-budget", choices=["quick", "balanced", "deep"], default="balanced")
    execute_tnep.add_argument("--measurement-repeats", type=int, default=3)
    execute_tnep.add_argument("--ttfr-repeats", type=int, default=1, help="Calibration-only fresh-network cold-TTFR repeats; default keeps the single-shot path")
    execute_tnep.add_argument("--replicate-idx", type=int, default=0)
    execute_tnep.add_argument("--graph-mode", choices=list(GRAPH_MODES), default=None, help="Optional CUDA Graph execution mode override")
    execute_tnep.add_argument("--execution-intent", choices=["optional_real", "prefer_real", "require_real"], default="optional_real")
    execute_tnep.add_argument("--allow-distributed", action=argparse.BooleanOptionalAction, default=True)
    execute_tnep.add_argument("--max-candidates", type=int)
    execute_tnep.add_argument("--out", help="Optional JSON output path")
    execute_tnep.add_argument("--db", help="Optional DuckDB path for insertion")
    execute_tnep.set_defaults(func=_cmd_tnep_execute)

    validate_planner = tnep_sub.add_parser("validate", help="Run surrogate-oracle regret validation over a workload family split")
    validate_planner.add_argument("--manifest", required=True, help="Benchmark manifest describing the validation slice")
    validate_planner.add_argument("--db")
    validate_planner.add_argument("--outdir")
    validate_planner.set_defaults(func=_cmd_tnep_validate)

    validate_measured = tnep_sub.add_parser("validate-measured", help="Run measured exact-TN validation over a small execution slice")
    validate_measured.add_argument("--manifest", required=True, help="Benchmark manifest describing the measured validation slice")
    validate_measured.add_argument("--db")
    validate_measured.add_argument("--outdir")
    validate_measured.set_defaults(func=_cmd_tnep_validate_measured)

    profile = sub.add_parser("profile", help="Profiler wrappers for real execution")
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)

    profile_nsys = profile_sub.add_parser("nsys", help="Run Nsight Systems over the shared execution entrypoint")
    profile_nsys.add_argument("--manifest", required=True)
    profile_nsys.add_argument("--system-manifest", required=True)
    profile_nsys.add_argument("--plan-rank", type=int, default=1)
    profile_nsys.add_argument("--objective", choices=["ttfr", "steady_state", "gpu_seconds"], default="ttfr")
    profile_nsys.add_argument("--probe-strategy", choices=["surrogate_only", "structural_real", "real_if_available", "cuquantum_if_available", "cuquantum_required"], default="structural_real")
    profile_nsys.add_argument("--planner-budget", choices=["quick", "balanced", "deep"], default="balanced")
    profile_nsys.add_argument("--measurement-repeats", type=int, default=3)
    profile_nsys.add_argument("--graph-mode", choices=list(GRAPH_MODES), default=None, help="Optional CUDA Graph execution mode override")
    profile_nsys.add_argument("--execution-intent", choices=["optional_real", "prefer_real", "require_real"], default="require_real")
    profile_nsys.add_argument("--allow-distributed", action=argparse.BooleanOptionalAction, default=False)
    profile_nsys.add_argument("--outdir")
    profile_nsys.add_argument("--db")
    profile_nsys.set_defaults(func=_cmd_profile_nsys)

    profile_ncu = profile_sub.add_parser("ncu", help="Run Nsight Compute over the shared execution entrypoint")
    profile_ncu.add_argument("--manifest", required=True)
    profile_ncu.add_argument("--system-manifest", required=True)
    profile_ncu.add_argument("--plan-rank", type=int, default=1)
    profile_ncu.add_argument("--objective", choices=["ttfr", "steady_state", "gpu_seconds"], default="ttfr")
    profile_ncu.add_argument("--probe-strategy", choices=["surrogate_only", "structural_real", "real_if_available", "cuquantum_if_available", "cuquantum_required"], default="structural_real")
    profile_ncu.add_argument("--planner-budget", choices=["quick", "balanced", "deep"], default="balanced")
    profile_ncu.add_argument("--measurement-repeats", type=int, default=3)
    profile_ncu.add_argument("--execution-intent", choices=["optional_real", "prefer_real", "require_real"], default="require_real")
    profile_ncu.add_argument("--profile-mode", choices=["basic", "diagnostic", "deep"], default="basic")
    profile_ncu.add_argument("--graph-mode", choices=list(GRAPH_MODES), default=None, help="Optional CUDA Graph execution mode override")
    profile_ncu.add_argument("--allow-distributed", action=argparse.BooleanOptionalAction, default=False)
    profile_ncu.add_argument("--outdir")
    profile_ncu.add_argument("--db")
    profile_ncu.set_defaults(func=_cmd_profile_ncu)

    profile_smoke = profile_sub.add_parser("smoke", help="Run the minimal profiler smoke target outside the full quantum pipeline")
    profile_smoke.add_argument("--tool", choices=["nsys", "ncu", "all"], default="all")
    profile_smoke.add_argument("--outdir")
    profile_smoke.add_argument("--db")
    profile_smoke.set_defaults(func=_cmd_profile_smoke)

    arch = sub.add_parser("arch", help="Architecture-facing analytics from measured runs")
    arch_sub = arch.add_subparsers(dest="arch_command", required=True)

    arch_exec = arch_sub.add_parser("analyze-execution", help="Nominate bottlenecks from one execution payload")
    arch_exec.add_argument("--payload", required=True, help="Path to a JSON payload emitted by `aqs tnep execute`")
    arch_exec.add_argument("--out", help="Optional JSON output path")
    arch_exec.add_argument("--db", help="Optional DuckDB path for insertion")
    arch_exec.set_defaults(func=_cmd_arch_analyze_execution)

    arch_val = arch_sub.add_parser("analyze-validation", help="Aggregate bottleneck nominations from a measured validation summary")
    arch_val.add_argument("--summary", required=True, help="Path to a measured validation summary JSON")
    arch_val.add_argument("--out", help="Optional JSON output path")
    arch_val.add_argument("--db", help="Optional DuckDB path for insertion")
    arch_val.set_defaults(func=_cmd_arch_analyze_validation)

    benchmark = sub.add_parser("benchmark", help="Benchmark manifest runners")
    benchmark_sub = benchmark.add_subparsers(dest="benchmark_command", required=True)
    bench_run = benchmark_sub.add_parser("run", help="Run a benchmark manifest over a workload glob")
    bench_run.add_argument("--manifest", required=True)
    bench_run.add_argument("--db")
    bench_run.add_argument("--outdir")
    bench_run.set_defaults(func=_cmd_benchmark_run)

    campaign = sub.add_parser("campaign", help="Campaign manifest runners")
    campaign_sub = campaign.add_subparsers(dest="campaign_command", required=True)

    campaign_validate = campaign_sub.add_parser("validate", help="Validate and enumerate a campaign manifest")
    campaign_validate.add_argument("--manifest", required=True)
    campaign_validate.set_defaults(func=_cmd_campaign_validate)

    campaign_run = campaign_sub.add_parser("run", help="Run a campaign manifest")
    campaign_run.add_argument("--manifest", required=True)
    campaign_run.add_argument("--db")
    campaign_run.add_argument("--outdir")
    campaign_run.set_defaults(func=_cmd_campaign_run)

    campaign_summarize = campaign_sub.add_parser("summarize", help="Render campaign outputs from existing cell artifacts")
    campaign_summarize.add_argument("--manifest", required=True)
    campaign_summarize.add_argument("--outdir")
    campaign_summarize.set_defaults(func=_cmd_campaign_summarize)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 1 and argv[0] in {"-V", "--version"}:
        print(f"aqs {__version__}")
        return 0
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:  # pragma: no cover - CLI boundary
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
