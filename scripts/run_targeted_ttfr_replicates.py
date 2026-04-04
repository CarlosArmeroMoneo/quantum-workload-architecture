from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aqs.execution import execute_selected_plan  # noqa: E402
from aqs.validation_confidence import pair_lookup_key  # noqa: E402


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _output_label(template_name: str, *, side: str, collide: bool) -> str:
    if collide:
        return f"{template_name}.{side}"
    return template_name


def _matches_manifest(candidate_path: str, requested_manifest: str) -> bool:
    return candidate_path == requested_manifest or candidate_path.endswith(requested_manifest)


def _find_workload(summary: dict[str, Any], manifest_path: str) -> dict[str, Any]:
    for workload in summary.get("results", []):
        candidate_path = str(workload.get("manifest_path") or "")
        if _matches_manifest(candidate_path, manifest_path):
            return workload
    raise SystemExit(f"Could not find manifest {manifest_path!r} in {summary.get('dataset_name')!r}")


def _find_evaluation(workload: dict[str, Any], template_name: str) -> dict[str, Any]:
    for evaluation in workload.get("evaluations", []):
        candidate = evaluation.get("candidate") or {}
        if candidate.get("template_name") == template_name:
            return evaluation
    raise SystemExit(f"Could not find template {template_name!r} for workload {workload.get('manifest_path')!r}")


def _pair_lookup_payload(workload: dict[str, Any], left_template: str, right_template: str) -> dict[str, Any] | None:
    key = pair_lookup_key(workload.get("workload_id"), left_template, right_template)
    if key is None:
        return None
    return {
        "workload_id": key[0],
        "templates": list(key[1]),
    }


def _sample_stats(samples: list[float]) -> dict[str, float | int]:
    if not samples:
        return {
            "count": 0,
            "median": 0.0,
            "mean": 0.0,
            "stdev": 0.0,
            "min": 0.0,
            "max": 0.0,
        }
    return {
        "count": len(samples),
        "median": round(statistics.median(samples), 9),
        "mean": round(statistics.mean(samples), 9),
        "stdev": round(statistics.stdev(samples), 9) if len(samples) > 1 else 0.0,
        "min": round(min(samples), 9),
        "max": round(max(samples), 9),
    }


def _ttfr_stats(payload: dict[str, Any]) -> dict[str, float]:
    calibration = (
        payload.get("execution_run", {})
        .get("failure_detail_json", {})
        .get("calibration_ttfr", {})
        .get("ttfr_stats", {})
    )
    return {
        "median": float(calibration.get("median") or 0.0),
        "stdev": float(calibration.get("stdev") or 0.0),
        "min": float(calibration.get("min") or 0.0),
        "max": float(calibration.get("max") or 0.0),
    }


def _phase_sample(payload: dict[str, Any]) -> dict[str, float]:
    run = payload.get("execution_run", {})
    if run.get("status") != "success":
        raise SystemExit(f"Targeted TTFR replicate payload did not succeed: status={run.get('status')!r}")
    phase_times = run.get("failure_detail_json", {}).get("phase_times", {})
    setup_time_s = (
        float(phase_times.get("load_circuit") or 0.0)
        + float(phase_times.get("convert_to_einsum") or 0.0)
        + float(phase_times.get("postprocess") or 0.0)
    )
    planner_time_s = float(phase_times.get("contract_path") or 0.0) + float(phase_times.get("autotune") or 0.0)
    first_contract_time_s = float(phase_times.get("contract_first") or 0.0)
    return {
        "ttfr_s": round(float(run.get("ttfr_s") or 0.0), 9),
        "planner_time_s": round(planner_time_s, 9),
        "setup_time_s": round(setup_time_s, 9),
        "first_contract_time_s": round(first_contract_time_s, 9),
    }


def _delta_confidence_interval(deltas_s: list[float]) -> dict[str, Any]:
    if not deltas_s:
        return {
            "level": 0.95,
            "method": "normal_mean_ci",
            "lower_s": None,
            "upper_s": None,
            "half_width_s": None,
        }
    if len(deltas_s) == 1:
        value = round(float(deltas_s[0]), 9)
        return {
            "level": 0.95,
            "method": "degenerate_single_sample",
            "lower_s": value,
            "upper_s": value,
            "half_width_s": 0.0,
        }
    stdev = statistics.stdev(deltas_s)
    half_width = 1.96 * stdev / math.sqrt(len(deltas_s))
    mean = statistics.mean(deltas_s)
    return {
        "level": 0.95,
        "method": "normal_mean_ci",
        "lower_s": round(mean - half_width, 9),
        "upper_s": round(mean + half_width, 9),
        "half_width_s": round(half_width, 9),
    }


