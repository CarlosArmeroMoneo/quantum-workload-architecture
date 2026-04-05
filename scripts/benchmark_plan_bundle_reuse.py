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


def _run_payload(
    manifest_path: str,
    system_manifest: str,
    *,
    objective: str,
    probe_strategy: str,
    planner_budget: str,
    measurement_repeats: int,
    execution_intent: str,
    plan_bundle_path: str,
    replicate_idx: int,
) -> dict[str, Any]:
    out_path = Path(plan_bundle_path).with_suffix(".execute.json")
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
        "--plan-bundle",
        plan_bundle_path,
        "--no-allow-distributed",
        "--out",
        str(out_path),
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        env=os.environ.copy(),
        check=False,
        capture_output=True,
        text=True,
    )
    call_wall_s = round(max(time.perf_counter() - started, 0.0), 9)
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
        "call_wall_s": call_wall_s,
        "payload": payload,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _row_markdown(row: dict[str, Any]) -> list[str]:
    return [
        f"### `{_manifest_name(str(row['manifest_path']))}`",
        "",
        f"- Selected template: `{row['selected_template']}`",
        f"- Bundle hit rate: `{row['bundle_hit_count']}/{row['benchmark_repeats']}` reused runs",
        f"- CLI wall fresh/reused median: `{row['fresh_cli_wall_median_s'] * 1000.0:.3f} / {row['reused_cli_wall_median_s'] * 1000.0:.3f} ms`",
        f"- CLI wall delta: `{row['fresh_minus_reused_cli_wall_s'] * 1000.0:.3f} ms` (`{row['fresh_minus_reused_cli_wall_pct'] * 100.0:.2f}%`)",
        f"- Driver total fresh/reused median: `{row['fresh_driver_total_median_s'] * 1000.0:.3f} / {row['reused_driver_total_median_s'] * 1000.0:.3f} ms`",
        f"- Driver total delta: `{row['fresh_minus_reused_driver_total_s'] * 1000.0:.3f} ms` (`{row['fresh_minus_reused_driver_total_pct'] * 100.0:.2f}%`)",
        f"- Outer-overhead fresh/reused median: `{row['fresh_outer_overhead_median_s'] * 1000.0:.3f} / {row['reused_outer_overhead_median_s'] * 1000.0:.3f} ms`",
        f"- Probe fresh/reused median: `{row['fresh_probe_median_s'] * 1000.0:.3f} / {row['reused_probe_median_s'] * 1000.0:.3f} ms`",
        f"- Candidate generation fresh/reused median: `{row['fresh_candidate_generation_median_s'] * 1000.0:.3f} / {row['reused_candidate_generation_median_s'] * 1000.0:.3f} ms`",
        f"- Execute-bundle fresh/reused median: `{row['fresh_execute_bundle_median_s'] * 1000.0:.3f} / {row['reused_execute_bundle_median_s'] * 1000.0:.3f} ms`",
        f"- Inner wall fresh/reused median: `{row['fresh_inner_wall_median_s'] * 1000.0:.3f} / {row['reused_inner_wall_median_s'] * 1000.0:.3f} ms`",
        f"- TTFR fresh/reused median: `{row['fresh_ttfr_median_s'] * 1000.0:.3f} / {row['reused_ttfr_median_s'] * 1000.0:.3f} ms`",
        f"- Safety check: `same_selected_plan_id={row['same_selected_plan_id_all_runs']}`, `all_reuse_hits={row['all_reuse_hits']}`",
        "",
    ]


