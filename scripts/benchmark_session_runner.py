from __future__ import annotations

import argparse
import csv
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

from aqs.execution import (  # noqa: E402
    _assess_plan_bundle_compatibility,
    _build_persistent_worker_request,
    _build_plan_bundle_scope,
    _load_plan_bundle,
    ExecutionConfig,
)
from aqs.manifest import load_yaml  # noqa: E402
from aqs.persistent_client import PersistentExecutorClient  # noqa: E402
from aqs.planner import load_system_manifest  # noqa: E402
from aqs.repo_metadata import capture_repo_metadata  # noqa: E402
from aqs.session_runner import PersistentWorkerProcess, run_session  # noqa: E402
from aqs.doctor import collect_system_profile  # noqa: E402


SYSTEM_MANIFEST_PATH = "configs/systems/ovh_gra9_rtx5000_28.yml"
SESSION_MANIFEST_PATH = "benchmarks/sessions/ovh_gate_s_trio.yaml"
GATE_P_REFERENCE_SUMMARY = "artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/summary.json"
DEFAULT_OUTDIR = "artifacts/session_runner/ovh_session_runner_prototype_v1"
BENCHMARK_REPEATS = 5
SAME_LENGTHS = (1, 2, 4, 8)
MIXED_ORDER = ("run01", "run06", "run08", "run01", "run06", "run08")


def _dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(float(statistics.median(values)), 9)


def _normalized(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve()).replace("\\", "/")


def _correctness_ok(payload: dict[str, Any]) -> bool:
    execution_ok = str((payload.get("execution_run") or {}).get("status") or "") == "success"
    accuracy = payload.get("accuracy_eval") or {}
    accuracy_ok = not accuracy or str(accuracy.get("status") or "") in {"pass", "ok", "success"}
    return bool(execution_ok and accuracy_ok)


def _load_base_session_manifest() -> dict[str, Any]:
    return load_yaml(REPO_ROOT / SESSION_MANIFEST_PATH)


