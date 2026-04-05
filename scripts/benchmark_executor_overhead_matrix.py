from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _median(values: list[float]) -> float:
    return round(statistics.median(values), 9)


def _manifest_name(manifest_path: str) -> str:
    return Path(manifest_path).name


def _timing(payload: dict[str, Any], key: str) -> float:
    return float((payload.get("driver_timing_json") or {}).get(key) or 0.0)


def _run_execute(
    manifest_path: str,
    system_manifest: str,
    *,
    objective: str,
    probe_strategy: str,
    planner_budget: str,
    measurement_repeats: int,
    execution_intent: str,
    replicate_idx: int,
    out_path: Path,
    plan_json_path: str | None = None,
    plan_bundle_path: str | None = None,
    prewarm_mode: str = "none",
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "aqs",
        "tnep",
        "execute",
        "--manifest",
        manifest_path,
        "--system-manifest",
        system_manifest,
        "--objective",
        objective,
        "--probe-strategy",
        probe_strategy,
        "--planner-budget",
        planner_budget,
        "--measurement-repeats",
        str(measurement_repeats),
        "--execution-intent",
        execution_intent,
        "--replicate-idx",
        str(replicate_idx),
        "--prewarm-mode",
        prewarm_mode,
        "--no-allow-distributed",
        "--out",
        str(out_path),
    ]
    if plan_json_path:
        command.extend(["--plan-json", plan_json_path])
    if plan_bundle_path:
        command.extend(["--plan-bundle", plan_bundle_path])

    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        env=os.environ.copy(),
        check=False,
        capture_output=True,
        text=True,
    )
    cli_wall_s = round(max(time.perf_counter() - started, 0.0), 9)
    if completed.returncode != 0:
        raise SystemExit(
            f"aqs tnep execute failed for {manifest_path!r} with exit code {completed.returncode}:\n"
            f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}"
        )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    run = payload["execution_run"]
    if run.get("status") != "success":
        raise SystemExit(f"Execution failed for {manifest_path!r}: status={run.get('status')!r}")
    return {
        "cli_wall_s": cli_wall_s,
        "payload": payload,
    }


def _write_seed_plan(path: Path, payload: dict[str, Any]) -> None:
    _dump_json(path, {"selected_plan": dict(payload["selected_plan"])})


def _sample_summary(sample: dict[str, Any]) -> dict[str, Any]:
    payload = sample["payload"]
    run = payload["execution_run"]
    accuracy = payload.get("accuracy_eval") or {}
    return {
        "cli_wall_s": float(sample["cli_wall_s"]),
        "driver_total_s": float(payload.get("driver_total_s") or 0.0),
        "outer_driver_overhead_s": float(payload.get("outer_driver_overhead_s") or 0.0),
        "execute_plan_bundle_s": _timing(payload, "execute_plan_bundle_s"),
        "dispatch_real_executor_s": _timing(payload, "dispatch_real_executor_s"),
        "real_execute_s": _timing(payload, "real_execute_s"),
        "post_execution_s": _timing(payload, "post_execution_s"),
        "bundle_lookup_s": _timing(payload, "bundle_lookup_s"),
        "bundle_compatibility_check_s": _timing(payload, "bundle_compatibility_check_s"),
        "pre_execute_request_validation_s": _timing(payload, "pre_execute_request_validation_s"),
        "import_real_stack_s": _timing(payload, "import_real_stack_s"),
        "network_build_s": _timing(payload, "network_build_s"),
        "pre_t_start_overhead_s": _timing(payload, "pre_t_start_overhead_s"),
        "execution_wall_s": float(run.get("wall_s") or 0.0),
        "ttfr_s": float(run.get("ttfr_s") or 0.0),
        "selected_plan_id": str(payload["selected_plan"].get("plan_id") or ""),
        "selection_source": str(payload.get("selection_source") or ""),
        "prewarm_mode": str((run.get("failure_detail_json") or {}).get("prewarm_mode") or "none"),
        "prewarm_wall_s": float((run.get("failure_detail_json") or {}).get("prewarm_wall_s") or 0.0),
        "prewarm_success": (run.get("failure_detail_json") or {}).get("prewarm_success"),
        "accuracy_status": str(accuracy.get("status") or "unknown"),
        "cache_status": str((payload.get("plan_bundle_provenance") or {}).get("cache_status") or ""),
    }


