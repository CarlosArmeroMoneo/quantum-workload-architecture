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

from aqs.doctor import collect_system_profile  # noqa: E402
from aqs.execution import (  # noqa: E402
    _build_persistent_request_context,
    _build_plan_bundle_scope,
    _load_plan_bundle,
)
from aqs.manifest import load_yaml  # noqa: E402
from aqs.persistent_executor import (  # noqa: E402
    PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
    PersistentExecutorClient,
)
from aqs.planner import load_system_manifest  # noqa: E402
from aqs.repo_metadata import capture_repo_metadata  # noqa: E402


def _dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
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
    return round(statistics.median(values), 9)


def _manifest_name(path: str | Path) -> str:
    return Path(path).name


def _stem(path: str | Path) -> str:
    return Path(path).stem


def _timing(payload: dict[str, Any], key: str) -> float:
    return float((payload.get("driver_timing_json") or {}).get(key) or 0.0)


def _health_event(*, label: str, status: dict[str, Any], manifest_path: str | None = None, mode: str | None = None, session_label: str | None = None, sequence_index: int | None = None) -> dict[str, Any]:
    return {
        "recorded_at": time.time(),
        "label": label,
        "manifest_path": manifest_path,
        "mode": mode,
        "session_label": session_label,
        "sequence_index": sequence_index,
        **status,
    }


class WorkerProcess:
    def __init__(
        self,
        socket_path: Path,
        *,
        replace_live_worker: bool = False,
        max_requests: int | None = None,
        max_session_seconds: float | None = None,
    ):
        self.socket_path = socket_path
        self.replace_live_worker = replace_live_worker
        self.max_requests = max_requests
        self.max_session_seconds = max_session_seconds
        self.proc: subprocess.Popen[str] | None = None

    def _command(self) -> list[str]:
        command = [
            sys.executable,
            "-m",
            "aqs",
            "persistent-executor",
            "serve",
            "--socket",
            str(self.socket_path),
        ]
        if self.replace_live_worker:
            command.append("--replace-live-worker")
        if self.max_requests is not None:
            command.extend(["--max-requests", str(self.max_requests)])
        if self.max_session_seconds is not None:
            command.extend(["--max-session-seconds", str(self.max_session_seconds)])
        return command

    def __enter__(self) -> WorkerProcess:
        self.proc = subprocess.Popen(
            self._command(),
            cwd=str(REPO_ROOT),
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.wait_ready()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.proc is None:
            return
        try:
            if self.socket_path.exists():
                self.shutdown()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5.0)

    def _logs(self) -> str:
        if self.proc is None:
            return ""
        stdout = ""
        stderr = ""
        if self.proc.stdout is not None:
            try:
                stdout = self.proc.stdout.read()
            except Exception:
                stdout = ""
        if self.proc.stderr is not None:
            try:
                stderr = self.proc.stderr.read()
            except Exception:
                stderr = ""
        return f"stdout:\n{stdout}\n\nstderr:\n{stderr}"

    def wait_ready(self, *, timeout_s: float = 10.0) -> dict[str, Any]:
        deadline = time.time() + timeout_s
        last_error: Exception | None = None
        while time.time() < deadline:
            if self.proc is not None and self.proc.poll() is not None:
                raise SystemExit(
                    f"persistent worker exited before becoming ready with code {self.proc.returncode}:\n{self._logs()}"
                )
            try:
                status = self.status(timeout_s=1.0)
                if status.get("ok"):
                    return status
            except Exception as exc:  # pragma: no cover - startup retry guard
                last_error = exc
                time.sleep(0.05)
        raise SystemExit(f"persistent worker did not become ready: {last_error}")

    def client(self, *, timeout_s: float = 30.0) -> PersistentExecutorClient:
        return PersistentExecutorClient(self.socket_path, timeout_s=timeout_s)

    def ping(self, *, timeout_s: float = 30.0) -> dict[str, Any]:
        return self.client(timeout_s=timeout_s).ping()

    def status(self, *, timeout_s: float = 30.0) -> dict[str, Any]:
        return self.client(timeout_s=timeout_s).status()

    def shutdown(self, *, timeout_s: float = 30.0) -> dict[str, Any]:
        payload = self.client(timeout_s=timeout_s).shutdown()
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if not self.socket_path.exists():
                break
            time.sleep(0.05)
        return payload


def _wait_for_new_session(socket_path: Path, previous_session_id: str, *, timeout_s: float = 10.0) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status = PersistentExecutorClient(socket_path, timeout_s=1.0).status()
            if status.get("ok") and status.get("worker_session_id") != previous_session_id:
                return status
        except Exception as exc:  # pragma: no cover - handoff retry guard
            last_error = exc
        time.sleep(0.05)
    raise SystemExit(
        f"replacement worker on {socket_path} did not become ready with a new session id: {last_error}"
    )


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
    allow_one_shot_fallback: bool = False,
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
    if allow_one_shot_fallback:
        command.append("--allow-one-shot-fallback")

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


