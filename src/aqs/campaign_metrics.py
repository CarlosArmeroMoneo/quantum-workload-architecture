from __future__ import annotations

import math
from collections import Counter
from typing import Any

from .planner import DEFAULT_PLANNER_POLICY


REPEAT_ROI_ANALYSIS_VERSION = "aqs.repeat_roi.v1"


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _safe_pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0.0:
        return None
    return round((numerator / denominator) * 100.0, 6)


def build_cell_aggregates(cell_specs: list[dict[str, Any]], run_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_by_cell: dict[str, list[dict[str, Any]]] = {}
    for row in run_rows:
        rows_by_cell.setdefault(str(row["cell_id"]), []).append(row)

    aggregates: list[dict[str, Any]] = []
    for cell in sorted(cell_specs, key=lambda item: item["cell_id"]):
        rows = rows_by_cell.get(str(cell["cell_id"]), [])
        successful = [row for row in rows if row.get("status") == "success"]
        status_counts = dict(sorted(Counter(str(row.get("status") or "unknown") for row in rows).items()))
        params = cell["parameter_json"]
        plan = cell["plan_json"]
        mean_wall_s = _mean(successful, "wall_s")
        repeat_count = int(params.get("repeat_count_hint", 1))
        aggregate = {
            "cell_id": cell["cell_id"],
            "campaign_id": cell["campaign_id"],
            "campaign_name": cell["campaign_name"],
            "manifest_path": cell["manifest_path"],
            "workload_id": cell["workload_id"],
            "plan_id": plan["plan_id"],
            "planner_budget": params.get("planner_budget"),
            "repeat_count_hint": repeat_count,
            "measurement_repeats": int(params.get("measurement_repeats", 3)),
            "autotune": bool(params.get("autotune", False)),
            "reuse_cache": bool(params.get("reuse_cache", False)),
            "run_count": len(rows),
            "success_count": len(successful),
            "status_counts": status_counts,
            "success_ratio_pct": _safe_pct(float(len(successful)), float(len(rows))) if rows else None,
            "predicted_ttfr_s": plan.get("predicted_ttfr_s"),
            "predicted_iter_ms": plan.get("predicted_iter_ms"),
            "predicted_gpu_seconds": plan.get("predicted_gpu_seconds"),
            "predicted_peak_gb": plan.get("predicted_peak_gb"),
            "mean_ttfr_s": _mean(successful, "ttfr_s"),
            "mean_steady_iter_ms": _mean(successful, "steady_iter_ms"),
            "mean_wall_s": mean_wall_s,
            "mean_gpu_seconds": _mean(successful, "gpu_seconds"),
            "mean_planner_share_pct": _mean(successful, "planner_share_pct"),
            "mean_launch_share_pct": _mean(successful, "launch_share_pct"),
            "mean_contract_share_pct": _mean(successful, "contract_share_pct"),
            "mean_per_repeat_wall_ms": round((mean_wall_s * 1000.0) / repeat_count, 6) if mean_wall_s is not None else None,
            "mean_planner_overhead_ms": round(
                (float(_mean(successful, "ttfr_s") or 0.0) * 1000.0) * (float(_mean(successful, "planner_share_pct") or 0.0) / 100.0),
                6,
            ) if successful else None,
            "execution_sources": sorted({str(row.get("execution_source") or "unknown") for row in rows}),
        }
        aggregates.append(aggregate)
    return aggregates


def build_repeat_roi_analysis(cell_aggregates: list[dict[str, Any]]) -> dict[str, Any]:
    baseline_no_opt: dict[tuple[Any, ...], dict[str, Any]] = {}
    baseline_repeat1: dict[tuple[Any, ...], dict[str, Any]] = {}
    for aggregate in cell_aggregates:
        no_opt_key = (
            aggregate["manifest_path"],
            aggregate["planner_budget"],
            aggregate["measurement_repeats"],
            aggregate["repeat_count_hint"],
        )
        if not aggregate["autotune"] and not aggregate["reuse_cache"]:
            baseline_no_opt[no_opt_key] = aggregate
        repeat1_key = (
            aggregate["manifest_path"],
            aggregate["planner_budget"],
            aggregate["measurement_repeats"],
            aggregate["autotune"],
            aggregate["reuse_cache"],
        )
        if aggregate["repeat_count_hint"] == 1:
            baseline_repeat1[repeat1_key] = aggregate

    findings: list[dict[str, Any]] = []
    positive_autotune: list[int] = []
    positive_reuse: list[int] = []
    for aggregate in cell_aggregates:
        no_opt_key = (
            aggregate["manifest_path"],
            aggregate["planner_budget"],
            aggregate["measurement_repeats"],
            aggregate["repeat_count_hint"],
        )
        repeat1_key = (
            aggregate["manifest_path"],
            aggregate["planner_budget"],
            aggregate["measurement_repeats"],
            aggregate["autotune"],
            aggregate["reuse_cache"],
        )
        baseline = baseline_no_opt.get(no_opt_key)
        repeat1 = baseline_repeat1.get(repeat1_key)
        steady_savings_ms = None
        ttfr_penalty_ms = None
        wall_delta_ms = None
        break_even_extra_repeats = None
        roi_label = "baseline"
        if baseline is not None and baseline["cell_id"] != aggregate["cell_id"]:
            steady_savings_ms = round(
                float(baseline.get("mean_steady_iter_ms") or 0.0) - float(aggregate.get("mean_steady_iter_ms") or 0.0),
                6,
            )
            ttfr_penalty_ms = round(
                (float(aggregate.get("mean_ttfr_s") or 0.0) - float(baseline.get("mean_ttfr_s") or 0.0)) * 1000.0,
                6,
            )
            wall_delta_ms = round(
                (float(aggregate.get("mean_wall_s") or 0.0) - float(baseline.get("mean_wall_s") or 0.0)) * 1000.0,
                6,
            )
            if steady_savings_ms > 0.0:
                break_even_extra_repeats = int(math.ceil(max(ttfr_penalty_ms or 0.0, 0.0) / steady_savings_ms))
                if max(aggregate["repeat_count_hint"] - 1, 0) >= break_even_extra_repeats and wall_delta_ms <= 0.0:
                    roi_label = "positive"
                elif wall_delta_ms > 0.0:
                    roi_label = "negative"
                else:
                    roi_label = "neutral"
            elif wall_delta_ms is not None and wall_delta_ms > 0.0:
                roi_label = "negative"
            else:
                roi_label = "neutral"
        amortized_wall_gain_pct = None
        if repeat1 is not None and repeat1.get("mean_per_repeat_wall_ms") not in {None, 0.0} and aggregate.get("mean_per_repeat_wall_ms") is not None:
            amortized_wall_gain_pct = round(
                (
                    (float(repeat1["mean_per_repeat_wall_ms"]) - float(aggregate["mean_per_repeat_wall_ms"]))
                    / float(repeat1["mean_per_repeat_wall_ms"])
                ) * 100.0,
                6,
            )
        finding = {
            "cell_id": aggregate["cell_id"],
            "manifest_path": aggregate["manifest_path"],
            "workload_id": aggregate["workload_id"],
            "planner_budget": aggregate["planner_budget"],
            "repeat_count_hint": aggregate["repeat_count_hint"],
            "measurement_repeats": aggregate["measurement_repeats"],
            "autotune": aggregate["autotune"],
            "reuse_cache": aggregate["reuse_cache"],
            "baseline_cell_id": baseline["cell_id"] if baseline is not None else None,
            "repeat1_cell_id": repeat1["cell_id"] if repeat1 is not None else None,
            "mean_ttfr_s": aggregate.get("mean_ttfr_s"),
            "mean_steady_iter_ms": aggregate.get("mean_steady_iter_ms"),
            "mean_wall_s": aggregate.get("mean_wall_s"),
            "mean_per_repeat_wall_ms": aggregate.get("mean_per_repeat_wall_ms"),
            "mean_planner_overhead_ms": aggregate.get("mean_planner_overhead_ms"),
            "steady_iter_savings_ms_vs_no_opt": steady_savings_ms,
            "ttfr_penalty_ms_vs_no_opt": ttfr_penalty_ms,
            "wall_delta_ms_vs_no_opt": wall_delta_ms,
            "amortized_wall_gain_pct_vs_repeat1": amortized_wall_gain_pct,
            "break_even_extra_repeats": break_even_extra_repeats,
            "roi_label": roi_label,
            "dry_run_only": all(source != "cuquantum_tensornet_gpu" for source in aggregate["execution_sources"]),
        }
        if roi_label == "positive" and aggregate["autotune"] and int(aggregate["repeat_count_hint"]) > 1:
            positive_autotune.append(int(aggregate["repeat_count_hint"]))
        if roi_label == "positive" and aggregate["reuse_cache"] and int(aggregate["repeat_count_hint"]) > 1:
            positive_reuse.append(int(aggregate["repeat_count_hint"]))
        findings.append(finding)

    findings.sort(
        key=lambda item: (
            item["workload_id"],
            item["planner_budget"] or "",
            int(item["repeat_count_hint"]),
            int(bool(item["autotune"])),
            int(bool(item["reuse_cache"])),
        )
    )
    suggested_policy: dict[str, Any] = {
        "confidence": "dry_run_structural_model_only",
        "current_defaults": dict(DEFAULT_PLANNER_POLICY),
    }
    if positive_autotune:
        suggested_policy["disable_autotune_below_repeat"] = min(positive_autotune)
    if positive_reuse:
        suggested_policy["disable_reuse_cache_below_repeat"] = min(positive_reuse)
    return {
        "analysis_version": REPEAT_ROI_ANALYSIS_VERSION,
        "dry_run_only": all(finding["dry_run_only"] for finding in findings),
        "finding_count": len(findings),
        "findings": findings,
        "positive_findings": [finding for finding in findings if finding["roi_label"] == "positive"],
        "suggested_policy_overrides": suggested_policy,
    }


def build_campaign_metrics(cell_specs: list[dict[str, Any]], run_rows: list[dict[str, Any]]) -> dict[str, Any]:
    cell_aggregates = build_cell_aggregates(cell_specs, run_rows)
    return {
        "cell_aggregates": cell_aggregates,
        "repeat_roi": build_repeat_roi_analysis(cell_aggregates),
    }


__all__ = [
    "REPEAT_ROI_ANALYSIS_VERSION",
    "build_campaign_metrics",
    "build_cell_aggregates",
    "build_repeat_roi_analysis",
]