def _median_row(samples: list[dict[str, Any]], *, mode: str) -> dict[str, Any]:
    numeric_keys = [
        "cli_wall_s",
        "driver_total_s",
        "outer_driver_overhead_s",
        "execute_plan_bundle_s",
        "dispatch_real_executor_s",
        "real_execute_s",
        "post_execution_s",
        "bundle_lookup_s",
        "bundle_compatibility_check_s",
        "pre_execute_request_validation_s",
        "import_real_stack_s",
        "network_build_s",
        "pre_t_start_overhead_s",
        "execution_wall_s",
        "ttfr_s",
        "prewarm_wall_s",
    ]
    medians = {key: _median([float(sample[key]) for sample in samples]) for key in numeric_keys}
    return {
        "mode": mode,
        **medians,
        "selection_sources": sorted({sample["selection_source"] for sample in samples}),
        "selected_plan_ids": sorted({sample["selected_plan_id"] for sample in samples}),
        "prewarm_mode": sorted({sample["prewarm_mode"] for sample in samples}),
        "prewarm_successes": [sample["prewarm_success"] for sample in samples],
        "accuracy_statuses": sorted({sample["accuracy_status"] for sample in samples}),
        "bundle_cache_statuses": sorted({sample["cache_status"] for sample in samples if sample["cache_status"]}),
    }


def _mode_table(row: dict[str, Any]) -> list[str]:
    lines = [
        f"### `{_manifest_name(str(row['manifest_path']))}`",
        "",
        "| Mode | CLI Wall ms | Driver Total ms | Outer Overhead ms | Dispatch ms | Real Execute ms | Post Exec ms | Pre-T-Start ms | Network Build ms | Inner Wall ms | TTFR ms | Prewarm ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode_row in row["mode_rows"]:
        lines.append(
            "| "
            + mode_row["mode"]
            + f" | {mode_row['cli_wall_s'] * 1000.0:.3f}"
            + f" | {mode_row['driver_total_s'] * 1000.0:.3f}"
            + f" | {mode_row['outer_driver_overhead_s'] * 1000.0:.3f}"
            + f" | {mode_row['dispatch_real_executor_s'] * 1000.0:.3f}"
            + f" | {mode_row['real_execute_s'] * 1000.0:.3f}"
            + f" | {mode_row['post_execution_s'] * 1000.0:.3f}"
            + f" | {mode_row['pre_t_start_overhead_s'] * 1000.0:.3f}"
            + f" | {mode_row['network_build_s'] * 1000.0:.3f}"
            + f" | {mode_row['execution_wall_s'] * 1000.0:.3f}"
            + f" | {mode_row['ttfr_s'] * 1000.0:.3f}"
            + f" | {mode_row['prewarm_wall_s'] * 1000.0:.3f} |"
        )
    lines.extend(
        [
            "",
            f"- Seed selected plan: `{row['seed_selected_plan_id']}`",
            f"- Fresh selected plan IDs: `{row['fresh_selected_plan_ids']}`",
            f"- All override/bundle paths preserved the seed plan ID: `{row['selection_semantics_preserved']}`",
            f"- Accuracy parity across all modes: `{row['all_accuracy_pass']}`",
            f"- Bundle-hit gap vs `--plan-json`: `{row['plan_json_minus_bundle_cli_wall_s'] * 1000.0:.3f} ms`",
            f"- Recovery from explicit prewarm: `{row['bundle_minus_prewarm_cli_wall_s'] * 1000.0:.3f} ms`",
            f"- Prewarm recovered `{row['prewarm_recovery_ratio']}` of the bundle-hit gap",
            "",
        ]
    )
    return lines


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# OVH Executor Overhead Matrix",
        "",
        f"- Prewarm mode under test: `{payload['prewarm_mode']}`",
        f"- Benchmark repeats per mode: `{payload['benchmark_repeats']}`",
        f"- Workloads: `{len(payload.get('rows') or [])}`",
        f"- Interpretation: {payload['interpretation']}",
        "",
    ]
    for row in payload["rows"]:
        lines.extend(_mode_table(row))
    return "\n".join(lines) + "\n"