def _build_sequential_pair_summary(
    workload: dict[str, Any],
    left_template: str,
    left_eval: dict[str, Any],
    left_payload: dict[str, Any],
    right_template: str,
    right_eval: dict[str, Any],
    right_payload: dict[str, Any],
    *,
    left_payload_paths: list[str],
    right_payload_paths: list[str],
) -> dict[str, Any]:
    left_baseline = float(left_eval.get("observed_ttfr_s") or 0.0)
    right_baseline = float(right_eval.get("observed_ttfr_s") or 0.0)
    baseline_winner = left_template if left_baseline <= right_baseline else right_template

    left_stats = _ttfr_stats(left_payload)
    right_stats = _ttfr_stats(right_payload)
    left_median = left_stats["median"]
    right_median = right_stats["median"]
    median_winner = left_template if left_median <= right_median else right_template

    winner_median = min(left_median, right_median)
    runner_up_median = max(left_median, right_median)
    winner_gap_s = round(runner_up_median - winner_median, 9)
    winner_gap_pct = round(winner_gap_s / max(winner_median, 1e-9), 6)
    uncertainty_band_s = round(max(left_stats["stdev"], right_stats["stdev"]), 9)

    if winner_gap_s <= uncertainty_band_s:
        conclusion = "inconclusive_vs_variance"
    elif median_winner != baseline_winner:
        conclusion = "winner_flipped_vs_single_shot"
    else:
        conclusion = "winner_stable"

    return {
        "source": "targeted_ttfr_replicates",
        "pair_mode": "sequential",
        "workload_id": workload.get("workload_id"),
        "manifest_path": workload.get("manifest_path"),
        "family_id": workload.get("family_id"),
        "repeat_count_hint": workload.get("repeat_count_hint"),
        "pair_lookup_key": _pair_lookup_payload(workload, left_template, right_template),
        "left_template": left_template,
        "right_template": right_template,
        "baseline_left_ttfr_s": round(left_baseline, 9),
        "baseline_right_ttfr_s": round(right_baseline, 9),
        "baseline_winner_template": baseline_winner,
        "replicate_left_median_ttfr_s": round(left_median, 9),
        "replicate_right_median_ttfr_s": round(right_median, 9),
        "replicate_winner_template": median_winner,
        "winner_gap_s": winner_gap_s,
        "winner_gap_pct": winner_gap_pct,
        "uncertainty_band_s": uncertainty_band_s,
        "left_ttfr_stats": left_stats,
        "right_ttfr_stats": right_stats,
        "per_block_deltas_s": None,
        "delta_mean_s": None,
        "delta_median_s": None,
        "delta_stdev_s": None,
        "delta_confidence_interval": None,
        "conclusion": conclusion,
        "payload_paths": {
            "left": left_payload_paths,
            "right": right_payload_paths,
        },
    }


