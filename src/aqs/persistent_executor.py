from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import socket
import time
from typing import Any

from .execution import EXECUTION_VERSION, PLAN_BUNDLE_VERSION
from .execution_real import (
    REAL_EXECUTION_STACK_VERSION,
    execute_real_plan_candidate_with_runtime,
    initialize_real_execution_runtime,
)
from .graph_modes import normalize_graph_mode
from .persistent_client import (
    PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
    PersistentClientError,
    PersistentExecutorClient,
    _normalized_path,
    _recv_json_line,
    _send_json_line,
    _unix_socket_family,
)
from .repo_metadata import capture_repo_metadata
from .utils import canonical_json, sha256_text

PERSISTENT_EXECUTION_MODE = "persistent_executor"
PERSISTENT_EXECUTOR_COMMANDS = ("ping", "status", "execute_bundle", "execute_plan_json", "shutdown")


class PersistentExecutorError(RuntimeError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _manifest_digest(payload: dict[str, Any]) -> str:
    return sha256_text(canonical_json(payload))


def _rss_bytes() -> int | None:
    status_path = Path("/proc/self/status")
    if status_path.exists():
        try:
            for line in status_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return int(parts[1]) * 1024
        except Exception:
            return None
    return None


def _gpu_health_snapshot(runtime: dict[str, Any] | None) -> dict[str, Any]:
    snapshot: dict[str, int | None] = {
        "device_id": None,
        "gpu_mem_free_bytes": None,
        "gpu_mem_total_bytes": None,
    }
    cupy = (runtime or {}).get("cupy")
    if cupy is None:
        return snapshot
    try:
        device = cupy.cuda.Device()
        device_id = getattr(device, "id", None)
        snapshot["device_id"] = int(device_id) if device_id is not None else None
    except Exception:
        snapshot["device_id"] = None
    try:
        free_bytes, total_bytes = cupy.cuda.runtime.memGetInfo()
        snapshot["gpu_mem_free_bytes"] = int(free_bytes)
        snapshot["gpu_mem_total_bytes"] = int(total_bytes)
    except Exception:
        snapshot["gpu_mem_free_bytes"] = None
        snapshot["gpu_mem_total_bytes"] = None
    return snapshot


def _sleep_briefly(seconds: float) -> None:
    time.sleep(max(seconds, 0.0))


def _build_worker_provenance(
    *,
    session_id: str,
    started_at: str,
    request_index: int,
    session_uptime_s: float,
    worker_startup_s: float,
    bundle_hit: bool,
    compatibility_match_reason: str | None,
    compatibility_reject_reason: str | None,
) -> dict[str, Any]:
    return {
        "execution_mode": PERSISTENT_EXECUTION_MODE,
        "bundle_hit": bool(bundle_hit),
        "worker_session_id": session_id,
        "worker_warm": bool(request_index > 1),
        "worker_start_time": started_at,
        "worker_request_index": int(request_index),
        "compatibility_match_reason": compatibility_match_reason,
        "compatibility_reject_reason": compatibility_reject_reason,
        "session_uptime_s": round(max(session_uptime_s, 0.0), 9),
        "worker_startup_s": round(max(worker_startup_s, 0.0), 9),
    }


def _build_reject_response(
    *,
    request: dict[str, Any],
    session_id: str,
    started_at: str,
    request_index: int,
    session_uptime_s: float,
    worker_startup_s: float,
    worker_request_dispatch_s: float,
    reason: str,
) -> dict[str, Any]:
    provenance = _build_worker_provenance(
        session_id=session_id,
        started_at=started_at,
        request_index=request_index,
        session_uptime_s=session_uptime_s,
        worker_startup_s=worker_startup_s,
        bundle_hit=bool((request.get("request_context") or {}).get("bundle_hit")),
        compatibility_match_reason=None,
        compatibility_reject_reason=reason,
    )
    return {
        "protocol_version": PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
        "ok": False,
        "command": request.get("command"),
        "persistent_executor_provenance": provenance,
        "driver_timing_json": {
            "worker_startup_s": round(max(worker_startup_s, 0.0), 9),
            "worker_request_dispatch_s": round(max(worker_request_dispatch_s, 0.0), 9),
            "worker_execute_s": 0.0,
            "worker_reply_s": 0.0,
            "session_request_index": int(request_index),
            "session_uptime_s": round(max(session_uptime_s, 0.0), 9),
        },
        "error": {
            "reason_code": "persistent_executor_rejected",
            "message": reason,
        },
    }


def assess_persistent_request_compatibility(
    request: dict[str, Any],
    *,
    worker_system_profile: dict[str, Any],
    worker_repo_metadata: dict[str, Any],
) -> dict[str, Any]:
    command = str(request.get("command") or "")
    if command not in PERSISTENT_EXECUTOR_COMMANDS:
        return {"compatible": False, "reason": f"unsupported command {command!r}", "mismatched_fields": ["command"]}

    request_context = request.get("request_context") or {}
    workload_manifest = request.get("workload_manifest") or {}
    system_manifest = request.get("system_manifest") or {}
    selected_plan = request.get("selected_plan") or {}
    execution_config = request.get("config") or {}
    allow_distributed = bool(request.get("allow_distributed"))

    required_context = [
        "workload_manifest_digest",
        "workload_id",
        "system_manifest_digest",
        "system_name",
        "system_id",
        "objective",
        "precision",
        "graph_mode",
        "execution_intent",
        "allow_distributed",
        "bundle_schema_version",
        "execution_stack_version",
        "real_execution_stack_version",
        "repo_commit",
        "package_version",
        "selected_plan_id",
        "selection_source",
        "bundle_hit",
    ]
    missing = [field for field in required_context if field not in request_context]
    if missing:
        return {
            "compatible": False,
            "reason": f"request_context is missing required fields: {', '.join(missing)}",
            "mismatched_fields": missing,
        }

    mismatched: list[str] = []
    if request.get("protocol_version") != PERSISTENT_EXECUTOR_PROTOCOL_VERSION:
        mismatched.append("protocol_version")
    if _manifest_digest(workload_manifest) != request_context["workload_manifest_digest"]:
        mismatched.append("workload_manifest_digest")
    if str((workload_manifest.get("ids") or {}).get("workload_id") or "") != str(request_context["workload_id"]):
        mismatched.append("workload_id")
    if _manifest_digest(system_manifest) != request_context["system_manifest_digest"]:
        mismatched.append("system_manifest_digest")
    if str(system_manifest.get("system_name") or "") != str(request_context["system_name"] or ""):
        mismatched.append("system_name")
    if str(worker_system_profile.get("system_id") or "") != str(request_context["system_id"] or ""):
        mismatched.append("system_id")
    if str(request_context["objective"] or "") != str(execution_config.get("objective") or ""):
        mismatched.append("objective")
    if str(request_context["precision"] or "") != str(execution_config.get("precision") or ""):
        mismatched.append("precision")
    if str(request_context["graph_mode"] or "") != str(normalize_graph_mode(execution_config.get("graph_mode"), default="off")):
        mismatched.append("graph_mode")
    if str(request_context["execution_intent"] or "") != str(execution_config.get("execution_intent") or ""):
        mismatched.append("execution_intent")
    if bool(request_context["allow_distributed"]) != allow_distributed:
        mismatched.append("allow_distributed")
    if str(request_context["bundle_schema_version"] or "") != PLAN_BUNDLE_VERSION:
        mismatched.append("bundle_schema_version")
    if str(request_context["execution_stack_version"] or "") != EXECUTION_VERSION:
        mismatched.append("execution_stack_version")
    if str(request_context["real_execution_stack_version"] or "") != REAL_EXECUTION_STACK_VERSION:
        mismatched.append("real_execution_stack_version")
    worker_commit = worker_repo_metadata.get("git_commit")
    if worker_commit and request_context.get("repo_commit") and request_context["repo_commit"] != worker_commit:
        mismatched.append("repo_commit")
    worker_package = worker_repo_metadata.get("package_version")
    if worker_package and request_context.get("package_version") and request_context["package_version"] != worker_package:
        mismatched.append("package_version")
    if str(request_context["selected_plan_id"] or "") != str(selected_plan.get("plan_id") or ""):
        mismatched.append("selected_plan_id")

    if command == "execute_bundle":
        if request_context.get("selection_source") != "plan_bundle_reuse":
            mismatched.append("selection_source")
        if not bool(request_context.get("bundle_hit")):
            mismatched.append("bundle_hit")
    if command == "execute_plan_json":
        if request_context.get("selection_source") != "plan_override":
            mismatched.append("selection_source")
        if bool(request_context.get("bundle_hit")):
            mismatched.append("bundle_hit")

    if mismatched:
        return {
            "compatible": False,
            "reason": (
                "request compatibility fingerprint did not match the worker session or the supplied execution payload: "
                + ", ".join(mismatched)
            ),
            "mismatched_fields": mismatched,
        }

    return {
        "compatible": True,
        "reason": (
            "request fingerprint matched the current worker environment, the execution payload, "
            "and the caller-supplied selection provenance"
        ),
        "mismatched_fields": [],
    }


class PersistentRealExecutorWorker:
    def __init__(
        self,
        socket_path: str | Path,
        *,
        replace_live_worker: bool = False,
        max_requests: int | None = None,
        max_session_seconds: float | None = None,
        startup_wait_seconds: float = 3.0,
    ):
        self.socket_path = _normalized_path(socket_path)
        self.replace_live_worker = bool(replace_live_worker)
        self.max_requests = int(max_requests) if max_requests is not None else None
        self.max_session_seconds = float(max_session_seconds) if max_session_seconds is not None else None
        self.startup_wait_seconds = float(startup_wait_seconds)

        self.session_started_at = _utc_now_iso()
        self.session_started_perf = time.perf_counter()
        self.system_profile: dict[str, Any] | None = None
        self.repo_metadata: dict[str, Any] | None = None
        self.runtime: dict[str, Any] | None = None
        self.worker_startup_s = 0.0
        self.session_id = "wrk_" + sha256_text(f"{self.socket_path}:{self.session_started_at}")[:16]
        self.request_count = 0
        self.startup_socket_action = "fresh_bind"
        self.stop_reason: str | None = None

    def _session_uptime_s(self) -> float:
        return max(time.perf_counter() - self.session_started_perf, 0.0)

    def _startup(self) -> None:
        if self.runtime is not None:
            return
        self.repo_metadata = capture_repo_metadata()
        self.runtime = initialize_real_execution_runtime(touch_context=True)
        self.system_profile = dict(self.runtime["system_profile"])
        self.worker_startup_s = float(self.runtime.get("startup_s") or 0.0)

    def _health_snapshot(self) -> dict[str, Any]:
        return {
            "worker_pid": int(os.getpid()),
            "rss_bytes": _rss_bytes(),
            "request_count": int(self.request_count),
            "session_uptime_s": round(self._session_uptime_s(), 9),
            **_gpu_health_snapshot(self.runtime),
        }

    def _health_payload(self, *, command: str, detailed: bool) -> dict[str, Any]:
        payload = {
            "protocol_version": PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
            "ok": True,
            "command": command,
            "worker_session_id": self.session_id,
            "worker_start_time": self.session_started_at,
            "worker_startup_s": self.worker_startup_s,
            "session_uptime_s": round(self._session_uptime_s(), 9),
            "request_count": int(self.request_count),
            "health": self._health_snapshot(),
        }
        if detailed:
            payload.update(
                {
                    "socket_path": self.socket_path,
                    "runtime_metadata": {
                        "execution_mode": PERSISTENT_EXECUTION_MODE,
                        "execution_stack_version": EXECUTION_VERSION,
                        "real_execution_stack_version": REAL_EXECUTION_STACK_VERSION,
                        "bundle_schema_version": PLAN_BUNDLE_VERSION,
                        "system_id": (self.system_profile or {}).get("system_id"),
                        "repo_commit": (self.repo_metadata or {}).get("git_commit"),
                        "package_version": (self.repo_metadata or {}).get("package_version"),
                    },
                    "session_bounds": {
                        "max_requests": self.max_requests,
                        "max_session_seconds": self.max_session_seconds,
                    },
                    "startup_socket_action": self.startup_socket_action,
                    "stop_reason": self.stop_reason,
                }
            )
        return payload

    def _prepare_socket_path(self) -> None:
        socket_path = Path(self.socket_path)
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        if not socket_path.exists():
            self.startup_socket_action = "fresh_bind"
            return

        client = PersistentExecutorClient(socket_path, timeout_s=1.0)
        try:
            health = client.ping()
        except Exception:
            socket_path.unlink()
            self.startup_socket_action = "stale_socket_removed"
            return

        if not health.get("ok"):
            socket_path.unlink()
            self.startup_socket_action = "stale_socket_removed"
            return

        if not self.replace_live_worker:
            raise PersistentExecutorError(
                f"live persistent executor already listening at {self.socket_path}; pass --replace-live-worker to replace it"
            )

        client.shutdown()
        deadline = time.time() + self.startup_wait_seconds
        while time.time() < deadline:
            if not socket_path.exists():
                self.startup_socket_action = "replaced_live_worker"
                return
            _sleep_briefly(0.05)
        raise PersistentExecutorError(
            f"live persistent executor at {self.socket_path} acknowledged shutdown but did not remove the socket in time"
        )

    def _should_stop_after_request(self) -> bool:
        if self.max_requests is not None and self.request_count >= self.max_requests:
            self.stop_reason = "max_requests_reached"
            return True
        if self.max_session_seconds is not None and self._session_uptime_s() >= self.max_session_seconds:
            self.stop_reason = "max_session_seconds_reached"
            return True
        return False

    def _should_stop_while_idle(self) -> bool:
        if self.max_session_seconds is not None and self._session_uptime_s() >= self.max_session_seconds:
            self.stop_reason = "max_session_seconds_reached"
            return True
        return False

    def _handle_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.runtime is None or self.system_profile is None or self.repo_metadata is None:
            raise PersistentExecutorError("persistent worker was not initialized before handling a request")

        dispatch_started = time.perf_counter()
        self.request_count += 1
        request_index = self.request_count
        session_uptime_s = self._session_uptime_s()
        compatibility = assess_persistent_request_compatibility(
            request,
            worker_system_profile=self.system_profile,
            worker_repo_metadata=self.repo_metadata,
        )
        worker_request_dispatch_s = round(max(time.perf_counter() - dispatch_started, 0.0), 9)
        if not compatibility["compatible"]:
            return _build_reject_response(
                request=request,
                session_id=self.session_id,
                started_at=self.session_started_at,
                request_index=request_index,
                session_uptime_s=session_uptime_s,
                worker_startup_s=self.worker_startup_s,
                worker_request_dispatch_s=worker_request_dispatch_s,
                reason=compatibility["reason"],
            )

        execute_started = time.perf_counter()
        bundle = execute_real_plan_candidate_with_runtime(
            request["workload_manifest"],
            request["selected_plan"],
            runtime={
                **self.runtime,
                "request_import_real_stack_s": 0.0,
            },
            config=type("PersistentCfg", (), request["config"])(),
        )
        worker_execute_s = round(max(time.perf_counter() - execute_started, 0.0), 9)

        driver_timing_json: dict[str, float | int] = {
            "worker_startup_s": round(max(self.worker_startup_s, 0.0), 9),
            "worker_request_dispatch_s": worker_request_dispatch_s,
            "worker_execute_s": worker_execute_s,
            "worker_reply_s": 0.0,
            "session_request_index": int(request_index),
            "session_uptime_s": round(max(session_uptime_s, 0.0), 9),
        }
        provenance = _build_worker_provenance(
            session_id=self.session_id,
            started_at=self.session_started_at,
            request_index=request_index,
            session_uptime_s=session_uptime_s,
            worker_startup_s=self.worker_startup_s,
            bundle_hit=bool((request.get("request_context") or {}).get("bundle_hit")),
            compatibility_match_reason=compatibility["reason"],
            compatibility_reject_reason=None,
        )
        response_started = time.perf_counter()
        response = {
            "protocol_version": PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
            "ok": True,
            "command": request.get("command"),
            "persistent_executor_provenance": provenance,
            "driver_timing_json": driver_timing_json,
            "bundle": {
                "execution_run": bundle["execution_run"],
                "accuracy_eval": bundle.get("accuracy_eval"),
                "profile_summary": bundle.get("profile_summary"),
                "linked_assets": bundle.get("linked_assets", []),
                "driver_timing_json": bundle.get("driver_timing_json") or {},
            },
        }
        driver_timing_json["worker_reply_s"] = round(max(time.perf_counter() - response_started, 0.0), 9)
        return response

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        command = str(request.get("command") or "")
        if command == "ping":
            return self._health_payload(command="ping", detailed=False)
        if command == "status":
            return self._health_payload(command="status", detailed=True)
        if command == "shutdown":
            self.stop_reason = "shutdown_requested"
            return {
                "protocol_version": PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
                "ok": True,
                "command": "shutdown",
                "worker_session_id": self.session_id,
                "session_uptime_s": round(self._session_uptime_s(), 9),
            }
        if command in {"execute_bundle", "execute_plan_json"}:
            return self._handle_execute(request)
        return {
            "protocol_version": PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
            "ok": False,
            "command": command,
            "error": {
                "reason_code": "persistent_executor_unknown_command",
                "message": f"unsupported command {command!r}",
            },
        }

    def serve_forever(self) -> int:
        socket_path = Path(self.socket_path)
        self._prepare_socket_path()
        self._startup()

        server = socket.socket(_unix_socket_family(), socket.SOCK_STREAM)
        server.bind(self.socket_path)
        server.listen(1)
        server.settimeout(0.25)
        try:
            running = True
            while running:
                if self._should_stop_while_idle():
                    break
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                with conn:
                    reader = conn.makefile("r", encoding="utf-8")
                    writer = conn.makefile("w", encoding="utf-8")
                    try:
                        request = _recv_json_line(reader)
                        response = self.handle_request(request)
                        _send_json_line(writer, response)
                        if str(request.get("command") or "") == "shutdown":
                            running = False
                        elif self._should_stop_after_request():
                            running = False
                    finally:
                        reader.close()
                        writer.close()
        finally:
            server.close()
            if socket_path.exists():
                socket_path.unlink()
        return 0


__all__ = [
    "PERSISTENT_EXECUTION_MODE",
    "PERSISTENT_EXECUTOR_COMMANDS",
    "PERSISTENT_EXECUTOR_PROTOCOL_VERSION",
    "PersistentClientError",
    "PersistentExecutorClient",
    "PersistentExecutorError",
    "PersistentRealExecutorWorker",
    "assess_persistent_request_compatibility",
]