def _request_lookup(session_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {request["id"]: dict(request) for request in session_manifest["requests"]}


def _sequence_manifest(base_session_manifest: dict[str, Any], request_ids: list[str], *, prefix: str) -> dict[str, Any]:
    lookup = _request_lookup(base_session_manifest)
    requests = []
    for index, request_id in enumerate(request_ids, start=1):
        base_request = dict(lookup[request_id])
        requests.append(
            {
                **base_request,
                "id": f"{prefix}_{index:02d}_{request_id}",
            }
        )
    return {
        **dict(base_session_manifest),
        "requests": requests,
    }


def _prepare_request_materials(base_session_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    system_manifest = load_system_manifest(REPO_ROOT / base_session_manifest["system_manifest"])
    system_profile = collect_system_profile()
    repo_metadata = capture_repo_metadata()
    materials: dict[str, dict[str, Any]] = {}
    for request in base_session_manifest["requests"]:
        workload_manifest = load_yaml(REPO_ROOT / request["workload_manifest"])
        bundle_payload = _load_plan_bundle(REPO_ROOT / request["plan_bundle"])
        bundle_scope = _build_plan_bundle_scope(
            REPO_ROOT / request["workload_manifest"],
            REPO_ROOT / base_session_manifest["system_manifest"],
            workload_manifest,
            system_manifest,
            system_profile,
            repo_metadata,
            objective=base_session_manifest["objective"],
            probe_strategy=base_session_manifest["probe_strategy"],
            planner_budget=base_session_manifest["planner_budget"],
            allow_distributed=bool(base_session_manifest.get("allow_distributed")),
            max_candidates=None,
        )
        compatibility = _assess_plan_bundle_compatibility(bundle_payload, bundle_scope)
        if not compatibility["compatible"]:
            raise SystemExit(
                f"seed bundle for {request['id']} is not compatible with the current checkout: {compatibility['reason']}"
            )
        selected_plan = dict(bundle_payload["selected_plan"])
        config = ExecutionConfig(
            objective=base_session_manifest["objective"],
            precision=str(selected_plan.get("precision") or "complex128"),
            probe_strategy=base_session_manifest["probe_strategy"],
            measurement_repeats=int(base_session_manifest["measurement_repeats"]),
            execution_intent=base_session_manifest["execution_intent"],
            graph_mode=str(base_session_manifest["graph_mode"]),
            prewarm_mode="none",
        )
        materials[request["id"]] = {
            "request": request,
            "workload_manifest": workload_manifest,
            "system_manifest": system_manifest,
            "bundle_scope": bundle_scope,
            "selected_plan": selected_plan,
            "request_payload": _build_persistent_worker_request(
                command="execute_bundle",
                bundle_scope=bundle_scope,
                workload_manifest=workload_manifest,
                system_manifest=system_manifest,
                selected_plan=selected_plan,
                config=config,
                selection_source="plan_bundle_reuse",
                allow_distributed=bool(base_session_manifest.get("allow_distributed")),
            ),
        }
    return materials


def _health_row(
    *,
    mode: str,
    sequence_label: str,
    benchmark_repeat: int,
    label: str,
    status: dict[str, Any] | None,
    request_id: str | None = None,
    workload_manifest: str | None = None,
) -> dict[str, Any]:
    row = {
        "recorded_at": time.time(),
        "mode": mode,
        "sequence_label": sequence_label,
        "benchmark_repeat": benchmark_repeat,
        "label": label,
        "request_id": request_id,
        "workload_manifest": workload_manifest,
    }
    if status:
        row.update(status)
    return row


def _run_execute_cli(
    *,
    manifest_path: str,
    plan_bundle_path: str,
    socket_path: str,
    out_path: Path,
    session_manifest: dict[str, Any],
) -> tuple[dict[str, Any], float]:
    command = [
        sys.executable,
        "-m",
        "aqs",
        "tnep",
        "execute",
        "--manifest",
        manifest_path,
        "--system-manifest",
        session_manifest["system_manifest"],
        "--objective",
        session_manifest["objective"],
        "--probe-strategy",
        session_manifest["probe_strategy"],
        "--planner-budget",
        session_manifest["planner_budget"],
        "--measurement-repeats",
        str(session_manifest["measurement_repeats"]),
        "--execution-intent",
        session_manifest["execution_intent"],
        "--graph-mode",
        session_manifest["graph_mode"],
        "--no-allow-distributed",
        "--plan-bundle",
        plan_bundle_path,
        "--persistent-worker-socket",
        socket_path,
        "--out",
        str(out_path),
    ]
    started = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    wall_s = round(max(time.perf_counter() - started, 0.0), 9)
    if proc.returncode != 0:
        raise SystemExit(
            f"persistent_warm_cli command failed for {manifest_path} with code {proc.returncode}:\n{proc.stdout}\n{proc.stderr}"
        )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    return payload, wall_s


def _prime_existing_worker(
    *,
    client: PersistentExecutorClient,
    base_request_material: dict[str, Any],
) -> None:
    response = client.execute_bundle(base_request_material["request_payload"])
    if not response.get("ok"):
        raise SystemExit(f"worker primer request was rejected: {response}")


def _rows_to_health_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rss_samples = [int((row.get("health") or {}).get("rss_bytes") or 0) for row in rows if isinstance(row.get("health"), dict)]
    monotonic_rss = bool(rss_samples) and all(curr >= prev for prev, curr in zip(rss_samples, rss_samples[1:]))
    return {
        "sample_count": len(rows),
        "rss_bytes_min": min(rss_samples) if rss_samples else None,
        "rss_bytes_max": max(rss_samples) if rss_samples else None,
        "rss_bytes_delta": (rss_samples[-1] - rss_samples[0]) if len(rss_samples) >= 2 else None,
        "monotonic_rss_increase": monotonic_rss,
    }


def _render_health_summary_markdown(summary: dict[str, Any]) -> str:
    return (
        "# Worker Health Summary\n\n"
        f"- Samples: `{summary['sample_count']}`\n"
        f"- RSS min bytes: `{summary['rss_bytes_min']}`\n"
        f"- RSS max bytes: `{summary['rss_bytes_max']}`\n"
        f"- RSS delta bytes: `{summary['rss_bytes_delta']}`\n"
        f"- Monotonic RSS increase: `{summary['monotonic_rss_increase']}`\n"
        f"- Median worker_execute_s: `{summary['worker_execute_median_s']:.6f}`\n"
    )


def _render_sequence_summary_markdown(rows: list[dict[str, Any]]) -> str:
    lines = ["# Gate S Sequence Summary", ""]
    for row in rows:
        lines.append(
            f"- `{row['mode']}` / `{row['sequence_label']}` / repeat `{row['benchmark_repeat']}`:"
            f" request_count=`{row['request_count']}`, session_total_wall_s=`{row['session_total_wall_s']:.6f}`,"
            f" per_request_median_wall_s=`{row['per_request_median_wall_s']:.6f}`, warm_only_median_wall_s=`{row['warm_only_median_wall_s']:.6f}`"
        )
    lines.append("")
    return "\n".join(lines)


def _render_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# OVH Session Runner Prototype v1",
        "",
        f"- Gate P reference: `{summary['gate_p_reference_summary_path']}`",
        f"- Gate S request rows: `{summary['request_row_count']}`",
        f"- No ranking changes: `{not summary['ranking_changed']}`",
        f"- No fallback used: `{summary['fallback_count'] == 0}`",
        "",
        "## Same-Workload Medians",
        "",
        "| Workload | persistent_warm_cli ms | session_runner_existing_worker ms | session_runner_autospawn_temp_worker ms | existing_worker gain vs CLI ms |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["same_workload_medians"]:
        lines.append(
            f"| `{Path(row['workload_manifest']).name}` | `{row['persistent_warm_cli_ms']:.3f}` | "
            f"`{row['session_runner_existing_worker_ms']:.3f}` | `{row['session_runner_autospawn_temp_worker_ms']:.3f}` | "
            f"`{row['existing_worker_gain_ms']:.3f}` |"
        )
    lines.extend(
        [
            "",
            "## Mixed Session",
            "",
            f"- Existing worker mixed per-request median ms: `{summary['mixed_existing_worker_per_request_ms']:.3f}`",
            f"- Pass bars met: `{summary['pass_bars']['all_passed']}`",
            "",
            "## Decision",
            "",
            f"- Recommendation: `{summary['recommendation']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _session_summary_row(
    *,
    mode: str,
    sequence_label: str,
    benchmark_repeat: int,
    request_count: int,
    session_total_wall_s: float,
    per_request_median_wall_s: float,
    warm_only_median_wall_s: float,
    worker_startup_s: float,
    selected_plan_id_stable: bool,
    correctness_stable: bool,
    fallback_count: int,
    rss_delta_bytes: int | None,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "sequence_label": sequence_label,
        "benchmark_repeat": benchmark_repeat,
        "request_count": request_count,
        "session_total_wall_s": round(float(session_total_wall_s), 9),
        "per_request_median_wall_s": round(float(per_request_median_wall_s), 9),
        "warm_only_median_wall_s": round(float(warm_only_median_wall_s), 9),
        "worker_startup_s": round(float(worker_startup_s), 9),
        "selected_plan_id_stable": bool(selected_plan_id_stable),
        "correctness_stable": bool(correctness_stable),
        "fallback_count": int(fallback_count),
        "rss_delta_bytes": rss_delta_bytes,
    }


def _run_persistent_warm_cli_mode(
    *,
    base_session_manifest: dict[str, Any],
    request_sequences: list[tuple[str, list[str]]],
    materials: dict[str, dict[str, Any]],
    outdir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    per_request_rows: list[dict[str, Any]] = []
    sequence_rows: list[dict[str, Any]] = []
    health_rows: list[dict[str, Any]] = []
    mode = "persistent_warm_cli"
    with tempfile.TemporaryDirectory(prefix="aqs_gate_s_cli_") as tempdir:
        socket_path = Path(tempdir) / "worker.sock"
        with PersistentWorkerProcess(socket_path) as worker:
            client = PersistentExecutorClient(socket_path, timeout_s=30.0)
            _prime_existing_worker(client=client, base_request_material=materials["run01"])
            for benchmark_repeat in range(1, BENCHMARK_REPEATS + 1):
                for sequence_label, request_ids in request_sequences:
                    session_started = time.perf_counter()
                    before_status = client.status()
                    health_rows.append(
                        _health_row(
                            mode=mode,
                            sequence_label=sequence_label,
                            benchmark_repeat=benchmark_repeat,
                            label="before_first_request",
                            status=before_status,
                        )
                    )
                    session_request_rows: list[dict[str, Any]] = []
                    for index, request_id in enumerate(request_ids, start=1):
                        request = materials[request_id]["request"]
                        payload_path = outdir / "raw" / mode / sequence_label / f"repeat_{benchmark_repeat}" / f"{index:02d}.json"
                        payload, cli_wall_s = _run_execute_cli(
                            manifest_path=request["workload_manifest"],
                            plan_bundle_path=request["plan_bundle"],
                            socket_path=str(socket_path),
                            out_path=payload_path,
                            session_manifest=base_session_manifest,
                        )
                        row = {
                            "request_id": f"{sequence_label}_{index:02d}_{request_id}",
                            "workload_manifest": _normalized(REPO_ROOT / request["workload_manifest"]),
                            "mode": mode,
                            "sequence_label": sequence_label,
                            "benchmark_repeat": benchmark_repeat,
                            "cli_wall_s": cli_wall_s,
                            "driver_total_s": float(payload.get("driver_total_s") or 0.0),
                            "outer_driver_overhead_s": float(payload.get("outer_driver_overhead_s") or 0.0),
                            "worker_execute_s": float((payload.get("driver_timing_json") or {}).get("worker_execute_s") or 0.0),
                            "worker_request_dispatch_s": float((payload.get("driver_timing_json") or {}).get("worker_request_dispatch_s") or 0.0),
                            "worker_reply_s": float((payload.get("driver_timing_json") or {}).get("worker_reply_s") or 0.0),
                            "worker_session_id": (payload.get("persistent_executor_provenance") or {}).get("worker_session_id"),
                            "session_request_index": int((payload.get("driver_timing_json") or {}).get("session_request_index") or 0),
                            "selected_plan_id": (payload.get("selected_plan") or {}).get("plan_id"),
                            "correctness_ok": _correctness_ok(payload),
                            "fallback_used": bool((payload.get("persistent_executor_provenance") or {}).get("fallback_used")),
                            "fallback_reason": (payload.get("persistent_executor_provenance") or {}).get("fallback_reason"),
                        }
                        per_request_rows.append(row)
                        session_request_rows.append(row)
                        status = client.status()
                        health_rows.append(
                            _health_row(
                                mode=mode,
                                sequence_label=sequence_label,
                                benchmark_repeat=benchmark_repeat,
                                label="after_request",
                                status=status,
                                request_id=row["request_id"],
                                workload_manifest=row["workload_manifest"],
                            )
                        )
                    after_status = client.status()
                    health_rows.append(
                        _health_row(
                            mode=mode,
                            sequence_label=sequence_label,
                            benchmark_repeat=benchmark_repeat,
                            label="after_session",
                            status=after_status,
                        )
                    )
                    session_total_wall_s = round(max(time.perf_counter() - session_started, 0.0), 9)
                    sequence_rows.append(
                        _session_summary_row(
                            mode=mode,
                            sequence_label=sequence_label,
                            benchmark_repeat=benchmark_repeat,
                            request_count=len(session_request_rows),
                            session_total_wall_s=session_total_wall_s,
                            per_request_median_wall_s=_median([row["cli_wall_s"] for row in session_request_rows]),
                            warm_only_median_wall_s=_median([row["cli_wall_s"] for row in session_request_rows]),
                            worker_startup_s=0.0,
                            selected_plan_id_stable=len({row["selected_plan_id"] for row in session_request_rows}) <= len({row["workload_manifest"] for row in session_request_rows}),
                            correctness_stable=all(bool(row["correctness_ok"]) for row in session_request_rows),
                            fallback_count=sum(1 for row in session_request_rows if row["fallback_used"]),
                            rss_delta_bytes=(
                                int((after_status.get("health") or {}).get("rss_bytes") or 0)
                                - int((before_status.get("health") or {}).get("rss_bytes") or 0)
                            ),
                        )
                    )
    return per_request_rows, sequence_rows, health_rows


def _run_session_runner_mode(
    *,
    mode: str,
    base_session_manifest: dict[str, Any],
    request_sequences: list[tuple[str, list[str]]],
    outdir: Path,
    spawn_temp_worker: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    per_request_rows: list[dict[str, Any]] = []
    sequence_rows: list[dict[str, Any]] = []
    health_rows: list[dict[str, Any]] = []
    if spawn_temp_worker:
        for benchmark_repeat in range(1, BENCHMARK_REPEATS + 1):
            for sequence_label, request_ids in request_sequences:
                session_manifest = _sequence_manifest(base_session_manifest, request_ids, prefix=f"{sequence_label}_r{benchmark_repeat}")
                socket_path = Path(tempfile.gettempdir()) / (
                    f"aqs-gs-{benchmark_repeat}-{abs(hash((mode, sequence_label, benchmark_repeat))) & 0xFFFFFF:x}.sock"
                )
                session_outdir = outdir / "sessions" / mode / sequence_label / f"repeat_{benchmark_repeat}"
                summary = run_session(
                    session_manifest=session_manifest,
                    session_manifest_path=f"{SESSION_MANIFEST_PATH}#{sequence_label}",
                    socket_path=socket_path,
                    outdir=session_outdir,
                    spawn_temp_worker=True,
                    allow_one_shot_fallback=False,
                    runner_mode=mode,
                )
                for row in summary["trace_rows"]:
                    per_request_rows.append(
                        {
                            **row,
                            "mode": mode,
                            "sequence_label": sequence_label,
                            "benchmark_repeat": benchmark_repeat,
                            "cli_wall_s": float(row["request_wall_s"]),
                        }
                    )
                for row in summary["health_rows"]:
                    health_rows.append(
                        {
                            **row,
                            "mode": mode,
                            "sequence_label": sequence_label,
                            "benchmark_repeat": benchmark_repeat,
                        }
                    )
                start_status = next((row for row in summary["health_rows"] if row["label"] == "before_first_request"), {})
                end_status = next((row for row in reversed(summary["health_rows"]) if row["label"] == "after_session"), {})
                sequence_rows.append(
                    _session_summary_row(
                        mode=mode,
                        sequence_label=sequence_label,
                        benchmark_repeat=benchmark_repeat,
                        request_count=summary["request_count"],
                        session_total_wall_s=summary["session_total_wall_s"],
                        per_request_median_wall_s=summary["per_request_median_wall_s"],
                        warm_only_median_wall_s=summary["warm_only_median_wall_s"],
                        worker_startup_s=summary["worker_startup_s"],
                        selected_plan_id_stable=summary["selected_plan_id_stable"],
                        correctness_stable=summary["correctness_stable"],
                        fallback_count=summary["fallback_count"],
                        rss_delta_bytes=(
                            int((end_status.get("health") or {}).get("rss_bytes") or 0)
                            - int((start_status.get("health") or {}).get("rss_bytes") or 0)
                        ),
                    )
                )
        return per_request_rows, sequence_rows, health_rows

    with tempfile.TemporaryDirectory(prefix="aqs_gate_s_session_") as tempdir:
        socket_path = Path(tempdir) / "worker.sock"
        with PersistentWorkerProcess(socket_path) as worker:
            client = PersistentExecutorClient(socket_path, timeout_s=30.0)
            materials = _prepare_request_materials(base_session_manifest)
            _prime_existing_worker(client=client, base_request_material=materials["run01"])
            for benchmark_repeat in range(1, BENCHMARK_REPEATS + 1):
                for sequence_label, request_ids in request_sequences:
                    session_manifest = _sequence_manifest(base_session_manifest, request_ids, prefix=f"{sequence_label}_r{benchmark_repeat}")
                    session_outdir = outdir / "sessions" / mode / sequence_label / f"repeat_{benchmark_repeat}"
                    summary = run_session(
                        session_manifest=session_manifest,
                        session_manifest_path=f"{SESSION_MANIFEST_PATH}#{sequence_label}",
                        socket_path=socket_path,
                        outdir=session_outdir,
                        spawn_temp_worker=False,
                        allow_one_shot_fallback=False,
                        runner_mode=mode,
                    )
                    for row in summary["trace_rows"]:
                        per_request_rows.append(
                            {
                                **row,
                                "mode": mode,
                                "sequence_label": sequence_label,
                                "benchmark_repeat": benchmark_repeat,
                                "cli_wall_s": float(row["request_wall_s"]),
                            }
                        )
                    for row in summary["health_rows"]:
                        health_rows.append(
                            {
                                **row,
                                "mode": mode,
                                "sequence_label": sequence_label,
                                "benchmark_repeat": benchmark_repeat,
                            }
                        )
                    start_status = next((row for row in summary["health_rows"] if row["label"] == "before_first_request"), {})
                    end_status = next((row for row in reversed(summary["health_rows"]) if row["label"] == "after_session"), {})
                    sequence_rows.append(
                        _session_summary_row(
                            mode=mode,
                            sequence_label=sequence_label,
                            benchmark_repeat=benchmark_repeat,
                            request_count=summary["request_count"],
                            session_total_wall_s=summary["session_total_wall_s"],
                            per_request_median_wall_s=summary["per_request_median_wall_s"],
                            warm_only_median_wall_s=summary["warm_only_median_wall_s"],
                            worker_startup_s=summary["worker_startup_s"],
                            selected_plan_id_stable=summary["selected_plan_id_stable"],
                            correctness_stable=summary["correctness_stable"],
                            fallback_count=summary["fallback_count"],
                            rss_delta_bytes=(
                                int((end_status.get("health") or {}).get("rss_bytes") or 0)
                                - int((start_status.get("health") or {}).get("rss_bytes") or 0)
                            ),
                        )
                    )
    return per_request_rows, sequence_rows, health_rows


def _mode_workload_median(rows: list[dict[str, Any]], mode: str, workload_manifest: str, *, same_only: bool = True) -> float:
    filtered = [
        float(row["cli_wall_s"])
        for row in rows
        if row["mode"] == mode
        and row["workload_manifest"] == workload_manifest
        and (not same_only or row["sequence_label"].startswith("same_"))
    ]
    return _median(filtered) * 1000.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the OVH Gate S session-runner packaging path")
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR)
    args = parser.parse_args()

    outdir = REPO_ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    base_session_manifest = _load_base_session_manifest()
    materials = _prepare_request_materials(base_session_manifest)
    request_sequences: list[tuple[str, list[str]]] = []
    for request_id in ("run01", "run06", "run08"):
        for length in SAME_LENGTHS:
            request_sequences.append((f"same_{request_id}_x{length}", [request_id] * length))
    request_sequences.append(("mixed_trio_x6", list(MIXED_ORDER)))

    cli_rows, cli_sequences, cli_health = _run_persistent_warm_cli_mode(
        base_session_manifest=base_session_manifest,
        request_sequences=request_sequences,
        materials=materials,
        outdir=outdir,
    )
    existing_rows, existing_sequences, existing_health = _run_session_runner_mode(
        mode="session_runner_existing_worker",
        base_session_manifest=base_session_manifest,
        request_sequences=request_sequences,
        outdir=outdir,
        spawn_temp_worker=False,
    )
    autospawn_rows, autospawn_sequences, autospawn_health = _run_session_runner_mode(
        mode="session_runner_autospawn_temp_worker",
        base_session_manifest=base_session_manifest,
        request_sequences=request_sequences,
        outdir=outdir,
        spawn_temp_worker=True,
    )

    per_request_rows = cli_rows + existing_rows + autospawn_rows
    sequence_rows = cli_sequences + existing_sequences + autospawn_sequences
    health_rows = cli_health + existing_health + autospawn_health

    _write_csv(outdir / "per_request.csv", per_request_rows)
    _dump_jsonl(outdir / "request_trace.jsonl", per_request_rows)
    _dump_jsonl(outdir / "worker_health.jsonl", health_rows)
    if health_rows:
        _dump_json(outdir / "worker_health_start.json", health_rows[0])
        _dump_json(outdir / "worker_health_end.json", health_rows[-1])

    same_workload_medians = []
    workload_names = {
        "run01": _normalized(REPO_ROOT / "workloads/manifests/imported/ovh_v2/01_real_dense_ring6_amplitude.yaml"),
        "run06": _normalized(REPO_ROOT / "workloads/manifests/imported/ovh_v2/06_star_graph_phase_amplitude_heldout_low.yaml"),
        "run08": _normalized(REPO_ROOT / "workloads/manifests/imported/ovh_v2/08_parity_iqp_batched_heldout_medium.yaml"),
    }
    for request_id, workload_manifest in workload_names.items():
        cli_ms = _mode_workload_median(per_request_rows, "persistent_warm_cli", workload_manifest)
        existing_ms = _mode_workload_median(per_request_rows, "session_runner_existing_worker", workload_manifest)
        autospawn_ms = _mode_workload_median(per_request_rows, "session_runner_autospawn_temp_worker", workload_manifest)
        same_workload_medians.append(
            {
                "request_id": request_id,
                "workload_manifest": workload_manifest,
                "persistent_warm_cli_ms": cli_ms,
                "session_runner_existing_worker_ms": existing_ms,
                "session_runner_autospawn_temp_worker_ms": autospawn_ms,
                "existing_worker_gain_ms": round(cli_ms - existing_ms, 3),
            }
        )

    mixed_existing_worker_rows = [
        row for row in per_request_rows
        if row["mode"] == "session_runner_existing_worker" and row["sequence_label"] == "mixed_trio_x6"
    ]
    health_summary = _rows_to_health_summary(health_rows)
    health_summary["worker_execute_median_s"] = _median(
        [
            float(row["worker_execute_s"])
            for row in per_request_rows
            if row["mode"] in {"persistent_warm_cli", "session_runner_existing_worker", "session_runner_autospawn_temp_worker"}
        ]
    )
    pass_bars = {
        "existing_worker_gain_ms_each_workload": all(row["existing_worker_gain_ms"] > 150.0 for row in same_workload_medians),
        "mixed_existing_worker_under_500ms": _median([row["cli_wall_s"] for row in mixed_existing_worker_rows]) * 1000.0 < 500.0 if mixed_existing_worker_rows else False,
        "worker_execute_under_120ms": all(
            _median(
                [
                    float(row["worker_execute_s"])
                    for row in per_request_rows
                    if row["mode"] == mode
                ]
            )
            < 0.120
            for mode in ("session_runner_existing_worker", "session_runner_autospawn_temp_worker")
        ),
        "dispatch_reply_under_5ms": all(
            _median(
                [
                    float(row["worker_request_dispatch_s"]) + float(row["worker_reply_s"])
                    for row in per_request_rows
                    if row["mode"] == mode
                ]
            )
            < 0.005
            for mode in ("session_runner_existing_worker", "session_runner_autospawn_temp_worker", "persistent_warm_cli")
        ),
        "no_selected_plan_drift": all(row["selected_plan_id_stable"] for row in sequence_rows),
        "no_correctness_drift": all(row["correctness_stable"] for row in sequence_rows),
        "no_silent_fallback": all(not bool(row["fallback_used"]) for row in per_request_rows),
        "no_obvious_monotonic_memory_leak": not bool(health_summary["monotonic_rss_increase"]),
    }
    pass_bars["all_passed"] = all(bool(value) for value in pass_bars.values())

    summary = {
        "gate_p_reference_summary_path": _normalized(REPO_ROOT / GATE_P_REFERENCE_SUMMARY),
        "gate_s_policy_path": _normalized(REPO_ROOT / "docs/reports/ovh_gate_s_policy.md"),
        "session_manifest_path": _normalized(REPO_ROOT / SESSION_MANIFEST_PATH),
        "request_row_count": len(per_request_rows),
        "sequence_row_count": len(sequence_rows),
        "health_row_count": len(health_rows),
        "ranking_changed": False,
        "same_workload_medians": same_workload_medians,
        "mixed_existing_worker_per_request_ms": round(_median([row["cli_wall_s"] for row in mixed_existing_worker_rows]) * 1000.0, 3) if mixed_existing_worker_rows else 0.0,
        "health_summary": health_summary,
        "pass_bars": pass_bars,
        "fallback_count": sum(1 for row in per_request_rows if row["fallback_used"]),
        "recommendation": (
            "worth productizing further as a lighter client/session packaging path"
            if pass_bars["all_passed"]
            else "not enough gain or operational headroom yet; keep this prototype local and performance-only"
        ),
    }

    _dump_json(outdir / "summary.json", summary)
    (outdir / "summary.md").write_text(_render_summary_markdown(summary), encoding="utf-8")
    _dump_json(outdir / "sequence_summary.json", {"rows": sequence_rows})
    (outdir / "sequence_summary.md").write_text(_render_sequence_summary_markdown(sequence_rows), encoding="utf-8")
    (outdir / "worker_health_summary.md").write_text(_render_health_summary_markdown(health_summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