def _build_interleaved_pair_summary(
    workload: dict[str, Any],
    left_template: str,
    left_eval: dict[str, Any],
    left_samples: list[dict[str, float]],
    right_template: str,
    right_eval: dict[str, Any],
    right_samples: list[dict[str, float]],
    *,
    left_payload_paths: list[str],
    right_payload_paths: list[str],
) -> dict[str, Any]:
    if len(left_samples) != len(right_samples):
        raise SystemExit("interleaved pair summaries require the same number of left and right blocks")

    left_baseline = float(left_eval.get("observed_ttfr_s") or 0.0)
    right_baseline = float(right_eval.get("observed_ttfr_s") or 0.0)
    baseline_winner = left_template if left_baseline <= right_baseline else right_template

    left_ttfr_samples = [float(sample["ttfr_s"]) for sample in left_samples]
    right_ttfr_samples = [float(sample["ttfr_s"]) for sample in right_samples]
    left_stats = _sample_stats(left_ttfr_samples)
    right_stats = _sample_stats(right_ttfr_samples)

    left_median = float(left_stats["median"])
    right_median = float(right_stats["median"])
    median_winner = left_template if left_median <= right_median else right_template

    winner_median = min(left_median, right_median)
    runner_up_median = max(left_median, right_median)
    winner_gap_s = round(runner_up_median - winner_median, 9)
    winner_gap_pct = round(winner_gap_s / max(winner_median, 1e-9), 6)

    deltas_s = [round(right["ttfr_s"] - left["ttfr_s"], 9) for left, right in zip(left_samples, right_samples)]
    delta_ci = _delta_confidence_interval(deltas_s)
    ci_lower = delta_ci.get("lower_s")
    ci_upper = delta_ci.get("upper_s")
    ci_crosses_zero = ci_lower is None or ci_upper is None or (float(ci_lower) <= 0.0 <= float(ci_upper))
    uncertainty_band_s = delta_ci.get("half_width_s")
    delta_mean_s = round(statistics.mean(deltas_s), 9) if deltas_s else None
    delta_median_s = round(statistics.median(deltas_s), 9) if deltas_s else None
    delta_stdev_s = round(statistics.stdev(deltas_s), 9) if len(deltas_s) > 1 else (0.0 if deltas_s else None)

    if ci_crosses_zero:
        conclusion = "inconclusive_vs_variance"
    elif median_winner != baseline_winner:
        conclusion = "winner_flipped_vs_single_shot"
    else:
        conclusion = "winner_stable"

    return {
        "source": "targeted_ttfr_replicates",
        "pair_mode": "interleaved",
        "delta_definition": "right_minus_left_ttfr_s",
        "workload_id": workload.get("workload_id"),
        "manifest_path": workload.get("manifest_path"),
        "family_id": workload.get("family_id"),
        "repeat_count_hint": workload.get("repeat_count_hint"),
        "pair_lookup_key": _pair_lookup_payload(workload, left_template, right_template),
        "left_template": left_template,
        "right_template": right_template,
        "baseline_left_ttfr_s": round(left_baseline, 9),
        "baseline_right_ttfr_s": round(right_baseline, 9),
        "baseline_winner_template": baseline_winner,
        "replicate_left_median_ttfr_s": round(left_median, 9),
        "replicate_right_median_ttfr_s": round(right_median, 9),
        "replicate_winner_template": median_winner,
        "winner_gap_s": winner_gap_s,
        "winner_gap_pct": winner_gap_pct,
        "uncertainty_band_s": uncertainty_band_s,
        "left_ttfr_samples_s": [round(value, 9) for value in left_ttfr_samples],
        "right_ttfr_samples_s": [round(value, 9) for value in right_ttfr_samples],
        "left_planner_time_samples_s": [round(float(sample["planner_time_s"]), 9) for sample in left_samples],
        "right_planner_time_samples_s": [round(float(sample["planner_time_s"]), 9) for sample in right_samples],
        "left_setup_time_samples_s": [round(float(sample["setup_time_s"]), 9) for sample in left_samples],
        "right_setup_time_samples_s": [round(float(sample["setup_time_s"]), 9) for sample in right_samples],
        "left_first_contract_samples_s": [round(float(sample["first_contract_time_s"]), 9) for sample in left_samples],
        "right_first_contract_samples_s": [round(float(sample["first_contract_time_s"]), 9) for sample in right_samples],
        "left_ttfr_stats": left_stats,
        "right_ttfr_stats": right_stats,
        "left_planner_time_stats": _sample_stats([float(sample["planner_time_s"]) for sample in left_samples]),
        "right_planner_time_stats": _sample_stats([float(sample["planner_time_s"]) for sample in right_samples]),
        "left_setup_time_stats": _sample_stats([float(sample["setup_time_s"]) for sample in left_samples]),
        "right_setup_time_stats": _sample_stats([float(sample["setup_time_s"]) for sample in right_samples]),
        "left_first_contract_stats": _sample_stats([float(sample["first_contract_time_s"]) for sample in left_samples]),
        "right_first_contract_stats": _sample_stats([float(sample["first_contract_time_s"]) for sample in right_samples]),
        "per_block_deltas_s": deltas_s,
        "delta_mean_s": delta_mean_s,
        "delta_median_s": delta_median_s,
        "delta_stdev_s": delta_stdev_s,
        "delta_confidence_interval": delta_ci,
        "conclusion": conclusion,
        "payload_paths": {
            "left": left_payload_paths,
            "right": right_payload_paths,
        },
    }


