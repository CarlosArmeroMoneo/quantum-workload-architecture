from __future__ import annotations

import argparse
import json
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


def _pair_summary(
    workload: dict[str, Any],
    left_template: str,
    left_eval: dict[str, Any],
    left_payload: dict[str, Any],
    right_template: str,
    right_eval: dict[str, Any],
    right_payload: dict[str, Any],
    *,
    outdir: Path,
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

    payload = {
        "source": "targeted_ttfr_replicates",
        "workload_id": workload.get("workload_id"),
        "manifest_path": workload.get("manifest_path"),
        "family_id": workload.get("family_id"),
        "repeat_count_hint": workload.get("repeat_count_hint"),
        "pair_lookup_key": (
            {
                "workload_id": pair_lookup_key(workload.get("workload_id"), left_template, right_template)[0],
                "templates": list(pair_lookup_key(workload.get("workload_id"), left_template, right_template)[1]),
            }
            if pair_lookup_key(workload.get("workload_id"), left_template, right_template) is not None
            else None
        ),
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
        "conclusion": conclusion,
        "payload_paths": {
            "left": str((outdir / f"{Path(str(workload['manifest_path'])).stem}.{left_template}.execute.json").resolve()),
            "right": str((outdir / f"{Path(str(workload['manifest_path'])).stem}.{right_template}.execute.json").resolve()),
        },
    }
    return payload


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
    args = parser.parse_args(argv)

    summary = _load_json(Path(args.summary))
    workload = _find_workload(summary, args.manifest)
    left_eval = _find_evaluation(workload, args.left_template)
    right_eval = _find_evaluation(workload, args.right_template)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    plan_dir = outdir / "plan_overrides"
    plan_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = str(workload["manifest_path"])
    manifest_stem = Path(manifest_path).stem
    left_plan_path = plan_dir / f"{manifest_stem}.{args.left_template}.json"
    right_plan_path = plan_dir / f"{manifest_stem}.{args.right_template}.json"
    _dump_json(left_plan_path, dict(left_eval.get("candidate") or {}))
    _dump_json(right_plan_path, dict(right_eval.get("candidate") or {}))

    left_payload = execute_selected_plan(
        manifest_path,
        args.system_manifest,
        objective=args.objective,
        probe_strategy=args.probe_strategy,
        planner_budget=args.planner_budget,
        allow_distributed=False,
        measurement_repeats=args.measurement_repeats,
        ttfr_repeats=args.ttfr_repeats,
        execution_intent=args.execution_intent,
        plan_json_path=str(left_plan_path),
    )
    right_payload = execute_selected_plan(
        manifest_path,
        args.system_manifest,
        objective=args.objective,
        probe_strategy=args.probe_strategy,
        planner_budget=args.planner_budget,
        allow_distributed=False,
        measurement_repeats=args.measurement_repeats,
        ttfr_repeats=args.ttfr_repeats,
        execution_intent=args.execution_intent,
        plan_json_path=str(right_plan_path),
    )

    left_payload_path = outdir / f"{manifest_stem}.{args.left_template}.execute.json"
    right_payload_path = outdir / f"{manifest_stem}.{args.right_template}.execute.json"
    _dump_json(left_payload_path, left_payload)
    _dump_json(right_payload_path, right_payload)

    pair_payload = _pair_summary(
        workload,
        args.left_template,
        left_eval,
        left_payload,
        args.right_template,
        right_eval,
        right_payload,
        outdir=outdir,
    )
    pair_json_path = outdir / f"{manifest_stem}.{args.left_template}_vs_{args.right_template}.pair_summary.json"
    _dump_json(pair_json_path, pair_payload)

    pair_md_path = outdir / f"{manifest_stem}.{args.left_template}_vs_{args.right_template}.pair_summary.md"
    lines = [
        "# Targeted TTFR Replicate Pair Summary",
        "",
        f"- Source summary: `{Path(args.summary).resolve()}`",
        f"- Manifest: `{manifest_path}`",
        f"- Pair: `{args.left_template}` vs `{args.right_template}`",
        f"- Baseline single-shot winner: `{pair_payload['baseline_winner_template']}`",
        f"- Replicate median winner: `{pair_payload['replicate_winner_template']}`",
        f"- Winner gap: `{pair_payload['winner_gap_s'] * 1000.0:.3f} ms`",
        f"- Uncertainty band: `{pair_payload['uncertainty_band_s'] * 1000.0:.3f} ms`",
        f"- Conclusion: `{pair_payload['conclusion']}`",
        "",
        "## Pair Table",
        "",
        "| Template | Baseline TTFR (ms) | Replicate median TTFR (ms) |",
        "| --- | ---: | ---: |",
        f"| `{args.left_template}` | {pair_payload['baseline_left_ttfr_s'] * 1000.0:.3f} | {pair_payload['replicate_left_median_ttfr_s'] * 1000.0:.3f} |",
        f"| `{args.right_template}` | {pair_payload['baseline_right_ttfr_s'] * 1000.0:.3f} | {pair_payload['replicate_right_median_ttfr_s'] * 1000.0:.3f} |",
    ]
    pair_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {left_payload_path}")
    print(f"Wrote {right_payload_path}")
    print(f"Wrote {pair_json_path}")
    print(f"Wrote {pair_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