def _sample_row(
    *,
    manifest_path: str,
    mode: str,
    sample: dict[str, Any],
    session_label: str | None = None,
    sequence_name: str | None = None,
    request_ordinal: int | None = None,
    session_total_s: float | None = None,
) -> dict[str, Any]:
    payload = sample["payload"]
    run = payload["execution_run"]
    accuracy = payload.get("accuracy_eval") or {}
    persistent = payload.get("persistent_executor_provenance") or {}
    return {
        "manifest_path": str(Path(manifest_path).resolve()),
        "manifest_name": _manifest_name(manifest_path),
        "mode": mode,
        "session_label": session_label,
        "sequence_name": sequence_name,
        "request_ordinal": request_ordinal,
        "cli_wall_s": float(sample["cli_wall_s"]),
        "session_total_s": float(session_total_s if session_total_s is not None else sample["cli_wall_s"]),
        "driver_total_s": float(payload.get("driver_total_s") or 0.0),
        "outer_driver_overhead_s": float(payload.get("outer_driver_overhead_s") or 0.0),
        "execute_plan_bundle_s": _timing(payload, "execute_plan_bundle_s"),
        "worker_startup_s": _timing(payload, "worker_startup_s"),
        "worker_request_dispatch_s": _timing(payload, "worker_request_dispatch_s"),
        "worker_execute_s": _timing(payload, "worker_execute_s"),
        "worker_reply_s": _timing(payload, "worker_reply_s"),
        "execution_wall_s": float(run.get("wall_s") or 0.0),
        "import_real_stack_s": _timing(payload, "import_real_stack_s"),
        "network_build_s": _timing(payload, "network_build_s"),
        "selected_plan_id": str(payload["selected_plan"].get("plan_id") or ""),
        "selection_source": str(payload.get("selection_source") or ""),
        "correctness_status": str(accuracy.get("status") or "unknown"),
        "execution_mode": str(payload.get("execution_mode") or "direct_executor"),
        "worker_session_id": persistent.get("worker_session_id"),
        "worker_warm": persistent.get("worker_warm"),
        "worker_request_index": persistent.get("worker_request_index"),
        "persistent_used": persistent.get("persistent_used"),
        "fallback_used": persistent.get("fallback_used"),
        "bundle_hit": persistent.get("bundle_hit"),
    }


def _mode_median_row(mode: str, samples: list[dict[str, Any]]) -> dict[str, Any]:
    numeric_keys = [
        "cli_wall_s",
        "session_total_s",
        "driver_total_s",
        "outer_driver_overhead_s",
        "execute_plan_bundle_s",
        "worker_startup_s",
        "worker_request_dispatch_s",
        "worker_execute_s",
        "worker_reply_s",
        "execution_wall_s",
        "import_real_stack_s",
        "network_build_s",
    ]
    row = {key: _median([float(sample[key]) for sample in samples]) for key in numeric_keys}
    row.update(
        {
            "mode": mode,
            "selected_plan_ids": sorted({str(sample["selected_plan_id"]) for sample in samples}),
            "selection_sources": sorted({str(sample["selection_source"]) for sample in samples}),
            "execution_modes": sorted({str(sample["execution_mode"]) for sample in samples}),
            "correctness_statuses": sorted({str(sample["correctness_status"]) for sample in samples}),
        }
    )
    return row


