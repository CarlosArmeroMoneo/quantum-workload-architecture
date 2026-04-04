from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aqs.arch import analyze_execution_payload  # noqa: E402


CSV_FIELDS = [
    "dataset_name",
    "workload_id",
    "manifest_path",
    "family_id",
    "split_tag",
    "repeat_count",
    "template_name",
    "oracle_template",
    "recommendation_rank",
    "oracle_rank",
    "selected_flag",
    "oracle_best_flag",
    "predicted_ttfr_s",
    "observed_ttfr_s",
    "ttfr_error_s",
    "ttfr_error_pct",
    "predicted_iter_ms",
    "observed_iter_ms",
    "iter_error_ms",
    "planner_phase_time_s",
    "setup_phase_time_s",
    "first_contract_time_s",
    "warm_median_ms",
    "planner_share_pct",
    "setup_share_pct",
    "regret_s",
    "normalized_regret",
    "primary_architecture_family",
    "failure_flag",
    "failure_reason",
    "accuracy_status",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _round_or_none(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _find_eval(workload: dict[str, Any], plan_id: str | None) -> dict[str, Any] | None:
    if not plan_id:
        return None
    for evaluation in workload.get("evaluations", []):
        if evaluation.get("plan_id") == plan_id:
            return evaluation
    return None


def _build_arch_payload(summary: dict[str, Any], workload: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    run = evaluation.get("execution_run") or {}
    return {
        "workload_id": workload.get("workload_id"),
        "family_id": workload.get("family_id"),
        "repeat_count_hint": workload.get("repeat_count_hint") or 1,
        "selected_plan": evaluation.get("candidate") or {},
        "execution_run": run,
        "profile_summary": evaluation.get("profile_summary") or run.get("profile_summary") or {},
        "probe": {"raw_info_json": {"family_id": workload.get("family_id")}},
        "system_manifest": summary.get("system_manifest") or {},
    }


def _run_arch(summary: dict[str, Any], workload: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    try:
        return analyze_execution_payload(_build_arch_payload(summary, workload, evaluation))
    except Exception as exc:
        return {"nominations": [], "analysis_error": str(exc)}


def _primary_arch_family(analysis: dict[str, Any]) -> str:
    nominations = analysis.get("nominations") or []
    if not nominations:
        return "none"
    return str(nominations[0].get("bottleneck_family") or "none")


def _phase_breakdown(run: dict[str, Any]) -> dict[str, float | None]:
    details = run.get("failure_detail_json") or {}
    phase_times = details.get("phase_times") or {}
    planner_phase = float(phase_times.get("contract_path") or 0.0) + float(phase_times.get("autotune") or 0.0)
    setup_phase = (
        float(phase_times.get("load_circuit") or 0.0)
        + float(phase_times.get("convert_to_einsum") or 0.0)
        + float(phase_times.get("postprocess") or 0.0)
    )
    first_contract = float(phase_times.get("contract_first") or details.get("first_contract_time_s") or 0.0)
    warm_samples = [float(value) for value in details.get("warm_contract_times_ms") or []]
    warm_median = statistics.median(warm_samples) if warm_samples else None
    total_phase = sum(float(value or 0.0) for value in phase_times.values())
    planner_share = (100.0 * planner_phase / total_phase) if total_phase > 0.0 else None
    setup_share = (100.0 * setup_phase / total_phase) if total_phase > 0.0 else None
    return {
        "planner_phase_time_s": _round_or_none(planner_phase, 9),
        "setup_phase_time_s": _round_or_none(setup_phase, 9),
        "first_contract_time_s": _round_or_none(first_contract, 9),
        "warm_median_ms": _round_or_none(warm_median, 6),
        "planner_share_pct": _round_or_none(planner_share, 6),
        "setup_share_pct": _round_or_none(setup_share, 6),
    }


def _failure_reason(evaluation: dict[str, Any]) -> str | None:
    details = evaluation.get("details_json") or {}
    for key in ("reason", "reason_code"):
        value = details.get(key)
        if value:
            return str(value)
    run = evaluation.get("execution_run") or {}
    run_details = run.get("failure_detail_json") or {}
    for key in ("reason", "reason_code"):
        value = run_details.get(key)
        if value:
            return str(value)
    return None


def _dataset_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for workload in summary.get("results", []):
        oracle_eval = _find_eval(workload, workload.get("oracle_best_plan_id"))
        oracle_template = (oracle_eval or {}).get("candidate", {}).get("template_name")
        for evaluation in workload.get("evaluations", []):
            run = evaluation.get("execution_run") or {}
            candidate = evaluation.get("candidate") or {}
            analysis = _run_arch(summary, workload, evaluation) if run else {"nominations": []}
            selected_flag = evaluation.get("plan_id") == workload.get("selected_plan_id")
            oracle_best_flag = evaluation.get("plan_id") == workload.get("oracle_best_plan_id")
            predicted_ttfr = candidate.get("predicted_ttfr_s")
            observed_ttfr = run.get("ttfr_s")
            predicted_iter = candidate.get("predicted_iter_ms")
            observed_iter = run.get("steady_iter_ms")
            ttfr_error = None
            ttfr_error_pct = None
            if predicted_ttfr is not None and observed_ttfr is not None:
                ttfr_error = float(observed_ttfr) - float(predicted_ttfr)
                if float(predicted_ttfr) != 0.0:
                    ttfr_error_pct = 100.0 * ttfr_error / float(predicted_ttfr)
            iter_error = None
            if predicted_iter is not None and observed_iter is not None:
                iter_error = float(observed_iter) - float(predicted_iter)

            phase = _phase_breakdown(run)
            row = {
                "dataset_name": summary.get("dataset_name"),
                "workload_id": workload.get("workload_id"),
                "manifest_path": workload.get("manifest_path"),
                "family_id": workload.get("family_id"),
                "split_tag": workload.get("split_tag"),
                "repeat_count": int(workload.get("repeat_count_hint") or 1),
                "template_name": candidate.get("template_name"),
                "oracle_template": oracle_template,
                "recommendation_rank": candidate.get("recommendation_rank"),
                "oracle_rank": evaluation.get("oracle_rank"),
                "selected_flag": selected_flag,
                "oracle_best_flag": oracle_best_flag,
                "predicted_ttfr_s": _round_or_none(predicted_ttfr, 6),
                "observed_ttfr_s": _round_or_none(observed_ttfr, 9),
                "ttfr_error_s": _round_or_none(ttfr_error, 6),
                "ttfr_error_pct": _round_or_none(ttfr_error_pct, 6),
                "predicted_iter_ms": _round_or_none(predicted_iter, 6),
                "observed_iter_ms": _round_or_none(observed_iter, 6),
                "iter_error_ms": _round_or_none(iter_error, 6),
                **phase,
                "regret_s": _round_or_none(workload.get("regret"), 6) if selected_flag else (0.0 if oracle_best_flag else None),
                "normalized_regret": _round_or_none(workload.get("normalized_regret"), 6) if selected_flag else (0.0 if oracle_best_flag else None),
                "primary_architecture_family": _primary_arch_family(analysis),
                "failure_flag": evaluation.get("status") != "success",
                "failure_reason": _failure_reason(evaluation),
                "accuracy_status": (evaluation.get("accuracy_eval") or {}).get("status"),
            }
            rows.append(row)
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in CSV_FIELDS})


def _near_tie(row: dict[str, Any]) -> bool:
    regret_s = row.get("regret_s")
    normalized_regret = row.get("normalized_regret")
    if regret_s is not None and float(regret_s) <= 0.001:
        return True
    if normalized_regret is not None and float(normalized_regret) <= 0.03:
        return True
    return False


def _dataset_interpretation(dataset_name: str, rows: list[dict[str, Any]], validation_arch: dict[str, Any] | None = None) -> list[str]:
    selected_rows = [row for row in rows if row["selected_flag"]]
    misses = [row for row in selected_rows if (row.get("regret_s") or 0.0) > 0.0]
    low_repeat = sum(1 for row in misses if int(row["repeat_count"]) <= 4)
    high_repeat = sum(1 for row in misses if int(row["repeat_count"]) > 4)
    pair_counts = Counter(f"{row['template_name']} -> {row['oracle_template']}" for row in misses)
    planner_setup_values = [
        float(row.get("planner_phase_time_s") or 0.0) + float(row.get("setup_phase_time_s") or 0.0)
        for row in misses
    ]
    first_contract_values = [float(row.get("first_contract_time_s") or 0.0) for row in misses]
    near_ties = sum(1 for row in misses if _near_tie(row))
    clear_misses = len(misses) - near_ties

    if planner_setup_values and first_contract_values:
        dominant_error = (
            "planning/setup dominates"
            if statistics.median(planner_setup_values) >= statistics.median(first_contract_values)
            else "steady contraction dominates"
        )
    else:
        dominant_error = "insufficient miss rows to classify"

    lines = [
        f"## `{dataset_name}`",
        "",
        f"- Wrong-pick selected rows: `{len(misses)}` of `{len(selected_rows)}`",
        f"- Are misses concentrated at repeat counts 1-4? `{low_repeat}` yes vs `{high_repeat}` above 4",
        f"- Are misses mostly balanced vs deep_search? `{dict(pair_counts) if pair_counts else {}}`",
        f"- Is the dominant error in planning/setup or steady contraction? `{dominant_error}`",
        f"- Are wrong picks near-ties or clear misses? `{near_ties}` near-ties vs `{clear_misses}` clear misses",
    ]
    if validation_arch:
        ranked = validation_arch.get("ranked_bottleneck_families") or []
        families = [entry.get("bottleneck_family") for entry in ranked[:3] if entry.get("bottleneck_family")]
        lines.append(f"- Selected-run aggregate from validation_arch: `{families}`")
    lines.extend(
        [
            "",
            "| Workload | Repeat | Selected | Oracle | Regret (ms) | Primary Architecture Family |",
            "| --- | ---: | --- | --- | ---: | --- |",
        ]
    )
    for row in misses:
        workload_name = Path(str(row["manifest_path"])).name
        regret_ms = float(row["regret_s"] or 0.0) * 1000.0
        lines.append(
            f"| `{workload_name}` | {row['repeat_count']} | `{row['template_name']}` | `{row['oracle_template']}` | "
            f"{regret_ms:.3f} | `{row['primary_architecture_family']}` |"
        )
    if not misses:
        lines.append("| none |  |  |  |  |  |")
    lines.append("")
    return lines


def _write_markdown(path: Path, *, rows: list[dict[str, Any]], validation_arch_by_dataset: dict[str, dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["dataset_name"])].append(row)

    lines = [
        "# Validation Residual Export",
        "",
        f"- Candidate rows: `{len(rows)}`",
        f"- Datasets: `{sorted(grouped)}`",
        "",
        "## Interpretation",
        "",
    ]
    for dataset_name in sorted(grouped):
        lines.extend(
            _dataset_interpretation(
                dataset_name,
                grouped[dataset_name],
                validation_arch=validation_arch_by_dataset.get(dataset_name),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export candidate-level residuals from measured-validation summaries")
    parser.add_argument("--summary", action="append", required=True, help="Path to a measured-validation summary.json; may be provided multiple times")
    parser.add_argument("--validation-arch", action="append", default=[], help="Optional validation_arch.json files for markdown context")
    parser.add_argument("--outdir", required=True, help="Output directory")
    args = parser.parse_args(argv)

    summaries = [_load_json(Path(path).resolve()) for path in args.summary]
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        rows.extend(_dataset_rows(summary))

    validation_arch_by_dataset: dict[str, dict[str, Any]] = {}
    for path in args.validation_arch:
        payload = _load_json(Path(path).resolve())
        dataset_name = str(payload.get("dataset_name") or "")
        if dataset_name:
            validation_arch_by_dataset[dataset_name] = payload

    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / "validation_residuals.csv"
    md_path = outdir / "validation_residuals.md"
    _write_csv(csv_path, rows)
    _write_markdown(md_path, rows=rows, validation_arch_by_dataset=validation_arch_by_dataset)

    print(json.dumps(
        {
            "summaries": [str(Path(path).resolve()) for path in args.summary],
            "csv": csv_path.as_posix(),
            "md": md_path.as_posix(),
            "row_count": len(rows),
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
