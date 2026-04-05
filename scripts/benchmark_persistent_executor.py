from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aqs.persistent_executor import PersistentExecutorClient  # noqa: E402


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
    persistent_worker_socket: str | None = None,
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
        "none",
        "--no-allow-distributed",
        "--out",
        str(out_path),
    ]
    if plan_json_path:
        command.extend(["--plan-json", plan_json_path])
    if plan_bundle_path:
        command.extend(["--plan-bundle", plan_bundle_path])
    if persistent_worker_socket:
        command.extend(["--persistent-worker-socket", persistent_worker_socket])

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


class WorkerProcess:
    def __init__(self, socket_path: Path):
        self.socket_path = socket_path
        self.proc: subprocess.Popen[str] | None = None

    def __enter__(self) -> PersistentExecutorClient:
        command = [
            sys.executable,
            "-m",
            "aqs",
            "persistent-worker",
            "--socket",
            str(self.socket_path),
        ]
        self.proc = subprocess.Popen(
            command,
            cwd=str(REPO_ROOT),
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        client = PersistentExecutorClient(self.socket_path, timeout_s=5.0)
        deadline = time.time() + 10.0
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                response = client.ping()
                if response.get("ok"):
                    return client
            except Exception as exc:  # pragma: no cover - startup retry guard
                last_error = exc
                time.sleep(0.05)
        raise SystemExit(f"persistent worker did not become ready: {last_error}")

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.proc is None:
            return
        try:
            PersistentExecutorClient(self.socket_path, timeout_s=2.0).shutdown()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5.0)


def _sample_summary(sample: dict[str, Any]) -> dict[str, Any]:
    payload = sample["payload"]
    run = payload["execution_run"]
    accuracy = payload.get("accuracy_eval") or {}
    persistent = payload.get("persistent_executor_provenance") or {}
    worker_startup_s = _timing(payload, "worker_startup_s")
    session_total_s = float(sample["cli_wall_s"]) + (worker_startup_s if payload.get("execution_mode") == "persistent_executor" else 0.0)
    return {
        "cli_wall_s": float(sample["cli_wall_s"]),
        "session_total_s": float(session_total_s),
        "driver_total_s": float(payload.get("driver_total_s") or 0.0),
        "outer_driver_overhead_s": float(payload.get("outer_driver_overhead_s") or 0.0),
        "execute_plan_bundle_s": _timing(payload, "execute_plan_bundle_s"),
        "execution_wall_s": float(run.get("wall_s") or 0.0),
        "import_real_stack_s": _timing(payload, "import_real_stack_s"),
        "network_build_s": _timing(payload, "network_build_s"),
        "worker_startup_s": worker_startup_s,
        "worker_request_dispatch_s": _timing(payload, "worker_request_dispatch_s"),
        "worker_execute_s": _timing(payload, "worker_execute_s"),
        "worker_reply_s": _timing(payload, "worker_reply_s"),
        "session_request_index": int(_timing(payload, "session_request_index")),
        "session_uptime_s": _timing(payload, "session_uptime_s"),
        "selected_plan_id": str(payload["selected_plan"].get("plan_id") or ""),
        "selection_source": str(payload.get("selection_source") or ""),
        "execution_mode": str(payload.get("execution_mode") or "direct_executor"),
        "worker_session_id": persistent.get("worker_session_id"),
        "worker_warm": persistent.get("worker_warm"),
        "bundle_hit": bool(persistent.get("bundle_hit")),
        "accuracy_status": str(accuracy.get("status") or "unknown"),
        "cache_status": str((payload.get("plan_bundle_provenance") or {}).get("cache_status") or ""),
    }


def _median_row(samples: list[dict[str, Any]], *, mode: str) -> dict[str, Any]:
    numeric_keys = [
        "cli_wall_s",
        "session_total_s",
        "driver_total_s",
        "outer_driver_overhead_s",
        "execute_plan_bundle_s",
        "execution_wall_s",
        "import_real_stack_s",
        "network_build_s",
        "worker_startup_s",
        "worker_request_dispatch_s",
        "worker_execute_s",
        "worker_reply_s",
        "session_uptime_s",
    ]
    medians = {key: _median([float(sample[key]) for sample in samples]) for key in numeric_keys}
    return {
        "mode": mode,
        **medians,
        "selection_sources": sorted({sample["selection_source"] for sample in samples}),
        "selected_plan_ids": sorted({sample["selected_plan_id"] for sample in samples}),
        "execution_modes": sorted({sample["execution_mode"] for sample in samples}),
        "worker_warm_states": sorted({str(sample["worker_warm"]) for sample in samples}),
        "session_request_indices": sorted({sample["session_request_index"] for sample in samples}),
        "accuracy_statuses": sorted({sample["accuracy_status"] for sample in samples}),
        "bundle_cache_statuses": sorted({sample["cache_status"] for sample in samples if sample["cache_status"]}),
    }


