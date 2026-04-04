from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aqs.execution import execute_selected_plan  # noqa: E402


def _dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _stats_median(run: dict[str, Any], section: str) -> float | None:
    calibration = (run.get("failure_detail_json") or {}).get("calibration_ttfr") or {}
    stats = calibration.get(section) or {}
    value = stats.get("median")
    if value is not None:
        return float(value)
    return None


def _warm_median_ms(run: dict[str, Any]) -> float | None:
    samples = (run.get("failure_detail_json") or {}).get("warm_contract_times_ms") or []
    if not samples:
        return None
    return float(statistics.median(float(sample) for sample in samples))


def _run_execute(
    manifest_path: str,
    system_manifest: str,
    *,
    objective: str,
    probe_strategy: str,
    planner_budget: str,
    measurement_repeats: int,
    ttfr_repeats: int,
    execution_intent: str,
    plan_json_path: str | None,
    replicate_idx: int,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    payload = execute_selected_plan(
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
        plan_json_path=plan_json_path,
    )
    return {
        "payload": payload,
        "call_wall_s": round(max(time.perf_counter() - t0, 0.0), 9),
    }


def _phase_snapshot(run: dict[str, Any]) -> dict[str, float | None]:
    return {
        "ttfr_median_s": _stats_median(run, "ttfr_stats"),
        "planner_time_median_s": _stats_median(run, "planner_time_stats"),
        "setup_time_median_s": _stats_median(run, "setup_time_stats"),
        "first_contract_median_s": _stats_median(run, "first_contract_stats"),
        "warm_median_ms": _warm_median_ms(run),
    }


def _round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return float(left) - float(right)


def _fraction(component_delta: float | None, total_delta: float | None) -> float | None:
    if component_delta is None or total_delta is None or total_delta <= 0.0:
        return None
    return round(component_delta / total_delta, 6)


def _manifest_name(manifest_path: str) -> str:
    return Path(manifest_path).name


def _row_markdown(row: dict[str, Any]) -> list[str]:
    return [
        f"### `{_manifest_name(str(row['manifest_path']))}`",
        "",
        f"- Selected template: `{row['selected_template']}`",
        f"- Fresh call wall: `{row['fresh_call_wall_s'] * 1000.0:.3f} ms`",
        f"- Frozen call wall: `{row['frozen_call_wall_s'] * 1000.0:.3f} ms`",
        f"- Fresh minus frozen call wall: `{(row['fresh_minus_frozen_call_wall_s'] or 0.0) * 1000.0:.3f} ms`",
        f"- Fresh outer orchestration: `{(row['fresh_outer_orchestration_s'] or 0.0) * 1000.0:.3f} ms`",
        f"- Frozen outer orchestration: `{(row['frozen_outer_orchestration_s'] or 0.0) * 1000.0:.3f} ms`",
        f"- Fresh TTFR median: `{(row['fresh_ttfr_median_s'] or 0.0) * 1000.0:.3f} ms`",
        f"- Frozen TTFR median: `{(row['frozen_ttfr_median_s'] or 0.0) * 1000.0:.3f} ms`",
        f"- Fresh minus frozen TTFR: `{(row['fresh_minus_frozen_ttfr_s'] or 0.0) * 1000.0:.3f} ms`",
        f"- Fresh planner/setup/first-contract medians: `{(row['fresh_planner_time_median_s'] or 0.0) * 1000.0:.3f} / {(row['fresh_setup_time_median_s'] or 0.0) * 1000.0:.3f} / {(row['fresh_first_contract_median_s'] or 0.0) * 1000.0:.3f} ms`",
        f"- Frozen planner/setup/first-contract medians: `{(row['frozen_planner_time_median_s'] or 0.0) * 1000.0:.3f} / {(row['frozen_setup_time_median_s'] or 0.0) * 1000.0:.3f} / {(row['frozen_first_contract_median_s'] or 0.0) * 1000.0:.3f} ms`",
        f"- Warm medians fresh/frozen: `{row['fresh_warm_median_ms'] or 0.0:.3f} / {row['frozen_warm_median_ms'] or 0.0:.3f} ms`",
        f"- Planning+setup share of TTFR delta: `{row['planning_setup_share_of_ttfr_delta']}`",
        f"- First-contract share of TTFR delta: `{row['first_contract_share_of_ttfr_delta']}`",
        "",
    ]


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# OVH Low-Repeat Overhead ROI",
        "",
        f"- Workloads: `{len(payload.get('rows') or [])}`",
        f"- Interpretation: {payload.get('interpretation')}",
        "",
    ]
    for row in payload.get("rows") or []:
        lines.extend(_row_markdown(row))
    return "\n".join(lines) + "\n"