def _write_pair_markdown(path: Path, *, summary_path: Path, pair_payload: dict[str, Any]) -> None:
    lines = [
        "# Targeted TTFR Replicate Pair Summary",
        "",
        f"- Source summary: `{summary_path}`",
        f"- Manifest: `{pair_payload['manifest_path']}`",
        f"- Pair: `{pair_payload['left_template']}` vs `{pair_payload['right_template']}`",
        f"- Pair mode: `{pair_payload['pair_mode']}`",
        f"- Baseline single-shot winner: `{pair_payload['baseline_winner_template']}`",
        f"- Replicate median winner: `{pair_payload['replicate_winner_template']}`",
        f"- Winner gap: `{pair_payload['winner_gap_s'] * 1000.0:.3f} ms`",
        f"- Uncertainty band: `{((pair_payload.get('uncertainty_band_s') or 0.0) * 1000.0):.3f} ms`",
        f"- Conclusion: `{pair_payload['conclusion']}`",
    ]
    if pair_payload.get("pair_mode") == "interleaved":
        delta_ci = pair_payload.get("delta_confidence_interval") or {}
        lines.extend(
            [
                f"- Delta definition: `{pair_payload.get('delta_definition')}`",
                f"- Delta median: `{((pair_payload.get('delta_median_s') or 0.0) * 1000.0):.3f} ms`",
                f"- Delta 95% CI: `[{((delta_ci.get('lower_s') or 0.0) * 1000.0):.3f}, {((delta_ci.get('upper_s') or 0.0) * 1000.0):.3f}] ms`",
            ]
        )
    lines.extend(
        [
            "",
            "## Pair Table",
            "",
            "| Template | Baseline TTFR (ms) | Replicate median TTFR (ms) |",
            "| --- | ---: | ---: |",
            f"| `{pair_payload['left_template']}` | {pair_payload['baseline_left_ttfr_s'] * 1000.0:.3f} | {pair_payload['replicate_left_median_ttfr_s'] * 1000.0:.3f} |",
            f"| `{pair_payload['right_template']}` | {pair_payload['baseline_right_ttfr_s'] * 1000.0:.3f} | {pair_payload['replicate_right_median_ttfr_s'] * 1000.0:.3f} |",
        ]
    )
    if pair_payload.get("pair_mode") == "interleaved":
        lines.extend(
            [
                "",
                "## Interleaved Delta Summary",
                "",
                "- `per_block_deltas_s` records `right_ttfr_s - left_ttfr_s` for each `A/B` block.",
                f"- Delta mean: `{((pair_payload.get('delta_mean_s') or 0.0) * 1000.0):.3f} ms`",
                f"- Delta stdev: `{((pair_payload.get('delta_stdev_s') or 0.0) * 1000.0):.3f} ms`",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _execute_plan(
    manifest_path: str,
    system_manifest: str,
    *,
    objective: str,
    probe_strategy: str,
    planner_budget: str,
    measurement_repeats: int,
    ttfr_repeats: int,
    execution_intent: str,
    plan_path: Path,
    replicate_idx: int,
) -> dict[str, Any]:
    return execute_selected_plan(
        manifest_path,
        system_manifest,
        objective=objective,
        probe_strategy=probe_strategy,
        planner_budget=planner_budget,
        allow_distributed=False,
        measurement_repeats=measurement_repeats,
        ttfr_repeats=ttfr_repeats,
        execution_intent=execution_intent,
        replicate_idx=replicate_idx,
        plan_json_path=str(plan_path),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run targeted calibration-only TTFR replicates for one workload pair")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--manifest", required=True, help="Exact manifest path or suffix to match inside the summary")
    parser.add_argument("--left-template", required=True)
    parser.add_argument("--right-template", required=True)
    parser.add_argument("--system-manifest", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--objective", default="ttfr", choices=["ttfr", "steady_state", "gpu_seconds"])
    parser.add_argument("--probe-strategy", default="real_if_available")
    parser.add_argument("--planner-budget", default="balanced")
    parser.add_argument("--measurement-repeats", type=int, default=2)
    parser.add_argument("--ttfr-repeats", type=int, default=7)
    parser.add_argument("--execution-intent", default="require_real")
    parser.add_argument("--pair-mode", default="sequential", choices=["sequential", "interleaved"])
    args = parser.parse_args(argv)

    summary_path = Path(args.summary).resolve()
    summary = _load_json(summary_path)
    workload = _find_workload(summary, args.manifest)
    left_eval = _find_evaluation(workload, args.left_template)
    right_eval = _find_evaluation(workload, args.right_template)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    plan_dir = outdir / "plan_overrides"
    plan_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = str(workload["manifest_path"])
    manifest_stem = Path(manifest_path).stem
    label_collision = args.left_template == args.right_template
    left_output_label = _output_label(args.left_template, side="left", collide=label_collision)
    right_output_label = _output_label(args.right_template, side="right", collide=label_collision)
    left_plan_path = plan_dir / f"{manifest_stem}.{left_output_label}.json"
    right_plan_path = plan_dir / f"{manifest_stem}.{right_output_label}.json"
    _dump_json(left_plan_path, dict(left_eval.get("candidate") or {}))
    _dump_json(right_plan_path, dict(right_eval.get("candidate") or {}))

    if args.pair_mode == "sequential":
        left_payload = _execute_plan(
            manifest_path,
            args.system_manifest,
            objective=args.objective,
            probe_strategy=args.probe_strategy,
            planner_budget=args.planner_budget,
            measurement_repeats=args.measurement_repeats,
            ttfr_repeats=args.ttfr_repeats,
            execution_intent=args.execution_intent,
            plan_path=left_plan_path,
            replicate_idx=0,
        )
        right_payload = _execute_plan(
            manifest_path,
            args.system_manifest,
            objective=args.objective,
            probe_strategy=args.probe_strategy,
            planner_budget=args.planner_budget,
            measurement_repeats=args.measurement_repeats,
            ttfr_repeats=args.ttfr_repeats,
            execution_intent=args.execution_intent,
            plan_path=right_plan_path,
            replicate_idx=0,
        )

        left_payload_path = outdir / f"{manifest_stem}.{left_output_label}.execute.json"
        right_payload_path = outdir / f"{manifest_stem}.{right_output_label}.execute.json"
        _dump_json(left_payload_path, left_payload)
        _dump_json(right_payload_path, right_payload)

        pair_payload = _build_sequential_pair_summary(
            workload,
            args.left_template,
            left_eval,
            left_payload,
            args.right_template,
            right_eval,
            right_payload,
            left_payload_paths=[str(left_payload_path.resolve())],
            right_payload_paths=[str(right_payload_path.resolve())],
        )
    else:
        block_dir = outdir / "blocks"
        block_dir.mkdir(parents=True, exist_ok=True)

        left_samples: list[dict[str, float]] = []
        right_samples: list[dict[str, float]] = []
        left_payload_paths: list[str] = []
        right_payload_paths: list[str] = []

        for block_idx in range(args.ttfr_repeats):
            left_payload = _execute_plan(
                manifest_path,
                args.system_manifest,
                objective=args.objective,
                probe_strategy=args.probe_strategy,
                planner_budget=args.planner_budget,
                measurement_repeats=args.measurement_repeats,
                ttfr_repeats=1,
                execution_intent=args.execution_intent,
                plan_path=left_plan_path,
                replicate_idx=block_idx * 2,
            )
            left_samples.append(_phase_sample(left_payload))
            left_payload_path = block_dir / f"{manifest_stem}.block{block_idx:02d}.{left_output_label}.execute.json"
            _dump_json(left_payload_path, left_payload)
            left_payload_paths.append(str(left_payload_path.resolve()))

            right_payload = _execute_plan(
                manifest_path,
                args.system_manifest,
                objective=args.objective,
                probe_strategy=args.probe_strategy,
                planner_budget=args.planner_budget,
                measurement_repeats=args.measurement_repeats,
                ttfr_repeats=1,
                execution_intent=args.execution_intent,
                plan_path=right_plan_path,
                replicate_idx=(block_idx * 2) + 1,
            )
            right_samples.append(_phase_sample(right_payload))
            right_payload_path = block_dir / f"{manifest_stem}.block{block_idx:02d}.{right_output_label}.execute.json"
            _dump_json(right_payload_path, right_payload)
            right_payload_paths.append(str(right_payload_path.resolve()))

        pair_payload = _build_interleaved_pair_summary(
            workload,
            args.left_template,
            left_eval,
            left_samples,
            args.right_template,
            right_eval,
            right_samples,
            left_payload_paths=left_payload_paths,
            right_payload_paths=right_payload_paths,
        )

    pair_json_path = outdir / f"{manifest_stem}.{args.left_template}_vs_{args.right_template}.pair_summary.json"
    _dump_json(pair_json_path, pair_payload)

    pair_md_path = outdir / f"{manifest_stem}.{args.left_template}_vs_{args.right_template}.pair_summary.md"
    _write_pair_markdown(pair_md_path, summary_path=summary_path, pair_payload=pair_payload)

    if args.pair_mode == "sequential":
        for payload_path in pair_payload["payload_paths"]["left"] + pair_payload["payload_paths"]["right"]:
            print(f"Wrote {payload_path}")
    else:
        print(f"Wrote {len(pair_payload['payload_paths']['left'])} left block payloads")
        print(f"Wrote {len(pair_payload['payload_paths']['right'])} right block payloads")
    print(f"Wrote {pair_json_path}")
    print(f"Wrote {pair_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