def _mode_table(row: dict[str, Any]) -> list[str]:
    lines = [
        f"### `{_manifest_name(str(row['manifest_path']))}`",
        "",
        "| Mode | CLI Wall ms | Session Total ms | Driver Total ms | Outer Overhead ms | Import Stack ms | Network Build ms | Worker Startup ms | Worker Dispatch ms | Worker Execute ms | Worker Reply ms | Inner Wall ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode_row in row["mode_rows"]:
        lines.append(
            "| "
            + mode_row["mode"]
            + f" | {mode_row['cli_wall_s'] * 1000.0:.3f}"
            + f" | {mode_row['session_total_s'] * 1000.0:.3f}"
            + f" | {mode_row['driver_total_s'] * 1000.0:.3f}"
            + f" | {mode_row['outer_driver_overhead_s'] * 1000.0:.3f}"
            + f" | {mode_row['import_real_stack_s'] * 1000.0:.3f}"
            + f" | {mode_row['network_build_s'] * 1000.0:.3f}"
            + f" | {mode_row['worker_startup_s'] * 1000.0:.3f}"
            + f" | {mode_row['worker_request_dispatch_s'] * 1000.0:.3f}"
            + f" | {mode_row['worker_execute_s'] * 1000.0:.3f}"
            + f" | {mode_row['worker_reply_s'] * 1000.0:.3f}"
            + f" | {mode_row['execution_wall_s'] * 1000.0:.3f} |"
        )
    lines.extend(
        [
            "",
            f"- Seed selected plan: `{row['seed_selected_plan_id']}`",
            f"- Selection semantics preserved across all modes: `{row['selection_semantics_preserved']}`",
            f"- Accuracy parity across all modes: `{row['all_accuracy_pass']}`",
            f"- One-shot bundle minus persistent warm CLI wall: `{row['bundle_minus_persistent_warm_cli_wall_s'] * 1000.0:.3f} ms`",
            f"- `--plan-json` minus one-shot bundle CLI wall: `{row['plan_json_minus_bundle_cli_wall_s'] * 1000.0:.3f} ms`",
            f"- Persistent warm recovered `{row['persistent_warm_recovery_ratio']}` of the one-shot bundle penalty",
            "",
        ]
    )
    return lines


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# OVH Persistent Executor Investigation v1",
        "",
        f"- Benchmark repeats per mode: `{payload['benchmark_repeats']}`",
        f"- Workloads: `{len(payload.get('rows') or [])}`",
        f"- Interpretation: {payload['interpretation']}",
        "",
    ]
    for row in payload["rows"]:
        lines.extend(_mode_table(row))
    return "\n".join(lines) + "\n"


