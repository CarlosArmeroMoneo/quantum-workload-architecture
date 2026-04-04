from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aqs.arch import analyze_execution_payload  # noqa: E402


CSV_FIELDS = [
    "workload_id",
    "manifest_path",
    "family_id",
    "split_tag",
    "repeat_count",
    "selected_plan_id",
    "oracle_best_plan_id",
    "selected_template",
    "oracle_template",
    "selected_primary_family",
    "oracle_primary_family",
    "selected_planner_roi_severity",
    "oracle_planner_roi_severity",
    "selected_launch_overhead_severity",
    "oracle_launch_overhead_severity",
    "selected_reuse_cache_severity",
    "oracle_reuse_cache_severity",
    "selected_memory_bandwidth_severity",
    "oracle_memory_bandwidth_severity",
    "selected_ttfr_s",
    "oracle_ttfr_s",
    "regret_s",
    "normalized_regret",
    "summary_diff_text",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_eval(workload: dict[str, Any], plan_id: str | None) -> dict[str, Any] | None:
    if not plan_id:
        return None
    for evaluation in workload.get("evaluations", []):
        if evaluation.get("plan_id") == plan_id:
            return evaluation
    return None


def _build_arch_payload(summary: dict[str, Any], workload: dict[str, Any], evaluation: dict[str, Any] | None) -> dict[str, Any] | None:
    if not evaluation:
        return None
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


def _run_arch(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {"nominations": []}
    try:
        return analyze_execution_payload(payload)
    except Exception as exc:
        return {
            "nominations": [],
            "analysis_error": str(exc),
        }


def _severity_map(analysis: dict[str, Any]) -> dict[str, float]:
    severities: dict[str, float] = {}
    for nomination in analysis.get("nominations", []):
        family = str(nomination.get("bottleneck_family") or "")
        if not family:
            continue
        severities[family] = float(nomination.get("severity_score") or 0.0)
    return severities


def _primary_family(analysis: dict[str, Any]) -> str:
    nominations = analysis.get("nominations") or []
    if not nominations:
        return "none"
    return str(nominations[0].get("bottleneck_family") or "none")


def _round_or_none(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _summary_diff_text(row: dict[str, Any]) -> str:
    parts: list[str] = []
    if row["selected_primary_family"] != row["oracle_primary_family"]:
        parts.append(
            f"primary family shifts {row['selected_primary_family']} -> {row['oracle_primary_family']}"
        )

    planner_delta = float(row["selected_planner_roi_severity"] or 0.0) - float(row["oracle_planner_roi_severity"] or 0.0)
    if planner_delta > 0.0:
        parts.append(f"oracle lowers planner_roi by {planner_delta:.3f}")
    elif planner_delta < 0.0:
        parts.append(f"oracle raises planner_roi by {abs(planner_delta):.3f}")

    launch_delta = float(row["selected_launch_overhead_severity"] or 0.0) - float(row["oracle_launch_overhead_severity"] or 0.0)
    if launch_delta > 0.0:
        parts.append(f"oracle lowers launch_overhead by {launch_delta:.3f}")
    elif launch_delta < 0.0:
        parts.append(f"oracle raises launch_overhead by {abs(launch_delta):.3f}")

    ttfr_gap = None
    if row["selected_ttfr_s"] is not None and row["oracle_ttfr_s"] is not None:
        ttfr_gap = float(row["selected_ttfr_s"]) - float(row["oracle_ttfr_s"])
    if ttfr_gap is not None:
        if ttfr_gap > 0.0:
            parts.append(f"oracle TTFR lower by {ttfr_gap * 1000.0:.3f} ms")
        elif ttfr_gap < 0.0:
            parts.append(f"selected TTFR lower by {abs(ttfr_gap) * 1000.0:.3f} ms")

    if not parts:
        return "selected and oracle analyses are materially similar"
    return "; ".join(parts)


def _compare_summary(summary: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    pattern_counter: Counter[str] = Counter()
    planner_roi_reductions = 0
    primary_family_shifts = 0

    for workload in summary.get("results", []):
        selected_eval = _find_eval(workload, workload.get("selected_plan_id"))
        oracle_eval = _find_eval(workload, workload.get("oracle_best_plan_id"))
        selected_arch = _run_arch(_build_arch_payload(summary, workload, selected_eval))
        oracle_arch = _run_arch(_build_arch_payload(summary, workload, oracle_eval))
        selected_severity = _severity_map(selected_arch)
        oracle_severity = _severity_map(oracle_arch)

        row = {
            "workload_id": workload.get("workload_id"),
            "manifest_path": workload.get("manifest_path"),
            "family_id": workload.get("family_id"),
            "split_tag": workload.get("split_tag"),
            "repeat_count": int(workload.get("repeat_count_hint") or 1),
            "selected_plan_id": workload.get("selected_plan_id"),
            "oracle_best_plan_id": workload.get("oracle_best_plan_id"),
            "selected_template": (selected_eval or {}).get("candidate", {}).get("template_name"),
            "oracle_template": (oracle_eval or {}).get("candidate", {}).get("template_name"),
            "selected_primary_family": _primary_family(selected_arch),
            "oracle_primary_family": _primary_family(oracle_arch),
            "selected_planner_roi_severity": _round_or_none(selected_severity.get("planner_roi"), 6) or 0.0,
            "oracle_planner_roi_severity": _round_or_none(oracle_severity.get("planner_roi"), 6) or 0.0,
            "selected_launch_overhead_severity": _round_or_none(selected_severity.get("launch_overhead"), 6) or 0.0,
            "oracle_launch_overhead_severity": _round_or_none(oracle_severity.get("launch_overhead"), 6) or 0.0,
            "selected_reuse_cache_severity": _round_or_none(selected_severity.get("reuse_cache"), 6) or 0.0,
            "oracle_reuse_cache_severity": _round_or_none(oracle_severity.get("reuse_cache"), 6) or 0.0,
            "selected_memory_bandwidth_severity": _round_or_none(selected_severity.get("memory_bandwidth"), 6) or 0.0,
            "oracle_memory_bandwidth_severity": _round_or_none(oracle_severity.get("memory_bandwidth"), 6) or 0.0,
            "selected_ttfr_s": _round_or_none((selected_eval or {}).get("execution_run", {}).get("ttfr_s"), 9),
            "oracle_ttfr_s": _round_or_none((oracle_eval or {}).get("execution_run", {}).get("ttfr_s"), 9),
            "regret_s": _round_or_none(workload.get("regret"), 6),
            "normalized_regret": _round_or_none(workload.get("normalized_regret"), 6),
        }
        row["summary_diff_text"] = _summary_diff_text(row)
        rows.append(row)

        if row["selected_primary_family"] != row["oracle_primary_family"]:
            primary_family_shifts += 1
        if row["oracle_planner_roi_severity"] < row["selected_planner_roi_severity"]:
            planner_roi_reductions += 1
        pattern_counter[row["summary_diff_text"]] += 1

    aggregate = {
        "summary_path": summary.get("benchmark_manifest"),
        "dataset_name": summary.get("dataset_name"),
        "workload_count": len(rows),
        "primary_family_shift_count": primary_family_shifts,
        "oracle_lowers_planner_roi_count": planner_roi_reductions,
        "selected_primary_families": Counter(row["selected_primary_family"] for row in rows),
        "oracle_primary_families": Counter(row["oracle_primary_family"] for row in rows),
        "top_patterns": pattern_counter.most_common(5),
    }
    return {"aggregate": aggregate, "rows": rows}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in CSV_FIELDS})


def _counter_to_lines(counter_payload: Counter[str]) -> list[str]:
    items = counter_payload.most_common()
    if not items:
        return ["- none"]
    return [f"- `{name}`: {count}" for name, count in items]


def _write_markdown(path: Path, *, summary_path: Path, summary: dict[str, Any], comparison: dict[str, Any]) -> None:
    aggregate = comparison["aggregate"]
    rows = comparison["rows"]
    selected_counter = Counter(row["selected_primary_family"] for row in rows)
    oracle_counter = Counter(row["oracle_primary_family"] for row in rows)
    pattern_lines = aggregate["top_patterns"] or []

    lines = [
        "# Selected vs Oracle Architecture Comparison",
        "",
        f"- Source summary: `{summary_path.as_posix()}`",
        f"- Dataset: `{summary.get('dataset_name')}`",
        f"- Workloads: `{aggregate['workload_count']}`",
        f"- Primary family shifts: `{aggregate['primary_family_shift_count']}`",
        f"- Oracle lowers `planner_roi`: `{aggregate['oracle_lowers_planner_roi_count']}`",
        "",
        "## Recurring Patterns",
        "",
        "Selected primary families:",
        * _counter_to_lines(selected_counter),
        "",
        "Oracle primary families:",
        * _counter_to_lines(oracle_counter),
        "",
        "Top per-workload comparison patterns:",
    ]
    if pattern_lines:
        lines.extend([f"- `{text}`: {count}" for text, count in pattern_lines])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Workloads",
            "",
            "| Workload | Repeat | Selected -> Oracle | Selected Primary | Oracle Primary | Regret (ms) | Summary |",
            "| --- | ---: | --- | --- | --- | ---: | --- |",
        ]
    )
    for row in rows:
        workload_name = Path(str(row["manifest_path"])).name
        regret_ms = "" if row["regret_s"] is None else f"{float(row['regret_s']) * 1000.0:.3f}"
        summary_text = str(row["summary_diff_text"]).replace("|", "/")
        lines.append(
            f"| `{workload_name}` | {row['repeat_count']} | `{row['selected_template']}` -> `{row['oracle_template']}` | "
            f"`{row['selected_primary_family']}` | `{row['oracle_primary_family']}` | {regret_ms} | {summary_text} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare selected and oracle architecture analyses from one measured-validation summary")
    parser.add_argument("--summary", required=True, help="Path to a measured-validation summary.json")
    parser.add_argument("--outdir", help="Output directory; defaults to the summary parent")
    args = parser.parse_args(argv)

    summary_path = Path(args.summary).resolve()
    summary = _load_json(summary_path)
    comparison = _compare_summary(summary)

    outdir = Path(args.outdir).resolve() if args.outdir else summary_path.parent
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / "selected_vs_oracle_arch.csv"
    json_path = outdir / "selected_vs_oracle_arch.json"
    md_path = outdir / "selected_vs_oracle_arch.md"

    _write_csv(csv_path, comparison["rows"])
    json_path.write_text(json.dumps(comparison, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(md_path, summary_path=summary_path, summary=summary, comparison=comparison)

    print(json.dumps(
        {
            "summary": summary_path.as_posix(),
            "csv": csv_path.as_posix(),
            "json": json_path.as_posix(),
            "md": md_path.as_posix(),
            "workload_count": comparison["aggregate"]["workload_count"],
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