def _render_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# OVH Persistent Executor Prototype v1",
        "",
        f"- Gate: `{summary['gate_name']}`",
        f"- Benchmark repeats per mode: `{summary['benchmark_repeats']}`",
        f"- Sequence lengths: `{summary['sequence_lengths']}`",
        f"- Mixed session order: `{summary['mixed_sequence']}`",
        f"- Interpretation: {summary['interpretation']}",
        "",
    ]
    for row in summary["rows"]:
        lines.extend(
            [
                f"## `{_manifest_name(row['manifest_path'])}`",
                "",
                "| Mode | CLI Wall ms | Session Total ms | Worker Startup ms | Worker Execute ms | Dispatch+Reply ms | Import Stack ms | Network Build ms | Inner Wall ms |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for mode_row in row["mode_rows"]:
            lines.append(
                f"| {mode_row['mode']} | "
                f"{mode_row['cli_wall_s'] * 1000.0:.3f} | "
                f"{mode_row['session_total_s'] * 1000.0:.3f} | "
                f"{mode_row['worker_startup_s'] * 1000.0:.3f} | "
                f"{mode_row['worker_execute_s'] * 1000.0:.3f} | "
                f"{(mode_row['worker_request_dispatch_s'] + mode_row['worker_reply_s']) * 1000.0:.3f} | "
                f"{mode_row['import_real_stack_s'] * 1000.0:.3f} | "
                f"{mode_row['network_build_s'] * 1000.0:.3f} | "
                f"{mode_row['execution_wall_s'] * 1000.0:.3f} |"
            )
        lines.extend(
            [
                "",
                f"- Seed selected plan: `{row['seed_selected_plan_id']}`",
                f"- Selected plan id stable: `{row['selected_plan_id_stable']}`",
                f"- Correctness stable: `{row['correctness_stable']}`",
                f"- Warm gain vs one-shot bundle: `{row['warm_gain_s'] * 1000.0:.3f} ms`",
                f"- Cold session total gain vs one-shot bundle: `{row['cold_total_gain_s'] * 1000.0:.3f} ms`",
                f"- Gate P checks: `{row['gate_p_checks']}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def _render_sequence_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# OVH Persistent Executor Sequence Summary",
        "",
        f"- Session lengths: `{summary['sequence_lengths']}`",
        f"- Mixed session order: `{summary['mixed_sequence']}`",
        "",
        "| Session | Requests | Cold CLI ms | Warm CLI median ms | Warm Worker Execute median ms | RSS Delta MB | Plan Stable | Correctness Stable |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in summary["sessions"]:
        lines.append(
            f"| {row['session_label']} | {row['request_count']} | "
            f"{row['cold_cli_wall_s'] * 1000.0:.3f} | "
            f"{row['warm_cli_wall_median_s'] * 1000.0:.3f} | "
            f"{row['warm_worker_execute_median_s'] * 1000.0:.3f} | "
            f"{row['rss_delta_mb']:.3f} | "
            f"{row['selected_plan_id_stable']} | "
            f"{row['correctness_stable']} |"
        )
    return "\n".join(lines) + "\n"


def _render_compatibility_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Persistent Executor Compatibility Reject Matrix",
        "",
        "| Case | Expected | Actual | Passed | Reject Reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in payload["cases"]:
        lines.append(
            f"| {case['case']} | {case['expected']} | {case['actual']} | {case['passed']} | {case['reason']} |"
        )
    return "\n".join(lines) + "\n"


def _render_worker_health_summary(events: list[dict[str, Any]]) -> str:
    sessions: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        session_id = str(event.get("worker_session_id") or "unknown")
        sessions.setdefault(session_id, []).append(event)
    lines = [
        "# Persistent Executor Worker Health Summary",
        "",
        "| Session | Samples | RSS Delta MB | Max Request Count | Max Session Uptime s |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for session_id, rows in sorted(sessions.items()):
        rss_values = [float((row.get("health") or {}).get("rss_bytes") or 0.0) for row in rows]
        uptime_values = [float(row.get("session_uptime_s") or 0.0) for row in rows]
        request_values = [int(row.get("request_count") or 0) for row in rows]
        rss_delta_mb = 0.0
        if rss_values:
            rss_delta_mb = (rss_values[-1] - rss_values[0]) / (1024.0 * 1024.0)
        lines.append(
            f"| {session_id} | {len(rows)} | {rss_delta_mb:.3f} | {max(request_values or [0])} | {max(uptime_values or [0.0]):.3f} |"
        )
    return "\n".join(lines) + "\n"


def _interpretation(rows: list[dict[str, Any]]) -> str:
    if rows and all(row["gate_p_pass"] for row in rows):
        return (
            "Gate P passed: persistent warm bundle requests remained materially faster than one-shot bundle hits across "
            "the OVH trio, cold session totals still beat one-shot totals, and the worker kept strict plan-id/correctness parity."
        )
    return (
        "Gate P did not clear every conservative productization threshold. Persistent execution remains promising, but the "
        "next branch should stay performance-only and target the surviving outer client/driver tax above the worker."
    )


def _case_result(case: str, expected: str, response: dict[str, Any]) -> dict[str, Any]:
    if response.get("ok"):
        actual = "accepted"
        reason = ""
    else:
        actual = str((response.get("error") or {}).get("reason_code") or "rejected")
        reason = str((response.get("persistent_executor_provenance") or {}).get("compatibility_reject_reason") or "")
    return {
        "case": case,
        "expected": expected,
        "actual": actual,
        "passed": bool((expected == "accepted" and response.get("ok")) or (expected != "accepted" and actual == expected)),
        "reason": reason,
    }


def _run_socket_recovery_checks(outdir: Path) -> dict[str, Any]:
    tempdir = Path(tempfile.mkdtemp(prefix="aqs_socket_recovery_"))
    live_socket = tempdir / "live.sock"
    stale_socket = tempdir / "stale.sock"
    restart_socket = tempdir / "restart.sock"
    checks: dict[str, Any] = {"checks": []}

    with WorkerProcess(live_socket) as worker:
        live_status = worker.status()
        conflict = subprocess.run(
            [
                sys.executable,
                "-m",
                "aqs",
                "persistent-executor",
                "serve",
                "--socket",
                str(live_socket),
            ],
            cwd=str(REPO_ROOT),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
        )
        checks["checks"].append(
            {
                "check": "live_socket_refusal",
                "passed": conflict.returncode != 0 and "live persistent executor already listening" in (conflict.stderr + conflict.stdout),
                "worker_session_id": live_status["worker_session_id"],
                "stderr": conflict.stderr.strip(),
            }
        )

        replacement = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "aqs",
                "persistent-executor",
                "serve",
                "--socket",
                str(live_socket),
                "--replace-live-worker",
            ],
            cwd=str(REPO_ROOT),
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            replacement_status = _wait_for_new_session(live_socket, live_status["worker_session_id"])
            checks["checks"].append(
                {
                    "check": "replace_live_worker",
                    "passed": replacement_status["worker_session_id"] != live_status["worker_session_id"],
                    "old_session_id": live_status["worker_session_id"],
                    "new_session_id": replacement_status["worker_session_id"],
                    "startup_socket_action": replacement_status.get("startup_socket_action"),
                }
            )
        finally:
            try:
                if live_socket.exists():
                    PersistentExecutorClient(live_socket, timeout_s=5.0).shutdown()
            except Exception:
                pass
            try:
                replacement.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                replacement.kill()
                replacement.wait(timeout=5.0)

    stale_socket.write_text("stale", encoding="utf-8")
    with WorkerProcess(stale_socket) as worker:
        stale_status = worker.status()
        checks["checks"].append(
            {
                "check": "stale_socket_cleanup",
                "passed": stale_status.get("startup_socket_action") == "stale_socket_removed",
                "startup_socket_action": stale_status.get("startup_socket_action"),
            }
        )

    with WorkerProcess(restart_socket) as worker:
        first_status = worker.status()
        worker.shutdown()
        time.sleep(0.1)
        checks["checks"].append(
            {
                "check": "shutdown_cleanup",
                "passed": not restart_socket.exists(),
                "worker_session_id": first_status["worker_session_id"],
            }
        )

    with WorkerProcess(restart_socket) as worker:
        restart_status = worker.status()
        checks["checks"].append(
            {
                "check": "restart_after_cleanup",
                "passed": restart_status["worker_session_id"] != first_status["worker_session_id"],
                "old_session_id": first_status["worker_session_id"],
                "new_session_id": restart_status["worker_session_id"],
            }
        )

    _dump_json(outdir / "socket_recovery_checks.json", checks)
    return checks


def _run_compatibility_reject_matrix(
    *,
    outdir: Path,
    manifest_path: str,
    system_manifest_path: str,
    bundle_path: str,
    objective: str,
    probe_strategy: str,
    planner_budget: str,
) -> dict[str, Any]:
    manifest = load_yaml(manifest_path)
    system_manifest = load_system_manifest(system_manifest_path)
    system_profile = collect_system_profile()
    repo_metadata = capture_repo_metadata()
    bundle_payload = _load_plan_bundle(bundle_path)
    selected_plan = dict(bundle_payload["selected_plan"])
    bundle_scope = _build_plan_bundle_scope(
        manifest_path,
        system_manifest_path,
        manifest,
        system_manifest,
        system_profile,
        repo_metadata,
        objective=objective,
        probe_strategy=probe_strategy,
        planner_budget=planner_budget,
        allow_distributed=False,
        max_candidates=None,
    )
    base_context = _build_persistent_request_context(
        bundle_scope=bundle_scope,
        selected_plan=selected_plan,
        selection_source="plan_bundle_reuse",
        graph_mode="off",
        execution_intent="require_real",
        precision=str(selected_plan.get("precision") or "complex128"),
        allow_distributed=False,
        bundle_hit=True,
    )
    base_request = {
        "protocol_version": PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
        "command": "execute_bundle",
        "request_context": base_context,
        "workload_manifest": manifest,
        "system_manifest": system_manifest,
        "selected_plan": selected_plan,
        "allow_distributed": False,
        "config": {
            "objective": objective,
            "precision": str(selected_plan.get("precision") or "complex128"),
            "probe_strategy": probe_strategy,
            "measurement_repeats": 3,
            "ttfr_repeats": 1,
            "execution_intent": "require_real",
            "replicate_idx": 0,
            "graph_mode": "off",
            "prewarm_mode": "none",
        },
    }

    temp_socket = Path(tempfile.gettempdir()) / f"aqs_compat_{int(time.time())}.sock"
    with WorkerProcess(temp_socket) as worker:
        client = worker.client(timeout_s=60.0)
        cases = [
            ("compatible_control", "accepted", lambda req: req),
            ("repo_commit_mismatch", "persistent_executor_rejected", lambda req: {**req, "request_context": {**req["request_context"], "repo_commit": "commit_other"}}),
            ("package_version_mismatch", "persistent_executor_rejected", lambda req: {**req, "request_context": {**req["request_context"], "package_version": "9.9.9"}}),
            ("execution_stack_version_mismatch", "persistent_executor_rejected", lambda req: {**req, "request_context": {**req["request_context"], "execution_stack_version": "aqs.execution.v999"}}),
            ("objective_mismatch", "persistent_executor_rejected", lambda req: {**req, "request_context": {**req["request_context"], "objective": "steady_state"}}),
            ("precision_mismatch", "persistent_executor_rejected", lambda req: {**req, "request_context": {**req["request_context"], "precision": "complex64"}}),
            ("system_id_mismatch", "persistent_executor_rejected", lambda req: {**req, "request_context": {**req["request_context"], "system_id": "sys_other"}}),
            ("selected_plan_id_mismatch", "persistent_executor_rejected", lambda req: {**req, "request_context": {**req["request_context"], "selected_plan_id": "plan_other"}}),
        ]
        payload = {"cases": []}
        for name, expected, mutator in cases:
            request = json.loads(json.dumps(mutator(base_request)))
            response = client.request(request)
            payload["cases"].append(_case_result(name, expected, response))

    _dump_json(outdir / "compatibility_reject_matrix.json", payload)
    (outdir / "compatibility_reject_matrix.md").write_text(_render_compatibility_markdown(payload), encoding="utf-8")
    return payload


def _workload_role(manifest_path: str) -> str:
    stem = _stem(manifest_path)
    if stem.startswith("01_"):
        return "low_repeat_amplitude"
    if stem.startswith("06_"):
        return "low_repeat_amplitude_heldout"
    return "control_medium_batched"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Gate P persistent executor prototype benchmarks on the OVH trio")
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

    per_request_rows: list[dict[str, Any]] = []
    health_events: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    seed_assets: dict[str, dict[str, Any]] = {}

    for manifest_index, manifest_path in enumerate(args.manifest):
        manifest_key = str(Path(manifest_path).resolve())
        manifest_stem = _stem(manifest_path)
        seed_bundle_path = seed_dir / f"{manifest_stem}.seed.plan_bundle.json"
        seed_plan_path = seed_dir / f"{manifest_stem}.seed.selected_plan.json"
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
        _write_seed_plan(seed_plan_path, seed_payload)
        seed_assets[manifest_key] = {
            "seed_bundle_path": seed_bundle_path,
            "seed_plan_path": seed_plan_path,
            "seed_selected_plan_id": str(seed_payload["selected_plan"].get("plan_id") or ""),
        }

        mode_samples: dict[str, list[dict[str, Any]]] = {
            "fresh": [],
            "plan_json": [],
            "one_shot_bundle": [],
            "persistent_cold_bundle": [],
            "persistent_warm_bundle": [],
        }

        for repeat_idx in range(args.benchmark_repeats):
            base_idx = (manifest_index * 1000) + 100 + (repeat_idx * 50)
            one_shot_modes = [
                ("fresh", {"plan_json_path": None, "plan_bundle_path": None}),
                ("plan_json", {"plan_json_path": str(seed_plan_path), "plan_bundle_path": None}),
                ("one_shot_bundle", {"plan_json_path": None, "plan_bundle_path": str(seed_bundle_path)}),
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
                row = _sample_row(manifest_path=manifest_path, mode=mode_name, sample=sample)
                mode_samples[mode_name].append(row)
                per_request_rows.append(row)

            socket_path = Path(tempfile.gettempdir()) / f"aqs_gate_p_{manifest_stem[:24]}_{repeat_idx}.sock"
            with WorkerProcess(socket_path) as worker:
                start_status = worker.status()
                health_events.append(
                    _health_event(
                        label="worker_start",
                        status=start_status,
                        manifest_path=manifest_path,
                        mode="persistent_session",
                        session_label=f"{manifest_stem}.rep{repeat_idx}",
                    )
                )
                cold = _run_execute(
                    manifest_path,
                    args.system_manifest,
                    objective=args.objective,
                    probe_strategy=args.probe_strategy,
                    planner_budget=args.planner_budget,
                    measurement_repeats=args.measurement_repeats,
                    execution_intent=args.execution_intent,
                    replicate_idx=base_idx + 10,
                    out_path=run_dir / f"{manifest_stem}.rep{repeat_idx}.persistent_cold_bundle.execute.json",
                    plan_bundle_path=str(seed_bundle_path),
                    persistent_worker_socket=str(socket_path),
                )
                cold_row = _sample_row(
                    manifest_path=manifest_path,
                    mode="persistent_cold_bundle",
                    sample=cold,
                    session_label=f"{manifest_stem}.rep{repeat_idx}",
                    request_ordinal=1,
                    session_total_s=float(cold["cli_wall_s"]) + _timing(cold["payload"], "worker_startup_s"),
                )
                mode_samples["persistent_cold_bundle"].append(cold_row)
                per_request_rows.append(cold_row)
                health_events.append(
                    _health_event(
                        label="after_request",
                        status=worker.status(),
                        manifest_path=manifest_path,
                        mode="persistent_cold_bundle",
                        session_label=f"{manifest_stem}.rep{repeat_idx}",
                        sequence_index=1,
                    )
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
                    out_path=run_dir / f"{manifest_stem}.rep{repeat_idx}.persistent_warm_bundle.execute.json",
                    plan_bundle_path=str(seed_bundle_path),
                    persistent_worker_socket=str(socket_path),
                )
                warm_row = _sample_row(
                    manifest_path=manifest_path,
                    mode="persistent_warm_bundle",
                    sample=warm,
                    session_label=f"{manifest_stem}.rep{repeat_idx}",
                    request_ordinal=2,
                )
                mode_samples["persistent_warm_bundle"].append(warm_row)
                per_request_rows.append(warm_row)
                health_events.append(
                    _health_event(
                        label="after_request",
                        status=worker.status(),
                        manifest_path=manifest_path,
                        mode="persistent_warm_bundle",
                        session_label=f"{manifest_stem}.rep{repeat_idx}",
                        sequence_index=2,
                    )
                )
                health_events.append(
                    _health_event(
                        label="before_shutdown",
                        status=worker.status(),
                        manifest_path=manifest_path,
                        mode="persistent_session",
                        session_label=f"{manifest_stem}.rep{repeat_idx}",
                    )
                )

        mode_rows = [_mode_median_row(mode, samples) for mode, samples in mode_samples.items()]
        mode_lookup = {row["mode"]: row for row in mode_rows}
        seed_plan_id = seed_assets[manifest_key]["seed_selected_plan_id"]
        selected_plan_id_stable = all(
            mode_lookup[mode]["selected_plan_ids"] == [seed_plan_id]
            for mode in mode_lookup
            if mode_lookup[mode]["selected_plan_ids"]
        )
        correctness_stable = all(
            mode_lookup[mode]["correctness_statuses"] == ["pass"]
            for mode in mode_lookup
        )
        warm_gain_s = round(
            mode_lookup["one_shot_bundle"]["cli_wall_s"] - mode_lookup["persistent_warm_bundle"]["cli_wall_s"],
            9,
        )
        cold_total_gain_s = round(
            mode_lookup["one_shot_bundle"]["cli_wall_s"] - mode_lookup["persistent_cold_bundle"]["session_total_s"],
            9,
        )
        gate_p_checks = {
            "warm_gain_gt_1s": warm_gain_s > 1.0,
            "persistent_cold_beats_one_shot": cold_total_gain_s > 0.0,
            "warm_worker_execute_lt_120ms": mode_lookup["persistent_warm_bundle"]["worker_execute_s"] < 0.120,
            "dispatch_reply_lt_5ms": (
                mode_lookup["persistent_warm_bundle"]["worker_request_dispatch_s"]
                + mode_lookup["persistent_warm_bundle"]["worker_reply_s"]
            ) < 0.005,
            "import_real_stack_near_zero": (
                mode_lookup["persistent_cold_bundle"]["import_real_stack_s"] <= 1e-9
                and mode_lookup["persistent_warm_bundle"]["import_real_stack_s"] <= 1e-9
            ),
            "selected_plan_id_stable": selected_plan_id_stable,
            "correctness_stable": correctness_stable,
        }
        rows.append(
            {
                "manifest_path": manifest_key,
                "manifest_role": _workload_role(manifest_path),
                "seed_selected_plan_id": seed_plan_id,
                "selected_plan_id_stable": selected_plan_id_stable,
                "correctness_stable": correctness_stable,
                "mode_rows": mode_rows,
                "warm_gain_s": warm_gain_s,
                "cold_total_gain_s": cold_total_gain_s,
                "gate_p_checks": gate_p_checks,
                "gate_p_pass": all(gate_p_checks.values()),
            }
        )

    sequence_lengths = [1, 2, 4, 8]
    mixed_sequence = [
        next(path for path in args.manifest if _stem(path).startswith("01_")),
        next(path for path in args.manifest if _stem(path).startswith("06_")),
        next(path for path in args.manifest if _stem(path).startswith("08_")),
        next(path for path in args.manifest if _stem(path).startswith("01_")),
        next(path for path in args.manifest if _stem(path).startswith("06_")),
        next(path for path in args.manifest if _stem(path).startswith("08_")),
    ]
    sequence_sessions: list[dict[str, Any]] = []

    for manifest_path in args.manifest:
        manifest_key = str(Path(manifest_path).resolve())
        manifest_stem = _stem(manifest_path)
        seed_bundle_path = seed_assets[manifest_key]["seed_bundle_path"]
        for session_length in sequence_lengths:
            socket_path = Path(tempfile.gettempdir()) / f"aqs_gate_p_seq_{manifest_stem[:18]}_{session_length}.sock"
            request_rows: list[dict[str, Any]] = []
            with WorkerProcess(socket_path) as worker:
                start_status = worker.status()
                health_events.append(
                    _health_event(
                        label="worker_start",
                        status=start_status,
                        manifest_path=manifest_path,
                        mode="persistent_sequence",
                        session_label=f"{manifest_stem}.len{session_length}",
                    )
                )
                for request_ordinal in range(1, session_length + 1):
                    sample = _run_execute(
                        manifest_path,
                        args.system_manifest,
                        objective=args.objective,
                        probe_strategy=args.probe_strategy,
                        planner_budget=args.planner_budget,
                        measurement_repeats=args.measurement_repeats,
                        execution_intent=args.execution_intent,
                        replicate_idx=9000 + len(sequence_sessions) * 100 + request_ordinal,
                        out_path=run_dir / f"{manifest_stem}.len{session_length}.req{request_ordinal}.execute.json",
                        plan_bundle_path=str(seed_bundle_path),
                        persistent_worker_socket=str(socket_path),
                    )
                    row = _sample_row(
                        manifest_path=manifest_path,
                        mode="persistent_sequence_bundle",
                        sample=sample,
                        session_label=f"{manifest_stem}.len{session_length}",
                        sequence_name=f"{manifest_stem}.len{session_length}",
                        request_ordinal=request_ordinal,
                    )
                    request_rows.append(row)
                    per_request_rows.append(row)
                    health_events.append(
                        _health_event(
                            label="after_request",
                            status=worker.status(),
                            manifest_path=manifest_path,
                            mode="persistent_sequence_bundle",
                            session_label=f"{manifest_stem}.len{session_length}",
                            sequence_index=request_ordinal,
                        )
                    )
                end_status = worker.status()
                health_events.append(
                    _health_event(
                        label="before_shutdown",
                        status=end_status,
                        manifest_path=manifest_path,
                        mode="persistent_sequence",
                        session_label=f"{manifest_stem}.len{session_length}",
                    )
                )
            warm_rows = request_rows[1:]
            sequence_sessions.append(
                {
                    "session_label": f"{manifest_stem}.len{session_length}",
                    "session_type": "same_workload",
                    "manifest_path": manifest_key,
                    "request_count": session_length,
                    "cold_cli_wall_s": float(request_rows[0]["cli_wall_s"]),
                    "warm_cli_wall_median_s": _median([float(row["cli_wall_s"]) for row in warm_rows]) if warm_rows else 0.0,
                    "warm_worker_execute_median_s": _median([float(row["worker_execute_s"]) for row in warm_rows]) if warm_rows else 0.0,
                    "selected_plan_id_stable": len({row["selected_plan_id"] for row in request_rows}) == 1,
                    "correctness_stable": len({row["correctness_status"] for row in request_rows}) == 1 and request_rows[0]["correctness_status"] == "pass",
                    "rss_delta_mb": round((((end_status.get("health") or {}).get("rss_bytes") or 0) - ((start_status.get("health") or {}).get("rss_bytes") or 0)) / (1024.0 * 1024.0), 6),
                    "worker_session_id": end_status.get("worker_session_id"),
                }
            )

    mixed_socket = Path(tempfile.gettempdir()) / "aqs_gate_p_mixed.sock"
    mixed_rows: list[dict[str, Any]] = []
    with WorkerProcess(mixed_socket) as worker:
        start_status = worker.status()
        health_events.append(
            _health_event(
                label="worker_start",
                status=start_status,
                mode="persistent_sequence",
                session_label="mixed.len6",
            )
        )
        for request_ordinal, manifest_path in enumerate(mixed_sequence, start=1):
            manifest_key = str(Path(manifest_path).resolve())
            seed_bundle_path = seed_assets[manifest_key]["seed_bundle_path"]
            manifest_stem = _stem(manifest_path)
            sample = _run_execute(
                manifest_path,
                args.system_manifest,
                objective=args.objective,
                probe_strategy=args.probe_strategy,
                planner_budget=args.planner_budget,
                measurement_repeats=args.measurement_repeats,
                execution_intent=args.execution_intent,
                replicate_idx=12000 + request_ordinal,
                out_path=run_dir / f"mixed.len6.req{request_ordinal}.{manifest_stem}.execute.json",
                plan_bundle_path=str(seed_bundle_path),
                persistent_worker_socket=str(mixed_socket),
            )
            row = _sample_row(
                manifest_path=manifest_path,
                mode="persistent_sequence_bundle",
                sample=sample,
                session_label="mixed.len6",
                sequence_name="mixed.len6",
                request_ordinal=request_ordinal,
            )
            mixed_rows.append(row)
            per_request_rows.append(row)
            health_events.append(
                _health_event(
                    label="after_request",
                    status=worker.status(),
                    manifest_path=manifest_path,
                    mode="persistent_sequence_bundle",
                    session_label="mixed.len6",
                    sequence_index=request_ordinal,
                )
            )
        end_status = worker.status()
        health_events.append(
            _health_event(
                label="before_shutdown",
                status=end_status,
                mode="persistent_sequence",
                session_label="mixed.len6",
            )
        )
    mixed_warm_rows = mixed_rows[1:]
    sequence_sessions.append(
        {
            "session_label": "mixed.len6",
            "session_type": "mixed_workload",
            "manifest_paths": [str(Path(path).resolve()) for path in mixed_sequence],
            "request_count": len(mixed_sequence),
            "cold_cli_wall_s": float(mixed_rows[0]["cli_wall_s"]),
            "warm_cli_wall_median_s": _median([float(row["cli_wall_s"]) for row in mixed_warm_rows]) if mixed_warm_rows else 0.0,
            "warm_worker_execute_median_s": _median([float(row["worker_execute_s"]) for row in mixed_warm_rows]) if mixed_warm_rows else 0.0,
            "selected_plan_id_stable": all(
                row["selected_plan_id"] == seed_assets[row["manifest_path"]]["seed_selected_plan_id"]
                for row in mixed_rows
            ),
            "correctness_stable": all(row["correctness_status"] == "pass" for row in mixed_rows),
            "rss_delta_mb": round((((end_status.get("health") or {}).get("rss_bytes") or 0) - ((start_status.get("health") or {}).get("rss_bytes") or 0)) / (1024.0 * 1024.0), 6),
            "worker_session_id": end_status.get("worker_session_id"),
        }
    )

    summary = {
        "study": "ovh_persistent_executor_prototype_v1",
        "gate_name": "Gate P",
        "gate_policy_path": str((REPO_ROOT / "docs/reports/ovh_gate_p_policy.md").resolve()),
        "system_manifest_path": str(Path(args.system_manifest).resolve()),
        "objective": args.objective,
        "probe_strategy": args.probe_strategy,
        "planner_budget": args.planner_budget,
        "measurement_repeats": args.measurement_repeats,
        "execution_intent": args.execution_intent,
        "benchmark_repeats": int(args.benchmark_repeats),
        "sequence_lengths": sequence_lengths,
        "mixed_sequence": [_manifest_name(path) for path in mixed_sequence],
        "rows": rows,
    }
    summary["interpretation"] = _interpretation(rows)

    sequence_summary = {
        "study": "ovh_persistent_executor_prototype_v1",
        "sequence_lengths": sequence_lengths,
        "mixed_sequence": [_manifest_name(path) for path in mixed_sequence],
        "sessions": sequence_sessions,
    }

    _dump_json(outdir / "summary.json", summary)
    (outdir / "summary.md").write_text(_render_summary_markdown(summary), encoding="utf-8")
    _write_csv(outdir / "per_request.csv", per_request_rows)
    _dump_json(outdir / "sequence_summary.json", sequence_summary)
    (outdir / "sequence_summary.md").write_text(_render_sequence_markdown(sequence_summary), encoding="utf-8")
    _dump_jsonl(outdir / "worker_health.jsonl", health_events)
    if health_events:
        _dump_json(outdir / "worker_health_start.json", health_events[0])
        _dump_json(outdir / "worker_health_end.json", health_events[-1])
    (outdir / "worker_health_summary.md").write_text(_render_worker_health_summary(health_events), encoding="utf-8")

    _run_socket_recovery_checks(outdir)
    first_manifest = next(path for path in args.manifest if _stem(path).startswith("01_"))
    first_manifest_key = str(Path(first_manifest).resolve())
    _run_compatibility_reject_matrix(
        outdir=outdir,
        manifest_path=first_manifest,
        system_manifest_path=args.system_manifest,
        bundle_path=str(seed_assets[first_manifest_key]["seed_bundle_path"]),
        objective=args.objective,
        probe_strategy=args.probe_strategy,
        planner_budget=args.planner_budget,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