def _interpretation(rows: list[dict[str, Any]]) -> str:
    warm_wins = [
        row for row in rows
        if row["manifest_role"] in {"low_repeat_amplitude", "low_repeat_amplitude_heldout"}
        and row["bundle_minus_persistent_warm_cli_wall_s"] > 0.0
    ]
    control_harm = any(
        row["manifest_role"] == "control_medium_batched" and row["bundle_minus_persistent_warm_cli_wall_s"] < -0.025
        for row in rows
    )
    if len(warm_wins) >= 2 and not control_harm:
        return (
            "Persistent execution amortized enough bootstrap cost to beat one-shot bundle hits on the canonical low-repeat OVH "
            "workloads without materially harming the medium-repeat control. The next branch should stay performance-only and "
            "turn the worker into a tighter persistent-executor prototype."
        )
    return (
        "Persistent execution did not deliver a clean enough warm-request win across the canonical OVH workloads. The next "
        "branch should stay performance-only and investigate an even higher outer process/bootstrap layer."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the OVH persistent executor benchmark matrix")
    parser.add_argument("--manifest", action="append", required=True)
    parser.add_argument("--system-manifest", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--objective", default="ttfr", choices=["ttfr", "steady_state", "gpu_seconds"])
    parser.add_argument("--probe-strategy", default="real_if_available")
    parser.add_argument("--planner-budget", default="balanced")
    parser.add_argument("--measurement-repeats", type=int, default=3)
    parser.add_argument("--execution-intent", default="require_real")
    parser.add_argument("--benchmark-repeats", type=int, default=5)
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
            "persistent_bundle_hit_cold": [],
            "persistent_bundle_hit_warm": [],
        }

        for repeat_idx in range(args.benchmark_repeats):
            base_idx = (manifest_index * 1000) + 1 + (repeat_idx * 20)
            one_shot_modes = [
                ("fresh", {"plan_json_path": None, "plan_bundle_path": None}),
                ("plan_json", {"plan_json_path": str(seed_plan_path), "plan_bundle_path": None}),
                ("bundle_hit", {"plan_json_path": None, "plan_bundle_path": str(seed_bundle_path)}),
            ]
            for offset, (mode_name, mode_spec) in enumerate(one_shot_modes):
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
                )
                per_mode_samples[mode_name].append(_sample_summary(sample))

            socket_path = Path(tempfile.gettempdir()) / f"aqs_{manifest_stem[:16]}_{repeat_idx}.sock"
            with WorkerProcess(socket_path):
                cold = _run_execute(
                    manifest_path,
                    args.system_manifest,
                    objective=args.objective,
                    probe_strategy=args.probe_strategy,
                    planner_budget=args.planner_budget,
                    measurement_repeats=args.measurement_repeats,
                    execution_intent=args.execution_intent,
                    replicate_idx=base_idx + 10,
                    out_path=run_dir / f"{manifest_stem}.rep{repeat_idx}.persistent_bundle_hit_cold.execute.json",
                    plan_bundle_path=str(seed_bundle_path),
                    persistent_worker_socket=str(socket_path),
                )
                warm = _run_execute(
                    manifest_path,
                    args.system_manifest,
                    objective=args.objective,
                    probe_strategy=args.probe_strategy,
                    planner_budget=args.planner_budget,
                    measurement_repeats=args.measurement_repeats,
                    execution_intent=args.execution_intent,
                    replicate_idx=base_idx + 11,
                    out_path=run_dir / f"{manifest_stem}.rep{repeat_idx}.persistent_bundle_hit_warm.execute.json",
                    plan_bundle_path=str(seed_bundle_path),
                    persistent_worker_socket=str(socket_path),
                )
            per_mode_samples["persistent_bundle_hit_cold"].append(_sample_summary(cold))
            per_mode_samples["persistent_bundle_hit_warm"].append(_sample_summary(warm))

        mode_rows = [_median_row(per_mode_samples[mode_name], mode=mode_name) for mode_name in per_mode_samples]
        mode_lookup = {row["mode"]: row for row in mode_rows}
        selection_semantics_preserved = all(
            mode_lookup[mode]["selected_plan_ids"] == [seed_plan_id]
            for mode in {"plan_json", "bundle_hit", "persistent_bundle_hit_cold", "persistent_bundle_hit_warm"}
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
        persistent_warm_gain = round(
            mode_lookup["bundle_hit"]["cli_wall_s"] - mode_lookup["persistent_bundle_hit_warm"]["cli_wall_s"],
            9,
        )
        persistent_cold_session_gain = round(
            mode_lookup["bundle_hit"]["cli_wall_s"] - mode_lookup["persistent_bundle_hit_cold"]["session_total_s"],
            9,
        )
        persistent_warm_recovery_ratio = None
        if plan_json_gap > 0.0:
            persistent_warm_recovery_ratio = round(persistent_warm_gain / plan_json_gap, 6)

        rows.append(
            {
                "manifest_path": str(Path(manifest_path).resolve()),
                "manifest_role": role,
                "seed_selected_plan_id": seed_plan_id,
                "selection_semantics_preserved": selection_semantics_preserved,
                "all_accuracy_pass": all_accuracy_pass,
                "benchmark_repeats": int(args.benchmark_repeats),
                "mode_rows": mode_rows,
                "plan_json_minus_bundle_cli_wall_s": plan_json_gap,
                "bundle_minus_persistent_warm_cli_wall_s": persistent_warm_gain,
                "bundle_minus_persistent_cold_session_total_s": persistent_cold_session_gain,
                "persistent_warm_recovery_ratio": persistent_warm_recovery_ratio,
            }
        )

    summary = {
        "study": "ovh_persistent_executor_investigation_v1",
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

    _dump_json(outdir / "ovh_persistent_executor_investigation_v1.json", summary)
    (outdir / "ovh_persistent_executor_investigation_v1.md").write_text(_build_markdown(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