def _interpretation(rows: list[dict[str, Any]], prewarm_mode: str) -> str:
    recovered = [
        row for row in rows
        if row["manifest_role"] in {"low_repeat_amplitude", "low_repeat_amplitude_heldout"}
        and row["prewarm_recovered_most"]
    ]
    harmed_control = any(
        row["manifest_role"] == "control_medium_batched" and row["bundle_minus_prewarm_cli_wall_s"] < -0.010
        for row in rows
    )
    if len(recovered) >= 2 and not harmed_control:
        return (
            f"Benchmark-only prewarm mode {prewarm_mode!r} recovered most of the bundle-hit penalty on the low-repeat amplitude "
            "workloads without materially harming the medium-repeat control. The next branch should stay performance-only and "
            "focus on turning that light prewarm into a first-class opt-in bundle companion."
        )
    return (
        f"Benchmark-only prewarm mode {prewarm_mode!r} did not recover most of the bundle-hit penalty across the canonical OVH "
        "workloads. The remaining cost points toward persistent executor/session overhead rather than a lightweight warmup fix."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the OVH executor overhead matrix with one explicit prewarm mode")
    parser.add_argument("--manifest", action="append", required=True)
    parser.add_argument("--system-manifest", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--objective", default="ttfr", choices=["ttfr", "steady_state", "gpu_seconds"])
    parser.add_argument("--probe-strategy", default="real_if_available")
    parser.add_argument("--planner-budget", default="balanced")
    parser.add_argument("--measurement-repeats", type=int, default=3)
    parser.add_argument("--execution-intent", default="require_real")
    parser.add_argument("--benchmark-repeats", type=int, default=5)
    parser.add_argument("--prewarm-mode", choices=["import_context", "tiny_network"], required=True)
    args = parser.parse_args(argv)

    outdir = Path(args.outdir)
    seed_dir = outdir / "seed"
    run_dir = outdir / "runs"
    seed_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for manifest_index, manifest_path in enumerate(args.manifest):
        manifest_stem = Path(manifest_path).stem
        role = "control_medium_batched"
        if manifest_stem.startswith("01_"):
            role = "low_repeat_amplitude"
        elif manifest_stem.startswith("06_"):
            role = "low_repeat_amplitude_heldout"

        seed_bundle_path = seed_dir / f"{manifest_stem}.seed.plan_bundle.json"
        seed_out_path = seed_dir / f"{manifest_stem}.seed.execute.json"
        seed_sample = _run_execute(
            manifest_path,
            args.system_manifest,
            objective=args.objective,
            probe_strategy=args.probe_strategy,
            planner_budget=args.planner_budget,
            measurement_repeats=args.measurement_repeats,
            execution_intent=args.execution_intent,
            replicate_idx=(manifest_index * 1000),
            out_path=seed_out_path,
            plan_bundle_path=str(seed_bundle_path),
            prewarm_mode="none",
        )
        seed_payload = seed_sample["payload"]
        if seed_payload["plan_bundle_provenance"]["cache_status"] != "miss":
            raise SystemExit(f"Expected seed miss for {manifest_path!r}")
        if seed_payload["plan_bundle_provenance"]["write_status"] != "written":
            raise SystemExit(f"Expected seed bundle write for {manifest_path!r}")
        seed_plan_path = seed_dir / f"{manifest_stem}.seed.selected_plan.json"
        _write_seed_plan(seed_plan_path, seed_payload)
        seed_plan_id = str(seed_payload["selected_plan"].get("plan_id") or "")

        per_mode_samples: dict[str, list[dict[str, Any]]] = {
            "fresh": [],
            "plan_json": [],
            "bundle_hit": [],
            f"bundle_hit+{args.prewarm_mode}": [],
        }

        for repeat_idx in range(args.benchmark_repeats):
            base_idx = (manifest_index * 1000) + 1 + (repeat_idx * 10)
            mode_specs = [
                ("fresh", {"plan_json_path": None, "plan_bundle_path": None, "prewarm_mode": "none"}),
                ("plan_json", {"plan_json_path": str(seed_plan_path), "plan_bundle_path": None, "prewarm_mode": "none"}),
                ("bundle_hit", {"plan_json_path": None, "plan_bundle_path": str(seed_bundle_path), "prewarm_mode": "none"}),
                (
                    f"bundle_hit+{args.prewarm_mode}",
                    {"plan_json_path": None, "plan_bundle_path": str(seed_bundle_path), "prewarm_mode": args.prewarm_mode},
                ),
            ]
            for offset, (mode_name, mode_spec) in enumerate(mode_specs):
                sample = _run_execute(
                    manifest_path,
                    args.system_manifest,
                    objective=args.objective,
                    probe_strategy=args.probe_strategy,
                    planner_budget=args.planner_budget,
                    measurement_repeats=args.measurement_repeats,
                    execution_intent=args.execution_intent,
                    replicate_idx=base_idx + offset,
                    out_path=run_dir / f"{manifest_stem}.rep{repeat_idx}.{mode_name}.execute.json",
                    plan_json_path=mode_spec["plan_json_path"],
                    plan_bundle_path=mode_spec["plan_bundle_path"],
                    prewarm_mode=mode_spec["prewarm_mode"],
                )
                summary = _sample_summary(sample)
                per_mode_samples[mode_name].append(summary)

        mode_rows = [_median_row(per_mode_samples[mode_name], mode=mode_name) for mode_name in per_mode_samples]
        mode_lookup = {row["mode"]: row for row in mode_rows}
        fresh_ids = sorted({sample["selected_plan_id"] for sample in per_mode_samples["fresh"]})
        selection_semantics_preserved = (
            mode_lookup["plan_json"]["selected_plan_ids"] == [seed_plan_id]
            and mode_lookup["bundle_hit"]["selected_plan_ids"] == [seed_plan_id]
            and mode_lookup[f"bundle_hit+{args.prewarm_mode}"]["selected_plan_ids"] == [seed_plan_id]
        )
        all_accuracy_pass = all(
            status == "pass"
            for row in mode_rows
            for status in row["accuracy_statuses"]
        )
        plan_json_gap = round(
            mode_lookup["bundle_hit"]["cli_wall_s"] - mode_lookup["plan_json"]["cli_wall_s"],
            9,
        )
        prewarm_recovery = round(
            mode_lookup["bundle_hit"]["cli_wall_s"] - mode_lookup[f"bundle_hit+{args.prewarm_mode}"]["cli_wall_s"],
            9,
        )
        if plan_json_gap > 0.0:
            prewarm_recovery_ratio = round(prewarm_recovery / plan_json_gap, 6)
        else:
            prewarm_recovery_ratio = None
        prewarm_recovered_most = bool(
            plan_json_gap > 0.0
            and prewarm_recovery_ratio is not None
            and prewarm_recovery_ratio >= 0.7
        )

        rows.append(
            {
                "manifest_path": str(Path(manifest_path).resolve()),
                "manifest_role": role,
                "seed_selected_plan_id": seed_plan_id,
                "fresh_selected_plan_ids": fresh_ids,
                "selection_semantics_preserved": selection_semantics_preserved,
                "all_accuracy_pass": all_accuracy_pass,
                "benchmark_repeats": int(args.benchmark_repeats),
                "mode_rows": mode_rows,
                "plan_json_minus_bundle_cli_wall_s": plan_json_gap,
                "bundle_minus_prewarm_cli_wall_s": prewarm_recovery,
                "prewarm_recovery_ratio": prewarm_recovery_ratio,
                "prewarm_recovered_most": prewarm_recovered_most,
            }
        )

    summary = {
        "study": "ovh_executor_overhead_matrix_v1",
        "system_manifest_path": str(Path(args.system_manifest).resolve()),
        "objective": args.objective,
        "probe_strategy": args.probe_strategy,
        "planner_budget": args.planner_budget,
        "measurement_repeats": args.measurement_repeats,
        "execution_intent": args.execution_intent,
        "benchmark_repeats": int(args.benchmark_repeats),
        "prewarm_mode": args.prewarm_mode,
        "interpretation": _interpretation(rows, args.prewarm_mode),
        "rows": rows,
    }

    _dump_json(outdir / "ovh_executor_overhead_matrix_v1.json", summary)
    (outdir / "ovh_executor_overhead_matrix_v1.md").write_text(_build_markdown(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