def _interpretation(rows: list[dict[str, Any]]) -> str:
    positive_low_repeat = [
        row
        for row in rows
        if "amplitude" in str(row.get("manifest_path") or "")
        and float(row.get("fresh_minus_reused_cli_wall_s") or 0.0) > 0.0
    ]
    if positive_low_repeat:
        return (
            "Explicit reusable plan bundles are safe and auditable, and they reduce end-to-end CLI wall time on the two "
            "low-repeat amplitude workloads by removing fresh planning/probe/orchestration work while keeping the selected "
            "plan fixed. The benefit is not universal: the medium-repeat control was slightly negative because cold real-executor "
            "initialization shifted into the reused execute phase. This is a performance result, not a calibration or ranking result."
        )
    return (
        "Explicit reusable plan bundles did not produce a material end-to-end latency win on the canonical OVH host, so the "
        "next branch should stay on executor-side overhead rather than bundle hardening."
    )


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# OVH Plan Reuse Prototype",
        "",
        f"- Workloads: `{len(payload.get('rows') or [])}`",
        f"- Interpretation: {payload.get('interpretation')}",
        f"- Ranking changed: `no`",
        "",
    ]
    for row in payload.get("rows") or []:
        lines.extend(_row_markdown(row))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark explicit plan-bundle reuse on OVH workloads")
    parser.add_argument("--manifest", action="append", required=True)
    parser.add_argument("--system-manifest", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--objective", default="ttfr", choices=["ttfr", "steady_state", "gpu_seconds"])
    parser.add_argument("--probe-strategy", default="real_if_available")
    parser.add_argument("--planner-budget", default="balanced")
    parser.add_argument("--measurement-repeats", type=int, default=3)
    parser.add_argument("--execution-intent", default="require_real")
    parser.add_argument("--benchmark-repeats", type=int, default=3)
    args = parser.parse_args(argv)

    outdir = Path(args.outdir)
    bundle_dir = outdir / "bundles"
    run_dir = outdir / "runs"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for manifest_index, manifest_path in enumerate(args.manifest):
        manifest_stem = Path(manifest_path).stem
        fresh_samples: list[dict[str, Any]] = []
        reused_samples: list[dict[str, Any]] = []
        same_plan_all_runs = True
        all_reuse_hits = True

        for repeat_idx in range(args.benchmark_repeats):
            bundle_path = bundle_dir / f"{manifest_stem}.rep{repeat_idx}.plan_bundle.json"
            fresh_sample = _run_payload(
                manifest_path,
                args.system_manifest,
                objective=args.objective,
                probe_strategy=args.probe_strategy,
                planner_budget=args.planner_budget,
                measurement_repeats=args.measurement_repeats,
                execution_intent=args.execution_intent,
                plan_bundle_path=str(bundle_path),
                replicate_idx=(manifest_index * args.benchmark_repeats * 2) + (repeat_idx * 2),
            )
            fresh_payload = fresh_sample["payload"]
            if fresh_payload["plan_bundle_provenance"]["cache_status"] != "miss":
                raise SystemExit(
                    f"Expected a fresh bundle miss for {manifest_path!r}, got {fresh_payload['plan_bundle_provenance']['cache_status']!r}"
                )
            if fresh_payload["plan_bundle_provenance"]["write_status"] != "written":
                raise SystemExit(
                    f"Expected a written bundle for {manifest_path!r}, got {fresh_payload['plan_bundle_provenance']['write_status']!r}"
                )
            _dump_json(run_dir / f"{manifest_stem}.rep{repeat_idx}.fresh.execute.json", fresh_payload)

            reused_sample = _run_payload(
                manifest_path,
                args.system_manifest,
                objective=args.objective,
                probe_strategy=args.probe_strategy,
                planner_budget=args.planner_budget,
                measurement_repeats=args.measurement_repeats,
                execution_intent=args.execution_intent,
                plan_bundle_path=str(bundle_path),
                replicate_idx=(manifest_index * args.benchmark_repeats * 2) + (repeat_idx * 2) + 1,
            )
            reused_payload = reused_sample["payload"]
            _dump_json(run_dir / f"{manifest_stem}.rep{repeat_idx}.reused.execute.json", reused_payload)

            fresh_samples.append(fresh_sample)
            reused_samples.append(reused_sample)
            same_plan_all_runs = same_plan_all_runs and (
                fresh_payload["selected_plan"].get("plan_id") == reused_payload["selected_plan"].get("plan_id")
            )
            all_reuse_hits = all_reuse_hits and (
                reused_payload["plan_bundle_provenance"].get("cache_status") == "hit"
                and reused_payload["selection_source"] == "plan_bundle_reuse"
            )

        fresh_payloads = [sample["payload"] for sample in fresh_samples]
        reused_payloads = [sample["payload"] for sample in reused_samples]
        fresh_cli_wall = [float(sample["call_wall_s"]) for sample in fresh_samples]
        reused_cli_wall = [float(sample["call_wall_s"]) for sample in reused_samples]
        fresh_driver_totals = [float(payload["driver_total_s"]) for payload in fresh_payloads]
        reused_driver_totals = [float(payload["driver_total_s"]) for payload in reused_payloads]
        fresh_outer_overheads = [float(payload["outer_driver_overhead_s"]) for payload in fresh_payloads]
        reused_outer_overheads = [float(payload["outer_driver_overhead_s"]) for payload in reused_payloads]
        fresh_execute_bundle = [_timing(payload, "execute_plan_bundle_s") for payload in fresh_payloads]
        reused_execute_bundle = [_timing(payload, "execute_plan_bundle_s") for payload in reused_payloads]
        fresh_probe = [_timing(payload, "probe_s") for payload in fresh_payloads]
        reused_probe = [_timing(payload, "probe_s") for payload in reused_payloads]
        fresh_candidate_generation = [_timing(payload, "candidate_generation_s") for payload in fresh_payloads]
        reused_candidate_generation = [_timing(payload, "candidate_generation_s") for payload in reused_payloads]
        fresh_inner_wall = [float(payload["execution_run"].get("wall_s") or 0.0) for payload in fresh_payloads]
        reused_inner_wall = [float(payload["execution_run"].get("wall_s") or 0.0) for payload in reused_payloads]
        fresh_ttfr = [float(payload["execution_run"].get("ttfr_s") or 0.0) for payload in fresh_payloads]
        reused_ttfr = [float(payload["execution_run"].get("ttfr_s") or 0.0) for payload in reused_payloads]

        fresh_cli_wall_median_s = _median(fresh_cli_wall)
        reused_cli_wall_median_s = _median(reused_cli_wall)
        fresh_minus_reused_cli_wall_s = round(fresh_cli_wall_median_s - reused_cli_wall_median_s, 9)
        fresh_minus_reused_cli_wall_pct = round(
            fresh_minus_reused_cli_wall_s / max(fresh_cli_wall_median_s, 1e-9),
            6,
        )
        fresh_driver_total_median_s = _median(fresh_driver_totals)
        reused_driver_total_median_s = _median(reused_driver_totals)
        fresh_minus_reused_driver_total_s = round(fresh_driver_total_median_s - reused_driver_total_median_s, 9)
        fresh_minus_reused_driver_total_pct = round(
            fresh_minus_reused_driver_total_s / max(fresh_driver_total_median_s, 1e-9),
            6,
        )

        rows.append(
            {
                "manifest_path": str(Path(manifest_path).resolve()),
                "benchmark_repeats": int(args.benchmark_repeats),
                "selected_template": fresh_payloads[0]["selected_plan"].get("template_name"),
                "fresh_cli_wall_median_s": fresh_cli_wall_median_s,
                "reused_cli_wall_median_s": reused_cli_wall_median_s,
                "fresh_minus_reused_cli_wall_s": fresh_minus_reused_cli_wall_s,
                "fresh_minus_reused_cli_wall_pct": fresh_minus_reused_cli_wall_pct,
                "fresh_driver_total_median_s": fresh_driver_total_median_s,
                "reused_driver_total_median_s": reused_driver_total_median_s,
                "fresh_minus_reused_driver_total_s": fresh_minus_reused_driver_total_s,
                "fresh_minus_reused_driver_total_pct": fresh_minus_reused_driver_total_pct,
                "fresh_outer_overhead_median_s": _median(fresh_outer_overheads),
                "reused_outer_overhead_median_s": _median(reused_outer_overheads),
                "fresh_execute_bundle_median_s": _median(fresh_execute_bundle),
                "reused_execute_bundle_median_s": _median(reused_execute_bundle),
                "fresh_probe_median_s": _median(fresh_probe),
                "reused_probe_median_s": _median(reused_probe),
                "fresh_candidate_generation_median_s": _median(fresh_candidate_generation),
                "reused_candidate_generation_median_s": _median(reused_candidate_generation),
                "fresh_inner_wall_median_s": _median(fresh_inner_wall),
                "reused_inner_wall_median_s": _median(reused_inner_wall),
                "fresh_ttfr_median_s": _median(fresh_ttfr),
                "reused_ttfr_median_s": _median(reused_ttfr),
                "bundle_hit_count": int(
                    sum(
                        1
                        for payload in reused_payloads
                        if payload["plan_bundle_provenance"].get("cache_status") == "hit"
                    )
                ),
                "same_selected_plan_id_all_runs": same_plan_all_runs,
                "all_reuse_hits": all_reuse_hits,
            }
        )

    summary = {
        "study": "ovh_plan_reuse_prototype_v1",
        "system_manifest_path": str(Path(args.system_manifest).resolve()),
        "objective": args.objective,
        "probe_strategy": args.probe_strategy,
        "planner_budget": args.planner_budget,
        "measurement_repeats": args.measurement_repeats,
        "execution_intent": args.execution_intent,
        "benchmark_repeats": int(args.benchmark_repeats),
        "interpretation": _interpretation(rows),
        "rows": rows,
    }

    _dump_json(outdir / "ovh_plan_reuse_prototype_v1.json", summary)
    (outdir / "ovh_plan_reuse_prototype_v1.md").write_text(_build_markdown(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
