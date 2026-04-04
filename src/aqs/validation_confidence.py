from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

CONFIDENCE_VERSION = "aqs.validation_confidence.v1"
NEAR_TIE_ABS_S = 0.001
NEAR_TIE_REL = 0.03


def is_near_tie(gap_s: float | None, gap_pct: float | None) -> bool:
    if gap_s is not None and float(gap_s) <= NEAR_TIE_ABS_S:
        return True
    if gap_pct is not None and float(gap_pct) <= NEAR_TIE_REL:
        return True
    return False


def pair_lookup_key(workload_id: str | None, template_a: str | None, template_b: str | None) -> tuple[str, tuple[str, str]] | None:
    if not workload_id or not template_a or not template_b:
        return None
    return str(workload_id), tuple(sorted((str(template_a), str(template_b))))


def build_replicate_lookup(pair_payloads: list[dict[str, Any]]) -> dict[tuple[str, tuple[str, str]], dict[str, Any]]:
    lookup: dict[tuple[str, tuple[str, str]], dict[str, Any]] = {}
    for payload in pair_payloads:
        key = pair_lookup_key(
            payload.get("workload_id"),
            payload.get("left_template"),
            payload.get("right_template"),
        )
        if key is None:
            continue
        uncertainty = payload.get("uncertainty_band_s")
        lookup[key] = {
            "uncertainty_band_s": float(uncertainty) if uncertainty is not None else None,
            "conclusion": payload.get("conclusion"),
            "source": payload.get("source") or "external_pair_summary",
        }
    return lookup


def _candidate_payload(evaluation: dict[str, Any]) -> dict[str, Any]:
    payload = evaluation.get("candidate")
    if isinstance(payload, dict):
        return payload
    return evaluation


def _template_name(evaluation: dict[str, Any]) -> str | None:
    template_name = _candidate_payload(evaluation).get("template_name")
    return str(template_name) if template_name is not None else None


def _objective_value(objective: str, evaluation: dict[str, Any]) -> float | None:
    if not evaluation or evaluation.get("status") != "success":
        return None
    if objective == "steady_state":
        value = evaluation.get("observed_iter_ms")
    elif objective == "gpu_seconds":
        value = evaluation.get("observed_gpu_seconds")
    else:
        value = evaluation.get("observed_ttfr_s")
    return float(value) if value is not None else None


def _selected_gap_metrics(objective: str, selected_value: float | None, winner_value: float | None) -> tuple[float | None, float | None]:
    if selected_value is None or winner_value is None:
        return None, None
    gap = max(selected_value - winner_value, 0.0)
    if winner_value <= 0.0:
        return gap, None
    return gap, gap / winner_value


def _embedded_uncertainty_s(evaluation: dict[str, Any]) -> float | None:
    run = evaluation.get("execution_run") or {}
    details = run.get("failure_detail_json") or {}
    calibration = details.get("calibration_ttfr") or {}
    stats = calibration.get("ttfr_stats") or {}
    stdev = stats.get("stdev")
    return float(stdev) if stdev is not None else None


def _replicate_uncertainty_band_s(
    workload: dict[str, Any],
    winner_eval: dict[str, Any] | None,
    runner_up_eval: dict[str, Any] | None,
    replicate_lookup: dict[tuple[str, tuple[str, str]], dict[str, Any]] | None,
) -> tuple[float | None, str | None, str | None]:
    embedded = [value for value in (_embedded_uncertainty_s(winner_eval or {}), _embedded_uncertainty_s(runner_up_eval or {})) if value is not None]
    if replicate_lookup and winner_eval and runner_up_eval:
        key = pair_lookup_key(workload.get("workload_id"), _template_name(winner_eval), _template_name(runner_up_eval))
        if key is not None:
            payload = replicate_lookup.get(key)
            if payload and payload.get("uncertainty_band_s") is not None:
                return (
                    float(payload["uncertainty_band_s"]),
                    str(payload.get("source") or "external_pair_summary"),
                    str(payload.get("conclusion") or ""),
                )
    if embedded:
        return max(embedded), "embedded_calibration_ttfr", None
    return None, None, None


