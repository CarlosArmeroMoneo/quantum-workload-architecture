from __future__ import annotations

import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any

from .doctor import collect_system_profile
from .execution import (
    _assess_plan_bundle_compatibility,
    _build_execution_payload,
    _build_persistent_worker_request,
    _build_plan_bundle_scope,
    _load_plan_bundle,
    execute_selected_plan,
)
from .io import dump_json
from .manifest import load_yaml, validate_manifest
from .persistent_client import PersistentExecutorClient, _normalized_path
from .planner import load_system_manifest
from .repo_metadata import capture_repo_metadata


REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION_API_VERSION = "aqs.session.v1"


class SessionRunnerError(RuntimeError):
    pass


def _dump_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(float(statistics.median(values)), 9)


def _correctness_ok(payload: dict[str, Any]) -> bool:
    execution_ok = str((payload.get("execution_run") or {}).get("status") or "") == "success"
    accuracy = payload.get("accuracy_eval") or {}
    accuracy_ok = not accuracy or str(accuracy.get("status") or "") in {"pass", "ok", "success"}
    return bool(execution_ok and accuracy_ok)


def _health_row(
    *,
    label: str,
    status: dict[str, Any] | None,
    request_id: str | None = None,
    workload_manifest: str | None = None,
    runner_mode: str,
) -> dict[str, Any]:
    payload = {
        "recorded_at": time.time(),
        "label": label,
        "request_id": request_id,
        "workload_manifest": workload_manifest,
        "runner_mode": runner_mode,
    }
    if status:
        payload.update(status)
    return payload


def _render_session_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# OVH Session Runner Summary",
        "",
        f"- Session manifest: `{summary['session_manifest_path']}`",
        f"- Runner mode: `{summary['runner_mode']}`",
        f"- Spawned temp worker: `{summary['spawn_temp_worker']}`",
        f"- Request count: `{summary['request_count']}`",
        f"- Session total wall: `{summary['session_total_wall_s']:.6f} s`",
        f"- Per-request median wall: `{summary['per_request_median_wall_s']:.6f} s`",
        f"- Warm-only median wall: `{summary['warm_only_median_wall_s']:.6f} s`",
        f"- Selected plan stable: `{summary['selected_plan_id_stable']}`",
        f"- Correctness stable: `{summary['correctness_stable']}`",
        f"- Fallback used: `{summary['fallback_count']}` request(s)",
        "",
    ]
    return "\n".join(lines) + "\n"


class PersistentWorkerProcess:
    def __init__(
        self,
        socket_path: str | Path,
        *,
        replace_live_worker: bool = False,
        max_requests: int | None = None,
        max_session_seconds: float | None = None,
    ):
        self.socket_path = Path(socket_path).expanduser().resolve()
        self.replace_live_worker = bool(replace_live_worker)
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

    def start(self) -> dict[str, Any]:
        self.proc = subprocess.Popen(
            self._command(),
            cwd=str(REPO_ROOT),
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return self.wait_ready()

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
                raise SessionRunnerError(
                    f"persistent worker exited before becoming ready with code {self.proc.returncode}:\n{self._logs()}"
                )
            try:
                status = PersistentExecutorClient(self.socket_path, timeout_s=1.0).status()
                if status.get("ok"):
                    return status
            except Exception as exc:
                last_error = exc
                time.sleep(0.05)
        raise SessionRunnerError(f"persistent worker did not become ready: {last_error}")

    def shutdown(self, *, timeout_s: float = 10.0) -> dict[str, Any]:
        payload = PersistentExecutorClient(self.socket_path, timeout_s=timeout_s).shutdown()
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if not self.socket_path.exists():
                break
            time.sleep(0.05)
        if self.proc is not None:
            try:
                self.proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=timeout_s)
        return payload

    def __enter__(self) -> PersistentWorkerProcess:
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self.socket_path.exists():
                self.shutdown()
        except Exception:
            if self.proc is not None:
                self.proc.kill()
                self.proc.wait(timeout=5.0)


def _load_session_manifest(path: str | Path) -> dict[str, Any]:
    manifest = load_yaml(path)
    errors = validate_manifest(manifest, mode="real")
    if errors:
        raise SessionRunnerError(
            "session manifest did not validate in real mode:\n- " + "\n- ".join(errors)
        )
    return manifest