def _interpretation(rows: list[dict[str, Any]]) -> str:
    deltas = [row["fresh_minus_frozen_call_wall_s"] for row in rows if row.get("fresh_minus_frozen_call_wall_s") is not None]
    if not deltas:
        return "No fresh-vs-frozen call-wall deltas were available."
    low_repeat_deltas_ms = [delta * 1000.0 for delta in deltas[:2]]
    max_low_repeat_delta_ms = max(low_repeat_deltas_ms) if low_repeat_deltas_ms else 0.0
    if max_low_repeat_delta_ms >= 5.0:
        return (
            "Fresh-vs-frozen call-wall savings are large enough to justify a performance branch focused on plan reuse, "
            "cache, or amortization before any ranking change. The current frozen-plan path does not deliver a stable "
            "inner-TTFR improvement by itself, so the best-supported target is outer orchestration overhead rather than ranking."
        )
    return (
        "Fresh-vs-frozen call-wall savings are small relative to the low-repeat pain, so the next branch should focus on "
        "executor-side overhead rather than ranking or lightweight plan override reuse."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure fresh-vs-frozen selected-plan ROI on OVH workloads")
    parser.add_argument("--manifest", action="append", required=True)
    parser.add_argument("--system-manifest", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--objective", default="ttfr", choices=["ttfr", "steady_state", "gpu_seconds"])
    parser.add_argument("--probe-strategy", default="real_if_available")
    parser.add_argument("--planner-budget", default="balanced")
    parser.add_argument("--measurement-repeats", type=int, default=3)
    parser.add_argument("--ttfr-repeats", type=int, default=7)
    parser.add_argument("--execution-intent", default="require_real")
    args = parser.parse_args(argv)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    plan_dir = outdir / "plan_overrides"
    run_dir = outdir / "runs"
    plan_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for idx, manifest_path in enumerate(args.manifest):
        fresh = _run_execute(
            manifest_path,
            args.system_manifest,
            objective=args.objective,
            probe_strategy=args.probe_strategy,
            planner_budget=args.planner_budget,
            measurement_repeats=args.measurement_repeats,
            ttfr_repeats=args.ttfr_repeats,
            execution_intent=args.execution_intent,
            plan_json_path=None,
            replicate_idx=idx * 2,
        )
        fresh_payload = fresh["payload"]
        fresh_run = fresh_payload["execution_run"]
        if fresh_run.get("status") != "success":
            raise SystemExit(f"Fresh selected-plan execution failed for {manifest_path!r}: {fresh_run.get('status')!r}")

        manifest_stem = Path(manifest_path).stem
        plan_path = plan_dir / f"{manifest_stem}.selected_plan.json"
        _dump_json(plan_path, {"selected_plan": dict(fresh_payload["selected_plan"])})
        (run_dir / f"{manifest_stem}.fresh_selected.execute.json").write_text(
            json.dumps(fresh_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        frozen = _run_execute(
            manifest_path,
            args.system_manifest,
            objective=args.objective,
            probe_strategy=args.probe_strategy,
            planner_budget=args.planner_budget,
            measurement_repeats=args.measurement_repeats,
            ttfr_repeats=args.ttfr_repeats,
            execution_intent=args.execution_intent,
            plan_json_path=str(plan_path),
            replicate_idx=(idx * 2) + 1,
        )
        frozen_payload = frozen["payload"]
        frozen_run = frozen_payload["execution_run"]
        if frozen_run.get("status") != "success":
            raise SystemExit(f"Frozen selected-plan execution failed for {manifest_path!r}: {frozen_run.get('status')!r}")
        (run_dir / f"{manifest_stem}.frozen_selected.execute.json").write_text(
            json.dumps(frozen_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        fresh_phase = _phase_snapshot(fresh_run)
        frozen_phase = _phase_snapshot(frozen_run)
        outer_fresh = max(float(fresh["call_wall_s"]) - float(fresh_run.get("wall_s") or 0.0), 0.0)
        outer_frozen = max(float(frozen["call_wall_s"]) - float(frozen_run.get("wall_s") or 0.0), 0.0)
        ttfr_delta = _delta(fresh_phase["ttfr_median_s"], frozen_phase["ttfr_median_s"])
        planner_setup_delta = None
        if fresh_phase["planner_time_median_s"] is not None and frozen_phase["planner_time_median_s"] is not None and fresh_phase["setup_time_median_s"] is not None and frozen_phase["setup_time_median_s"] is not None:
            planner_setup_delta = (
                float(fresh_phase["planner_time_median_s"]) + float(fresh_phase["setup_time_median_s"])
                - float(frozen_phase["planner_time_median_s"]) - float(frozen_phase["setup_time_median_s"])
            )
        first_contract_delta = _delta(fresh_phase["first_contract_median_s"], frozen_phase["first_contract_median_s"])

        rows.append(
            {
                "manifest_path": str(Path(manifest_path).resolve()),
                "selected_template": fresh_payload["selected_plan"].get("template_name"),
                "fresh_call_wall_s": _round_or_none(float(fresh["call_wall_s"]), 9),
                "frozen_call_wall_s": _round_or_none(float(frozen["call_wall_s"]), 9),
                "fresh_minus_frozen_call_wall_s": _round_or_none(_delta(fresh["call_wall_s"], frozen["call_wall_s"]), 9),
                "fresh_outer_orchestration_s": _round_or_none(outer_fresh, 9),
                "frozen_outer_orchestration_s": _round_or_none(outer_frozen, 9),
                "fresh_inner_wall_s": _round_or_none(float(fresh_run.get("wall_s") or 0.0), 9),
                "frozen_inner_wall_s": _round_or_none(float(frozen_run.get("wall_s") or 0.0), 9),
                "fresh_ttfr_median_s": _round_or_none(fresh_phase["ttfr_median_s"], 9),
                "frozen_ttfr_median_s": _round_or_none(frozen_phase["ttfr_median_s"], 9),
                "fresh_minus_frozen_ttfr_s": _round_or_none(ttfr_delta, 9),
                "fresh_planner_time_median_s": _round_or_none(fresh_phase["planner_time_median_s"], 9),
                "frozen_planner_time_median_s": _round_or_none(frozen_phase["planner_time_median_s"], 9),
                "fresh_setup_time_median_s": _round_or_none(fresh_phase["setup_time_median_s"], 9),
                "frozen_setup_time_median_s": _round_or_none(frozen_phase["setup_time_median_s"], 9),
                "fresh_first_contract_median_s": _round_or_none(fresh_phase["first_contract_median_s"], 9),
                "frozen_first_contract_median_s": _round_or_none(frozen_phase["first_contract_median_s"], 9),
                "fresh_warm_median_ms": _round_or_none(fresh_phase["warm_median_ms"], 6),
                "frozen_warm_median_ms": _round_or_none(frozen_phase["warm_median_ms"], 6),
                "planning_setup_share_of_ttfr_delta": _fraction(planner_setup_delta, ttfr_delta),
                "first_contract_share_of_ttfr_delta": _fraction(first_contract_delta, ttfr_delta),
                "plan_override_path": str(plan_path.resolve()),
            }
        )

    payload = {
        "study_name": "ovh_low_repeat_overhead_roi",
        "row_count": len(rows),
        "rows": rows,
        "interpretation": _interpretation(rows),
    }
    json_path = outdir / "ovh_low_repeat_overhead_roi.json"
    md_path = outdir / "ovh_low_repeat_overhead_roi.md"
    _dump_json(json_path, payload)
    md_path.write_text(_build_markdown(payload), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