def annotate_workload_confidence(
    workload: dict[str, Any],
    *,
    objective: str,
    replicate_lookup: dict[tuple[str, tuple[str, str]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    evaluations = list(workload.get("evaluations") or [])
    successful = [evaluation for evaluation in evaluations if evaluation.get("status") == "success"]
    ranked = sorted(
        successful,
        key=lambda evaluation: float(_objective_value(objective, evaluation) or float("inf")),
    )
    winner_eval = ranked[0] if ranked else None
    runner_up_eval = ranked[1] if len(ranked) > 1 else None
    selected_plan_id = workload.get("selected_plan_id")
    selected_eval = next((evaluation for evaluation in evaluations if evaluation.get("plan_id") == selected_plan_id), None)

    winner_value = _objective_value(objective, winner_eval or {})
    runner_up_value = _objective_value(objective, runner_up_eval or {})
    selected_value = _objective_value(objective, selected_eval or {})

    winner_gap_s = None
    winner_gap_pct = None
    if winner_value is not None and runner_up_value is not None:
        winner_gap_s = max(runner_up_value - winner_value, 0.0)
        winner_gap_pct = winner_gap_s / winner_value if winner_value > 0.0 else None

    selected_gap_s, selected_gap_pct = _selected_gap_metrics(objective, selected_value, winner_value)
    selected_matches_winner = bool(
        winner_eval
        and selected_eval
        and selected_eval.get("status") == "success"
        and selected_eval.get("plan_id") == winner_eval.get("plan_id")
    )

    top1_within_1ms = bool(selected_gap_s is not None and selected_gap_s <= NEAR_TIE_ABS_S)
    top1_within_3pct = bool(selected_gap_pct is not None and selected_gap_pct <= NEAR_TIE_REL)

    replicate_uncertainty_band_s, replicate_support, replicate_conclusion = _replicate_uncertainty_band_s(
        workload,
        winner_eval,
        runner_up_eval,
        replicate_lookup,
    )

    if winner_eval is None:
        selection_confidence = "low"
        confidence_reason = "no feasible winner is available in the stored evaluations"
    elif runner_up_eval is None:
        selection_confidence = "medium"
        confidence_reason = "only one feasible evaluation is available, so winner margin confidence is limited"
    elif is_near_tie(winner_gap_s, winner_gap_pct):
        selection_confidence = "low"
        confidence_reason = "winner and runner-up stay inside the near-tie band"
    elif (not selected_matches_winner) and is_near_tie(selected_gap_s, selected_gap_pct):
        selection_confidence = "low"
        confidence_reason = "the selected plan misses the winner only inside the near-tie band"
    elif replicate_conclusion == "winner_flipped_vs_single_shot":
        selection_confidence = "medium"
        confidence_reason = "replicate medians flip the stored single-shot winner, so the baseline winner is not stable enough for high confidence"
    elif replicate_uncertainty_band_s is None:
        selection_confidence = "medium"
        confidence_reason = "winner margin clears the near-tie band, but no replicate uncertainty is available"
    elif winner_gap_s is not None and winner_gap_s <= replicate_uncertainty_band_s:
        selection_confidence = "medium"
        confidence_reason = "winner margin clears the near-tie band but not the observed replicate uncertainty band"
    else:
        selection_confidence = "high"
        confidence_reason = "winner margin clears both the near-tie band and the observed replicate uncertainty band"

    return {
        "selected_template": _template_name(selected_eval or {}),
        "winner_gap_s": round(winner_gap_s, 6) if winner_gap_s is not None else None,
        "winner_gap_pct": round(winner_gap_pct, 6) if winner_gap_pct is not None else None,
        "winner_template": _template_name(winner_eval or {}),
        "runner_up_template": _template_name(runner_up_eval or {}),
        "top1_within_1ms": top1_within_1ms,
        "top1_within_3pct": top1_within_3pct,
        "selection_confidence": selection_confidence,
        "selection_confidence_reason": confidence_reason,
        "replicate_uncertainty_band_s": round(replicate_uncertainty_band_s, 6) if replicate_uncertainty_band_s is not None else None,
        "replicate_uncertainty_source": replicate_support,
        "replicate_conclusion": replicate_conclusion,
        "replicate_stability": replicate_conclusion,
        "selected_winner_gap_s": round(selected_gap_s, 6) if selected_gap_s is not None else None,
        "selected_winner_gap_pct": round(selected_gap_pct, 6) if selected_gap_pct is not None else None,
    }


def annotate_validation_results(
    results: list[dict[str, Any]],
    *,
    objective: str,
    replicate_lookup: dict[tuple[str, tuple[str, str]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    annotated_results: list[dict[str, Any]] = []
    confidence_counts = Counter({"low": 0, "medium": 0, "high": 0})
    top1_within_1ms_hits = 0
    top1_within_3pct_hits = 0
    high_confidence_hits = 0
    high_confidence_total = 0

    for workload in results:
        annotation = annotate_workload_confidence(
            workload,
            objective=objective,
            replicate_lookup=replicate_lookup,
        )
        annotated = {**workload, **annotation}
        annotated_results.append(annotated)
        confidence_counts[annotation["selection_confidence"]] += 1
        top1_within_1ms_hits += 1 if annotation["top1_within_1ms"] else 0
        top1_within_3pct_hits += 1 if annotation["top1_within_3pct"] else 0
        if annotation["selection_confidence"] == "high":
            high_confidence_total += 1
            if workload.get("selected_plan_id") == workload.get("oracle_best_plan_id"):
                high_confidence_hits += 1

    workload_count = len(annotated_results)
    return {
        "results": annotated_results,
        "confidence_version": CONFIDENCE_VERSION,
        "top1_within_1ms_rate": round(top1_within_1ms_hits / max(workload_count, 1), 6),
        "top1_within_3pct_rate": round(top1_within_3pct_hits / max(workload_count, 1), 6),
        "high_confidence_top1_accuracy": (
            round(high_confidence_hits / high_confidence_total, 6)
            if high_confidence_total
            else None
        ),
        "selection_confidence_counts": {
            "low": int(confidence_counts["low"]),
            "medium": int(confidence_counts["medium"]),
            "high": int(confidence_counts["high"]),
        },
    }


def annotate_validation_summary(
    summary: dict[str, Any],
    *,
    replicate_lookup: dict[tuple[str, tuple[str, str]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    annotated = annotate_validation_results(
        list(summary.get("results") or []),
        objective=str(summary.get("objective") or "ttfr"),
        replicate_lookup=replicate_lookup,
    )
    return {
        **summary,
        **{key: value for key, value in annotated.items() if key != "results"},
        "results": annotated["results"],
    }


def build_confidence_summary_payload(summary: dict[str, Any]) -> dict[str, Any]:
    results = []
    for row in summary.get("results") or []:
        results.append(
            {
                "workload_id": row.get("workload_id"),
                "manifest_path": row.get("manifest_path"),
                "family_id": row.get("family_id"),
                "split_tag": row.get("split_tag"),
                "repeat_count_hint": row.get("repeat_count_hint"),
                "selected_plan_id": row.get("selected_plan_id"),
                "oracle_best_plan_id": row.get("oracle_best_plan_id"),
                "selected_template": row.get("selected_template"),
                "winner_template": row.get("winner_template"),
                "runner_up_template": row.get("runner_up_template"),
                "winner_gap_s": row.get("winner_gap_s"),
                "winner_gap_pct": row.get("winner_gap_pct"),
                "top1_within_1ms": row.get("top1_within_1ms"),
                "top1_within_3pct": row.get("top1_within_3pct"),
                "selection_confidence": row.get("selection_confidence"),
                "selection_confidence_reason": row.get("selection_confidence_reason"),
                "replicate_stability": row.get("replicate_stability"),
                "replicate_uncertainty_band_s": row.get("replicate_uncertainty_band_s"),
                "selected_winner_gap_s": row.get("selected_winner_gap_s"),
                "selected_winner_gap_pct": row.get("selected_winner_gap_pct"),
            }
        )

    return {
        "validation_run_id": summary.get("validation_run_id"),
        "benchmark_manifest": summary.get("benchmark_manifest"),
        "dataset_name": summary.get("dataset_name"),
        "objective": summary.get("objective"),
        "evaluation_source": summary.get("evaluation_source"),
        "summary_path": summary.get("summary_path"),
        "confidence_version": summary.get("confidence_version"),
        "workload_count": summary.get("workload_count"),
        "heldout_workload_count": summary.get("heldout_workload_count"),
        "top1_accuracy": summary.get("top1_accuracy"),
        "mean_regret": summary.get("mean_regret"),
        "heldout_mean_regret": summary.get("heldout_mean_regret"),
        "top1_within_1ms_rate": summary.get("top1_within_1ms_rate"),
        "top1_within_3pct_rate": summary.get("top1_within_3pct_rate"),
        "high_confidence_top1_accuracy": summary.get("high_confidence_top1_accuracy"),
        "selection_confidence_counts": summary.get("selection_confidence_counts"),
        "warnings": summary.get("warnings") or [],
        "results": results,
    }


def build_confidence_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Validation Confidence Summary",
        "",
        f"- Source summary: `{payload.get('summary_path')}`",
        f"- Dataset: `{payload.get('dataset_name')}`",
        f"- Confidence version: `{payload.get('confidence_version')}`",
        f"- Workloads: `{payload.get('workload_count')}`",
        f"- top1_accuracy: `{payload.get('top1_accuracy')}`",
        f"- mean_regret: `{payload.get('mean_regret')}`",
        f"- heldout_mean_regret: `{payload.get('heldout_mean_regret')}`",
        f"- top1_within_1ms_rate: `{payload.get('top1_within_1ms_rate')}`",
        f"- top1_within_3pct_rate: `{payload.get('top1_within_3pct_rate')}`",
        f"- high_confidence_top1_accuracy: `{payload.get('high_confidence_top1_accuracy')}`",
        f"- selection_confidence_counts: `{payload.get('selection_confidence_counts')}`",
        "",
        "## Workloads",
        "",
        "| Workload | Selected | Winner | Runner-up | Winner gap (ms) | top1<=1ms | top1<=3pct | Confidence | Replicate Stability |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for workload in payload.get("results") or []:
        lines.append(
            f"| `{Path(str(workload.get('manifest_path') or '')).name}` | "
            f"`{workload.get('selected_template')}` | "
            f"`{workload.get('winner_template')}` | "
            f"`{workload.get('runner_up_template')}` | "
            f"{((workload.get('winner_gap_s') or 0.0) * 1000.0):.3f} | "
            f"`{workload.get('top1_within_1ms')}` | "
            f"`{workload.get('top1_within_3pct')}` | "
            f"`{workload.get('selection_confidence')}` | "
            f"`{workload.get('replicate_stability')}` |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `top1_within_1ms_rate` and `top1_within_3pct_rate` are additive to `top1_accuracy`; they do not replace it.",
            "- `selection_confidence_counts` bucket workloads as low / medium / high using the current near-tie thresholds `0.001 s` or `3%`.",
            f"- Heldout metrics remain descriptive while `heldout_workload_count={payload.get('heldout_workload_count')}` is below `5`.",
        ]
    )
    warnings = payload.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines) + "\n"


def write_confidence_summary_artifacts(summary: dict[str, Any], outdir: str | Path) -> dict[str, str]:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    payload = build_confidence_summary_payload(summary)
    json_path = outdir / "confidence_summary.json"
    md_path = outdir / "confidence_summary.md"
    summary_with_paths = {
        **summary,
        "confidence_summary_json_path": str(json_path),
        "confidence_summary_path": str(md_path),
    }
    json_path.write_text(json.dumps(summary_with_paths, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(build_confidence_summary_markdown(payload), encoding="utf-8")
    return {
        "confidence_summary_json_path": str(json_path),
        "confidence_summary_path": str(md_path),
    }


__all__ = [
    "CONFIDENCE_VERSION",
    "NEAR_TIE_ABS_S",
    "NEAR_TIE_REL",
    "annotate_validation_results",
    "annotate_validation_summary",
    "annotate_workload_confidence",
    "build_confidence_summary_markdown",
    "build_confidence_summary_payload",
    "build_replicate_lookup",
    "is_near_tie",
    "pair_lookup_key",
    "write_confidence_summary_artifacts",
]