def _prepare_session_requests(
    *,
    session_manifest_path: str | Path,
    session_manifest: dict[str, Any],
    system_manifest: dict[str, Any],
    system_profile: dict[str, Any],
    repo_metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for request_entry in session_manifest["requests"]:
        lookup_started = time.perf_counter()
        workload_manifest = load_yaml(request_entry["workload_manifest"])
        bundle_payload = _load_plan_bundle(request_entry["plan_bundle"])
        bundle_lookup_s = round(max(time.perf_counter() - lookup_started, 0.0), 9)
        compatibility_started = time.perf_counter()
        bundle_scope = _build_plan_bundle_scope(
            request_entry["workload_manifest"],
            session_manifest["system_manifest"],
            workload_manifest,
            system_manifest,
            system_profile,
            repo_metadata,
            objective=session_manifest["objective"],
            probe_strategy=session_manifest["probe_strategy"],
            planner_budget=session_manifest["planner_budget"],
            allow_distributed=bool(session_manifest.get("allow_distributed")),
            max_candidates=None,
        )
        compatibility = _assess_plan_bundle_compatibility(bundle_payload, bundle_scope)
        compatibility_s = round(max(time.perf_counter() - compatibility_started, 0.0), 9)
        requests.append(
            {
                "id": request_entry["id"],
                "workload_manifest_path": request_entry["workload_manifest"],
                "plan_bundle_path": request_entry["plan_bundle"],
                "workload_manifest": workload_manifest,
                "bundle_payload": bundle_payload,
                "bundle_scope": bundle_scope,
                "bundle_lookup_s": bundle_lookup_s,
                "bundle_compatibility_check_s": compatibility_s,
                "compatibility": compatibility,
                "selection_source": "plan_bundle_reuse",
                "plan_json_path": None,
                "session_manifest_path": _normalized_path(session_manifest_path),
            }
        )
    return requests


def run_session(
    *,
    session_manifest: dict[str, Any],
    session_manifest_path: str | Path,
    socket_path: str | Path,
    outdir: str | Path,
    spawn_temp_worker: bool = False,
    replace_live_worker: bool = False,
    allow_one_shot_fallback: bool = False,
    runner_mode: str | None = None,
) -> dict[str, Any]:
    session_manifest_path = _normalized_path(session_manifest_path)
    socket_path = _normalized_path(socket_path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    requests_dir = outdir / "requests"
    requests_dir.mkdir(parents=True, exist_ok=True)

    system_manifest = load_system_manifest(session_manifest["system_manifest"])
    system_profile = collect_system_profile()
    repo_metadata = capture_repo_metadata()
    request_specs = _prepare_session_requests(
        session_manifest_path=session_manifest_path,
        session_manifest=session_manifest,
        system_manifest=system_manifest,
        system_profile=system_profile,
        repo_metadata=repo_metadata,
    )

    mode_label = runner_mode or ("session_runner_autospawn_temp_worker" if spawn_temp_worker else "session_runner_existing_worker")
    health_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    correctness_flags: list[bool] = []
    fallback_count = 0
    startup_status: dict[str, Any] | None = None
    final_status: dict[str, Any] | None = None
    total_started = time.perf_counter()

    worker: PersistentWorkerProcess | None = None
    if spawn_temp_worker:
        worker = PersistentWorkerProcess(
            socket_path,
            replace_live_worker=replace_live_worker,
        )
        startup_status = worker.start()

    client = PersistentExecutorClient(socket_path, timeout_s=60.0)
    try:
        if startup_status is None:
            try:
                startup_status = client.status()
            except Exception as exc:
                raise SessionRunnerError(f"persistent worker at {socket_path} is unavailable: {exc}") from exc
        health_rows.append(_health_row(label="before_first_request", status=startup_status, runner_mode=mode_label))

        for request_spec in request_specs:
            request_id = request_spec["id"]
            manifest_path = request_spec["workload_manifest_path"]
            selected_plan = dict(request_spec["bundle_payload"]["selected_plan"])
            plan_bundle_provenance = {
                "requested": True,
                "bundle_path": _normalized_path(request_spec["plan_bundle_path"]),
                "cache_status": "hit" if request_spec["compatibility"]["compatible"] else "rejected",
                "cache_reason": request_spec["compatibility"]["reason"],
                "write_status": "skipped_hit" if request_spec["compatibility"]["compatible"] else "skipped_rejected",
                "write_reason": (
                    "existing compatible bundle was reused without rewriting"
                    if request_spec["compatibility"]["compatible"]
                    else "existing bundle was incompatible and was left untouched"
                ),
                "bundle_id": request_spec["compatibility"].get("bundle_id"),
                "compatibility": request_spec["compatibility"],
            }

            request_started = time.perf_counter()
            if not request_spec["compatibility"]["compatible"]:
                reject_reason = request_spec["compatibility"]["reason"]
                if not allow_one_shot_fallback:
                    raise SessionRunnerError(f"request {request_id} bundle was incompatible: {reject_reason}")
                execution_payload = execute_selected_plan(
                    manifest_path,
                    session_manifest["system_manifest"],
                    objective=session_manifest["objective"],
                    probe_strategy=session_manifest["probe_strategy"],
                    planner_budget=session_manifest["planner_budget"],
                    allow_distributed=bool(session_manifest.get("allow_distributed")),
                    measurement_repeats=int(session_manifest["measurement_repeats"]),
                    execution_intent=session_manifest["execution_intent"],
                    plan_bundle_path=request_spec["plan_bundle_path"],
                    graph_mode=session_manifest["graph_mode"],
                )
                request_wall_s = round(max(time.perf_counter() - request_started, 0.0), 9)
                fallback_used = True
                fallback_reason = reject_reason
            else:
                request_payload = _build_persistent_worker_request(
                    command="execute_bundle",
                    bundle_scope=request_spec["bundle_scope"],
                    workload_manifest=request_spec["workload_manifest"],
                    system_manifest=system_manifest,
                    selected_plan=selected_plan,
                    config=type(
                        "SessionExecutionConfig",
                        (),
                        {
                            "objective": session_manifest["objective"],
                            "precision": str(selected_plan.get("precision") or "complex128"),
                            "probe_strategy": session_manifest["probe_strategy"],
                            "measurement_repeats": int(session_manifest["measurement_repeats"]),
                            "ttfr_repeats": 1,
                            "execution_intent": session_manifest["execution_intent"],
                            "replicate_idx": 0,
                            "graph_mode": session_manifest["graph_mode"],
                            "prewarm_mode": "none",
                        },
                    )(),
                    selection_source="plan_bundle_reuse",
                    allow_distributed=bool(session_manifest.get("allow_distributed")),
                )
                try:
                    worker_response = client.execute_bundle(request_payload)
                except Exception as exc:
                    if not allow_one_shot_fallback:
                        raise SessionRunnerError(f"persistent worker request failed for {request_id}: {exc}") from exc
                    execution_payload = execute_selected_plan(
                        manifest_path,
                        session_manifest["system_manifest"],
                        objective=session_manifest["objective"],
                        probe_strategy=session_manifest["probe_strategy"],
                        planner_budget=session_manifest["planner_budget"],
                        allow_distributed=bool(session_manifest.get("allow_distributed")),
                        measurement_repeats=int(session_manifest["measurement_repeats"]),
                        execution_intent=session_manifest["execution_intent"],
                        plan_bundle_path=request_spec["plan_bundle_path"],
                        graph_mode=session_manifest["graph_mode"],
                    )
                    request_wall_s = round(max(time.perf_counter() - request_started, 0.0), 9)
                    fallback_used = True
                    fallback_reason = str(exc)
                else:
                    request_wall_s = round(max(time.perf_counter() - request_started, 0.0), 9)
                    if not worker_response.get("ok"):
                        reject_reason = (
                            str(((worker_response.get("persistent_executor_provenance") or {}).get("compatibility_reject_reason")) or "")
                            or str(((worker_response.get("error") or {}).get("message")) or "")
                            or "persistent worker rejected the request"
                        )
                        if not allow_one_shot_fallback:
                            raise SessionRunnerError(f"persistent worker rejected {request_id}: {reject_reason}")
                        execution_payload = execute_selected_plan(
                            manifest_path,
                            session_manifest["system_manifest"],
                            objective=session_manifest["objective"],
                            probe_strategy=session_manifest["probe_strategy"],
                            planner_budget=session_manifest["planner_budget"],
                            allow_distributed=bool(session_manifest.get("allow_distributed")),
                            measurement_repeats=int(session_manifest["measurement_repeats"]),
                            execution_intent=session_manifest["execution_intent"],
                            plan_bundle_path=request_spec["plan_bundle_path"],
                            graph_mode=session_manifest["graph_mode"],
                        )
                        fallback_used = True
                        fallback_reason = reject_reason
                    else:
                        worker_timing = dict(worker_response.get("driver_timing_json") or {})
                        bundle = dict(worker_response["bundle"])
                        bundle["driver_timing_json"] = {
                            **dict(bundle.get("driver_timing_json") or {}),
                            **worker_timing,
                        }
                        persistent_executor_provenance = {
                            "requested": True,
                            "socket_path": socket_path,
                            "execution_mode": "persistent_executor",
                            "persistent_used": True,
                            "bundle_hit": True,
                            "worker_session_id": None,
                            "worker_warm": None,
                            "worker_start_time": None,
                            "worker_request_index": None,
                            "compatibility_match_reason": None,
                            "compatibility_reject_reason": None,
                            "fallback_used": False,
                            "fallback_reason": None,
                            **dict(worker_response.get("persistent_executor_provenance") or {}),
                        }
                        driver_timing = {
                            "load_manifest_s": 0.0,
                            "load_system_manifest_s": 0.0,
                            "collect_system_profile_s": 0.0,
                            "capture_repo_metadata_s": 0.0,
                            "normalize_manifest_s": 0.0,
                            "extract_features_s": 0.0,
                            "probe_s": 0.0,
                            "candidate_generation_s": 0.0,
                            "selection_s": 0.0,
                            "bundle_lookup_s": float(request_spec["bundle_lookup_s"]),
                            "bundle_compatibility_check_s": float(request_spec["bundle_compatibility_check_s"]),
                            "plan_bundle_lookup_s": float(request_spec["bundle_lookup_s"]),
                            "execute_plan_bundle_s": float(request_wall_s),
                            "plan_bundle_write_s": 0.0,
                            **dict(bundle.get("driver_timing_json") or {}),
                        }
                        execution_payload = _build_execution_payload(
                            manifest=request_spec["workload_manifest"],
                            system_manifest=system_manifest,
                            repo_metadata=repo_metadata,
                            probe=None,
                            selected_plan=selected_plan,
                            selection_source="plan_bundle_reuse",
                            execution_mode="persistent_executor",
                            plan_json_path=None,
                            plan_bundle_path=request_spec["plan_bundle_path"],
                            plan_bundle_provenance=plan_bundle_provenance,
                            persistent_executor_provenance=persistent_executor_provenance,
                            driver_timing=driver_timing,
                            bundle=bundle,
                            candidate_count=int((request_spec["bundle_payload"].get("selection_context") or {}).get("candidate_count") or 0),
                            total_s=request_wall_s,
                        )
                        fallback_used = False
                        fallback_reason = None

            if fallback_used:
                fallback_count += 1

            request_payload_path = requests_dir / f"{request_id}.execution.json"
            dump_json(execution_payload, request_payload_path)

            trace_row = {
                "request_id": request_id,
                "workload_manifest": _normalized_path(manifest_path),
                "runner_mode": mode_label,
                "request_wall_s": request_wall_s,
                "driver_total_s": float(execution_payload.get("driver_total_s") or 0.0),
                "outer_driver_overhead_s": float(execution_payload.get("outer_driver_overhead_s") or 0.0),
                "worker_execute_s": float((execution_payload.get("driver_timing_json") or {}).get("worker_execute_s") or 0.0),
                "worker_request_dispatch_s": float((execution_payload.get("driver_timing_json") or {}).get("worker_request_dispatch_s") or 0.0),
                "worker_reply_s": float((execution_payload.get("driver_timing_json") or {}).get("worker_reply_s") or 0.0),
                "worker_session_id": (execution_payload.get("persistent_executor_provenance") or {}).get("worker_session_id"),
                "session_request_index": int((execution_payload.get("driver_timing_json") or {}).get("session_request_index") or 0),
                "selected_plan_id": (execution_payload.get("selected_plan") or {}).get("plan_id"),
                "correctness_ok": _correctness_ok(execution_payload),
                "fallback_used": bool(fallback_used),
                "fallback_reason": fallback_reason,
                "execution_payload_path": _normalized_path(request_payload_path),
            }
            trace_rows.append(trace_row)
            correctness_flags.append(bool(trace_row["correctness_ok"]))

            try:
                request_status = client.status()
            except Exception:
                request_status = None
            health_rows.append(
                _health_row(
                    label="after_request",
                    status=request_status,
                    request_id=request_id,
                    workload_manifest=manifest_path,
                    runner_mode=mode_label,
                )
            )

        try:
            final_status = client.status()
        except Exception:
            final_status = None
        health_rows.append(_health_row(label="after_session", status=final_status, runner_mode=mode_label))
    finally:
        if spawn_temp_worker and worker is not None:
            try:
                worker.shutdown()
            except Exception:
                pass

    session_total_wall_s = round(max(time.perf_counter() - total_started, 0.0), 9)
    warm_rows = [row["request_wall_s"] for row in trace_rows if int(row.get("session_request_index") or 0) > 1]
    plan_ids_by_workload: dict[str, set[str]] = {}
    for row in trace_rows:
        plan_ids_by_workload.setdefault(str(row["workload_manifest"]), set()).add(str(row["selected_plan_id"] or ""))
    summary = {
        "api_version": SESSION_API_VERSION,
        "session_manifest_path": session_manifest_path,
        "runner_mode": mode_label,
        "spawn_temp_worker": bool(spawn_temp_worker),
        "socket_path": socket_path,
        "request_count": len(trace_rows),
        "session_total_wall_s": session_total_wall_s,
        "per_request_median_wall_s": _median([float(row["request_wall_s"]) for row in trace_rows]),
        "warm_only_median_wall_s": _median([float(value) for value in warm_rows]),
        "worker_startup_s": float((startup_status or {}).get("worker_startup_s") or 0.0),
        "selected_plan_id_stable": all(len(plan_ids) <= 1 for plan_ids in plan_ids_by_workload.values()),
        "correctness_stable": bool(correctness_flags) and all(correctness_flags),
        "fallback_count": int(fallback_count),
        "worker_health_start_path": _normalized_path(outdir / "worker_health_start.json"),
        "worker_health_end_path": _normalized_path(outdir / "worker_health_end.json"),
        "request_trace_path": _normalized_path(outdir / "request_trace.jsonl"),
        "worker_health_path": _normalized_path(outdir / "worker_health.jsonl"),
        "trace_rows": trace_rows,
        "health_rows": health_rows,
    }
    if startup_status is not None:
        dump_json(startup_status, outdir / "worker_health_start.json")
    if final_status is not None:
        dump_json(final_status, outdir / "worker_health_end.json")
    _dump_jsonl(outdir / "request_trace.jsonl", trace_rows)
    _dump_jsonl(outdir / "worker_health.jsonl", health_rows)
    dump_json({k: v for k, v in summary.items() if k not in {"trace_rows", "health_rows"}}, outdir / "summary.json")
    (outdir / "summary.md").write_text(_render_session_summary_markdown(summary), encoding="utf-8")
    return summary


def run_session_manifest(
    session_manifest_path: str | Path,
    *,
    socket_path: str | Path,
    outdir: str | Path,
    spawn_temp_worker: bool = False,
    replace_live_worker: bool = False,
    allow_one_shot_fallback: bool = False,
) -> dict[str, Any]:
    session_manifest = _load_session_manifest(session_manifest_path)
    return run_session(
        session_manifest=session_manifest,
        session_manifest_path=session_manifest_path,
        socket_path=socket_path,
        outdir=outdir,
        spawn_temp_worker=spawn_temp_worker,
        replace_live_worker=replace_live_worker,
        allow_one_shot_fallback=allow_one_shot_fallback,
    )


__all__ = [
    "PersistentWorkerProcess",
    "SESSION_API_VERSION",
    "SessionRunnerError",
    "run_session",
    "run_session_manifest",
]
