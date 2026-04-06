from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .doctor import collect_system_profile
from .execution import (
    ExecutionConfig,
    _assess_plan_bundle_compatibility,
    _build_execution_payload,
    _build_persistent_worker_request,
    _build_plan_bundle_scope,
    _load_plan_bundle,
    execute_selected_plan,
)
from .manifest import load_yaml
from .persistent_client import PersistentExecutorClient, _normalized_path
from .planner import load_system_manifest
from .repo_metadata import capture_repo_metadata
from .session_runner import PersistentWorkerProcess, _correctness_ok, _health_row, _median


class EmbeddedSessionError(RuntimeError):
    pass


class PersistentSession:
    def __init__(
        self,
        *,
        socket_path: str,
        spawn_temp_worker: bool = False,
        allow_one_shot_fallback: bool = False,
        replace_live_worker: bool = False,
        max_requests: int | None = None,
        max_session_seconds: float | None = None,
        timeout_s: float = 60.0,
    ):
        self.socket_path = _normalized_path(socket_path)
        self.spawn_temp_worker = bool(spawn_temp_worker)
        self.allow_one_shot_fallback = bool(allow_one_shot_fallback)
        self.replace_live_worker = bool(replace_live_worker)
        self.max_requests = max_requests
        self.max_session_seconds = max_session_seconds
        self.timeout_s = float(timeout_s)

        self._worker: PersistentWorkerProcess | None = None
        self._client: PersistentExecutorClient | None = None
        self._startup_status: dict[str, Any] | None = None
        self._final_status: dict[str, Any] | None = None
        self._closed = False
        self._session_started = time.perf_counter()
        self._system_profile: dict[str, Any] | None = None
        self._repo_metadata: dict[str, Any] | None = None
        self._system_manifest_cache: dict[str, dict[str, Any]] = {}
        self._trace_rows: list[dict[str, Any]] = []
        self._health_rows: list[dict[str, Any]] = []
        self._fallback_count = 0

    @property
    def trace_rows(self) -> list[dict[str, Any]]:
        return list(self._trace_rows)

    @property
    def health_rows(self) -> list[dict[str, Any]]:
        return list(self._health_rows)

    @property
    def startup_status(self) -> dict[str, Any] | None:
        return dict(self._startup_status) if self._startup_status is not None else None

    @property
    def final_status(self) -> dict[str, Any] | None:
        return dict(self._final_status) if self._final_status is not None else None

    def __enter__(self) -> PersistentSession:
        self._ensure_ready()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _ensure_context(self) -> tuple[dict[str, Any], dict[str, Any]]:
        if self._system_profile is None:
            self._system_profile = collect_system_profile()
        if self._repo_metadata is None:
            self._repo_metadata = capture_repo_metadata()
        return self._system_profile, self._repo_metadata

    def _ensure_ready(self) -> PersistentExecutorClient:
        if self._closed:
            raise EmbeddedSessionError("persistent session is already closed")
        if self._client is not None:
            return self._client

        self._ensure_context()
        if self.spawn_temp_worker:
            self._worker = PersistentWorkerProcess(
                self.socket_path,
                replace_live_worker=self.replace_live_worker,
                max_requests=self.max_requests,
                max_session_seconds=self.max_session_seconds,
            )
            self._startup_status = self._worker.start()
        else:
            self._startup_status = PersistentExecutorClient(self.socket_path, timeout_s=self.timeout_s).status()
        self._client = PersistentExecutorClient(self.socket_path, timeout_s=self.timeout_s)
        return self._client

    def _record_health(
        self,
        *,
        label: str,
        status: dict[str, Any] | None,
        request_id: str | None = None,
        workload_manifest: str | None = None,
        runner_mode: str,
    ) -> None:
        self._health_rows.append(
            _health_row(
                label=label,
                status=status,
                request_id=request_id,
                workload_manifest=workload_manifest,
                runner_mode=runner_mode,
            )
        )

    def _runner_mode(self) -> str:
        return "embedded_session_autospawn_temp_worker" if self.spawn_temp_worker else "embedded_session_existing_worker"

    def _system_manifest(self, system_manifest_path: str | Path) -> dict[str, Any]:
        normalized = _normalized_path(system_manifest_path)
        cached = self._system_manifest_cache.get(normalized)
        if cached is None:
            cached = load_system_manifest(normalized)
            self._system_manifest_cache[normalized] = cached
        return cached

    def status(self) -> dict[str, Any]:
        return self._ensure_ready().status()

    def _session_fallback_payload(
        self,
        *,
        workload_manifest_path: str,
        system_manifest_path: str,
        objective: str,
        probe_strategy: str,
        planner_budget: str,
        allow_distributed: bool,
        measurement_repeats: int,
        execution_intent: str,
        graph_mode: str,
        plan_bundle_path: str,
        fallback_reason: str,
        compatibility_reject_reason: str | None = None,
    ) -> dict[str, Any]:
        payload = execute_selected_plan(
            workload_manifest_path,
            system_manifest_path,
            objective=objective,
            probe_strategy=probe_strategy,
            planner_budget=planner_budget,
            allow_distributed=allow_distributed,
            measurement_repeats=measurement_repeats,
            execution_intent=execution_intent,
            plan_bundle_path=plan_bundle_path,
            graph_mode=graph_mode,
        )
        provenance = {
            **dict(payload.get("persistent_executor_provenance") or {}),
            "requested": True,
            "socket_path": self.socket_path,
            "execution_mode": "direct_executor",
            "persistent_used": False,
            "bundle_hit": bool(payload.get("selection_source") == "plan_bundle_reuse"),
            "fallback_used": True,
            "fallback_reason": fallback_reason,
        }
        if compatibility_reject_reason:
            provenance["compatibility_reject_reason"] = compatibility_reject_reason
        payload["persistent_executor_provenance"] = provenance
        return payload

    def execute_bundle(
        self,
        *,
        workload_manifest: str,
        plan_bundle: str,
        system_manifest: str,
        execution_intent: str = "require_real",
        objective: str = "ttfr",
        probe_strategy: str = "real_if_available",
        planner_budget: str = "balanced",
        measurement_repeats: int = 3,
        graph_mode: str = "off",
        allow_distributed: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        client = self._ensure_ready()
        runner_mode = self._runner_mode()
        system_profile, repo_metadata = self._ensure_context()
        request_id = str(request_id or f"request_{len(self._trace_rows) + 1:02d}")
        workload_manifest_path = _normalized_path(workload_manifest)
        system_manifest_path = _normalized_path(system_manifest)
        plan_bundle_path = _normalized_path(plan_bundle)

        if not any(row.get("label") == "before_first_request" for row in self._health_rows):
            self._record_health(
                label="before_first_request",
                status=self._startup_status or client.status(),
                runner_mode=runner_mode,
            )

        manifest_payload = load_yaml(workload_manifest_path)
        system_manifest_payload = self._system_manifest(system_manifest_path)
        bundle_payload = _load_plan_bundle(plan_bundle_path)
        bundle_scope = _build_plan_bundle_scope(
            workload_manifest_path,
            system_manifest_path,
            manifest_payload,
            system_manifest_payload,
            system_profile,
            repo_metadata,
            objective=objective,
            probe_strategy=probe_strategy,
            planner_budget=planner_budget,
            allow_distributed=allow_distributed,
            max_candidates=None,
        )
        compatibility = _assess_plan_bundle_compatibility(bundle_payload, bundle_scope)
        selected_plan = dict(bundle_payload["selected_plan"])
        request_started = time.perf_counter()

        if not compatibility["compatible"]:
            reject_reason = compatibility["reason"]
            if not self.allow_one_shot_fallback:
                raise EmbeddedSessionError(f"bundle was incompatible for {request_id}: {reject_reason}")
            execution_payload = self._session_fallback_payload(
                workload_manifest_path=workload_manifest_path,
                system_manifest_path=system_manifest_path,
                objective=objective,
                probe_strategy=probe_strategy,
                planner_budget=planner_budget,
                allow_distributed=allow_distributed,
                measurement_repeats=measurement_repeats,
                execution_intent=execution_intent,
                graph_mode=graph_mode,
                plan_bundle_path=plan_bundle_path,
                fallback_reason=reject_reason,
                compatibility_reject_reason=reject_reason,
            )
            request_wall_s = round(max(time.perf_counter() - request_started, 0.0), 9)
            fallback_used = True
            fallback_reason = reject_reason
        else:
            request_payload = _build_persistent_worker_request(
                command="execute_bundle",
                bundle_scope=bundle_scope,
                workload_manifest=manifest_payload,
                system_manifest=system_manifest_payload,
                selected_plan=selected_plan,
                config=ExecutionConfig(
                    objective=objective,
                    precision=str(selected_plan.get("precision") or "complex128"),
                    probe_strategy=probe_strategy,
                    measurement_repeats=int(measurement_repeats),
                    execution_intent=execution_intent,
                    graph_mode=graph_mode,
                ),
                selection_source="plan_bundle_reuse",
                allow_distributed=allow_distributed,
            )
            try:
                worker_response = client.execute_bundle(request_payload)
            except Exception as exc:
                reason = f"persistent worker request failed: {exc}"
                if not self.allow_one_shot_fallback:
                    raise EmbeddedSessionError(reason) from exc
                execution_payload = self._session_fallback_payload(
                    workload_manifest_path=workload_manifest_path,
                    system_manifest_path=system_manifest_path,
                    objective=objective,
                    probe_strategy=probe_strategy,
                    planner_budget=planner_budget,
                    allow_distributed=allow_distributed,
                    measurement_repeats=measurement_repeats,
                    execution_intent=execution_intent,
                    graph_mode=graph_mode,
                    plan_bundle_path=plan_bundle_path,
                    fallback_reason=reason,
                )
                request_wall_s = round(max(time.perf_counter() - request_started, 0.0), 9)
                fallback_used = True
                fallback_reason = reason
            else:
                request_wall_s = round(max(time.perf_counter() - request_started, 0.0), 9)
                if not worker_response.get("ok"):
                    reject_reason = (
                        str(((worker_response.get("persistent_executor_provenance") or {}).get("compatibility_reject_reason")) or "")
                        or str(((worker_response.get("error") or {}).get("message")) or "")
                        or "persistent worker rejected the request"
                    )
                    if not self.allow_one_shot_fallback:
                        raise EmbeddedSessionError(f"persistent worker rejected {request_id}: {reject_reason}")
                    execution_payload = self._session_fallback_payload(
                        workload_manifest_path=workload_manifest_path,
                        system_manifest_path=system_manifest_path,
                        objective=objective,
                        probe_strategy=probe_strategy,
                        planner_budget=planner_budget,
                        allow_distributed=allow_distributed,
                        measurement_repeats=measurement_repeats,
                        execution_intent=execution_intent,
                        graph_mode=graph_mode,
                        plan_bundle_path=plan_bundle_path,
                        fallback_reason=reject_reason,
                        compatibility_reject_reason=reject_reason,
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
                        "socket_path": self.socket_path,
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
                        "bundle_lookup_s": 0.0,
                        "bundle_compatibility_check_s": 0.0,
                        "plan_bundle_lookup_s": 0.0,
                        "execute_plan_bundle_s": float(request_wall_s),
                        "plan_bundle_write_s": 0.0,
                        **dict(bundle.get("driver_timing_json") or {}),
                    }
                    execution_payload = _build_execution_payload(
                        manifest=manifest_payload,
                        system_manifest=system_manifest_payload,
                        repo_metadata=repo_metadata,
                        probe=None,
                        selected_plan=selected_plan,
                        selection_source="plan_bundle_reuse",
                        execution_mode="persistent_executor",
                        plan_json_path=None,
                        plan_bundle_path=plan_bundle_path,
                        plan_bundle_provenance={
                            "requested": True,
                            "bundle_path": plan_bundle_path,
                            "cache_status": "hit",
                            "cache_reason": compatibility["reason"],
                            "write_status": "skipped_hit",
                            "write_reason": "existing compatible bundle was reused without rewriting",
                            "bundle_id": compatibility.get("bundle_id"),
                            "compatibility": compatibility,
                        },
                        persistent_executor_provenance=persistent_executor_provenance,
                        driver_timing=driver_timing,
                        bundle=bundle,
                        candidate_count=int((bundle_payload.get("selection_context") or {}).get("candidate_count") or 0),
                        total_s=request_wall_s,
                    )
                    fallback_used = False
                    fallback_reason = None

        if fallback_used:
            self._fallback_count += 1

        trace_row = {
            "request_id": request_id,
            "workload_manifest": workload_manifest_path,
            "runner_mode": runner_mode,
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
        }
        self._trace_rows.append(trace_row)
        try:
            request_status = client.status()
        except Exception:
            request_status = None
        self._record_health(
            label="after_request",
            status=request_status,
            request_id=request_id,
            workload_manifest=workload_manifest_path,
            runner_mode=runner_mode,
        )
        return execution_payload

    def summary(self) -> dict[str, Any]:
        warm_rows = [row["request_wall_s"] for row in self._trace_rows if int(row.get("session_request_index") or 0) > 1]
        plan_ids_by_workload: dict[str, set[str]] = {}
        for row in self._trace_rows:
            plan_ids_by_workload.setdefault(str(row["workload_manifest"]), set()).add(str(row["selected_plan_id"] or ""))
        return {
            "socket_path": self.socket_path,
            "runner_mode": self._runner_mode(),
            "spawn_temp_worker": self.spawn_temp_worker,
            "request_count": len(self._trace_rows),
            "session_total_wall_s": round(max(time.perf_counter() - self._session_started, 0.0), 9),
            "per_request_median_wall_s": _median([float(row["request_wall_s"]) for row in self._trace_rows]),
            "warm_only_median_wall_s": _median([float(value) for value in warm_rows]),
            "worker_startup_s": float((self._startup_status or {}).get("worker_startup_s") or 0.0),
            "selected_plan_id_stable": all(len(plan_ids) <= 1 for plan_ids in plan_ids_by_workload.values()),
            "correctness_stable": bool(self._trace_rows) and all(bool(row["correctness_ok"]) for row in self._trace_rows),
            "fallback_count": int(self._fallback_count),
            "trace_rows": self.trace_rows,
            "health_rows": self.health_rows,
        }

    def shutdown(self) -> dict[str, Any]:
        if not self.spawn_temp_worker:
            raise EmbeddedSessionError("shutdown is only available for sessions that own a temporary worker")
        self._ensure_ready()
        if self._final_status is None:
            try:
                self._final_status = self._client.status() if self._client is not None else None
            except Exception:
                self._final_status = None
            if self._final_status is not None:
                self._record_health(label="after_session", status=self._final_status, runner_mode=self._runner_mode())
        payload = self._worker.shutdown() if self._worker is not None else {"ok": False}
        self._closed = True
        self._client = None
        self._worker = None
        return payload

    def close(self) -> None:
        if self._closed:
            return
        try:
            if self._client is not None and self._final_status is None:
                try:
                    self._final_status = self._client.status()
                except Exception:
                    self._final_status = None
                if self._final_status is not None:
                    self._record_health(label="after_session", status=self._final_status, runner_mode=self._runner_mode())
            if self.spawn_temp_worker and self._worker is not None:
                try:
                    self._worker.shutdown()
                except Exception:
                    pass
        finally:
            self._client = None
            self._worker = None
            self._closed = True


__all__ = ["EmbeddedSessionError", "PersistentSession"]
