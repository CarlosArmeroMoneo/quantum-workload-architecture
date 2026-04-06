from __future__ import annotations

import json
from pathlib import Path

import pytest

from aqs.execution import _build_plan_bundle_scope
from aqs.manifest import load_yaml
from aqs.embedded_session_client import EmbeddedSessionError, PersistentSession


SYSTEM_MANIFEST_PATH = "configs/systems/ovh_gra9_rtx5000_28.yml"
WORKLOAD_MANIFEST_PATH = "workloads/manifests/imported/ovh_v2/01_real_dense_ring6_amplitude.yaml"


def _write_bundle(path: Path, *, system_profile: dict, repo_metadata: dict, selected_plan: dict) -> None:
    workload_manifest = load_yaml(WORKLOAD_MANIFEST_PATH)
    system_manifest = load_yaml(SYSTEM_MANIFEST_PATH)
    scope = _build_plan_bundle_scope(
        WORKLOAD_MANIFEST_PATH,
        SYSTEM_MANIFEST_PATH,
        workload_manifest,
        system_manifest,
        system_profile,
        repo_metadata,
        objective="ttfr",
        probe_strategy="real_if_available",
        planner_budget="balanced",
        allow_distributed=False,
        max_candidates=None,
    )
    payload = {
        "api_version": "aqs.plan_bundle.v1",
        "bundle_id": "bundle_test",
        "bundle_schema_version": "aqs.plan_bundle.v1",
        "bundle_scope": scope,
        "compatibility_fingerprint": scope["compatibility_fingerprint"],
        "execution_stack_version": scope["execution_stack_version"],
        "real_execution_stack_version": scope["real_execution_stack_version"],
        "repo_metadata": repo_metadata,
        "selected_plan": selected_plan,
        "selection_context": {
            "selection_source": "plan_rank",
            "plan_rank": 1,
            "candidate_count": 3,
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_persistent_session_existing_worker_round_trip(tmp_path, monkeypatch):
    repo_metadata = {"git_commit": "commit_test", "package_version": "0.5.0"}
    system_profile = {"system_id": "sys_test"}
    selected_plan = {"plan_id": "plan_test", "precision": "complex128", "workspace_gb": 2.7}
    bundle_path = tmp_path / "seed.bundle.json"
    _write_bundle(bundle_path, system_profile=system_profile, repo_metadata=repo_metadata, selected_plan=selected_plan)

    class FakeClient:
        def __init__(self, socket_path, *, timeout_s=60.0):
            self.socket_path = socket_path
            self.timeout_s = timeout_s

        def status(self):
            return {
                "ok": True,
                "worker_session_id": "wrk_test",
                "worker_start_time": "2026-04-06T00:00:00+00:00",
                "worker_startup_s": 0.25,
                "session_uptime_s": 1.5,
                "request_count": 1,
                "health": {
                    "worker_pid": 1234,
                    "rss_bytes": 1_000_000,
                    "request_count": 1,
                    "session_uptime_s": 1.5,
                    "device_id": 0,
                    "gpu_mem_free_bytes": 100,
                    "gpu_mem_total_bytes": 200,
                },
            }

        def execute_bundle(self, request):
            return {
                "protocol_version": "aqs.persistent_executor.v1",
                "ok": True,
                "command": "execute_bundle",
                "persistent_executor_provenance": {
                    "execution_mode": "persistent_executor",
                    "bundle_hit": True,
                    "worker_session_id": "wrk_test",
                    "worker_warm": False,
                    "worker_start_time": "2026-04-06T00:00:00+00:00",
                    "worker_request_index": 1,
                    "compatibility_match_reason": "matched",
                    "compatibility_reject_reason": None,
                },
                "driver_timing_json": {
                    "worker_startup_s": 0.25,
                    "worker_request_dispatch_s": 0.001,
                    "worker_execute_s": 0.08,
                    "worker_reply_s": 0.001,
                    "session_request_index": 1,
                    "session_uptime_s": 1.5,
                },
                "bundle": {
                    "execution_run": {
                        "plan_id": request["selected_plan"]["plan_id"],
                        "workload_id": request["workload_manifest"]["ids"]["workload_id"],
                        "system_id": "sys_test",
                        "replicate_idx": 0,
                        "graph_mode": "off",
                        "status": "success",
                        "started_at": "2026-04-06T00:00:00+00:00",
                        "finished_at": "2026-04-06T00:00:01+00:00",
                        "wall_s": 0.08,
                        "ttfr_s": 0.07,
                        "steady_iter_ms": 5.0,
                        "gpu_seconds": 0.08,
                        "peak_mem_gb": 0.25,
                        "peak_workspace_gb": 2.7,
                        "output_digest": "out_test",
                        "execution_source": "cuquantum_tensornet_gpu",
                        "failure_detail_json": {},
                        "run_id": "run_test",
                    },
                    "accuracy_eval": {"status": "pass", "rows": []},
                    "profile_summary": None,
                    "linked_assets": [],
                    "driver_timing_json": {
                        "dispatch_real_executor_s": 0.0,
                        "real_execute_s": 0.08,
                        "post_execution_s": 0.003,
                        "import_real_stack_s": 0.0,
                        "network_build_s": 0.01,
                        "pre_t_start_overhead_s": 0.001,
                    },
                },
            }

    monkeypatch.setattr("aqs.embedded_session_client.collect_system_profile", lambda: system_profile)
    monkeypatch.setattr("aqs.embedded_session_client.capture_repo_metadata", lambda: repo_metadata)
    monkeypatch.setattr("aqs.embedded_session_client.PersistentExecutorClient", FakeClient)

    session = PersistentSession(socket_path=str(tmp_path / "worker.sock"))
    with session:
        payload = session.execute_bundle(
            workload_manifest=WORKLOAD_MANIFEST_PATH,
            plan_bundle=str(bundle_path),
            system_manifest=SYSTEM_MANIFEST_PATH,
            request_id="run01",
        )

    summary = session.summary()
    assert payload["selected_plan"]["plan_id"] == "plan_test"
    assert payload["execution_mode"] == "persistent_executor"
    assert payload["persistent_executor_provenance"]["worker_session_id"] == "wrk_test"
    assert summary["request_count"] == 1
    assert summary["fallback_count"] == 0
    assert summary["selected_plan_id_stable"] is True
    assert summary["correctness_stable"] is True
    assert summary["trace_rows"][0]["selected_plan_id"] == "plan_test"
    assert any(row["label"] == "before_first_request" for row in summary["health_rows"])
    assert any(row["label"] == "after_session" for row in summary["health_rows"])


def test_persistent_session_autospawn_shutdown_only_for_owned_worker(tmp_path, monkeypatch):
    repo_metadata = {"git_commit": "commit_test", "package_version": "0.5.0"}
    system_profile = {"system_id": "sys_test"}
    selected_plan = {"plan_id": "plan_test", "precision": "complex128", "workspace_gb": 2.7}
    bundle_path = tmp_path / "seed.bundle.json"
    _write_bundle(bundle_path, system_profile=system_profile, repo_metadata=repo_metadata, selected_plan=selected_plan)
    lifecycle: dict[str, int] = {"start": 0, "shutdown": 0}

    class FakeClient:
        def __init__(self, socket_path, *, timeout_s=60.0):
            self.socket_path = socket_path
            self.timeout_s = timeout_s

        def status(self):
            return {"ok": True, "worker_session_id": "wrk_test", "worker_startup_s": 0.2, "health": {}}

        def execute_bundle(self, request):
            return {
                "protocol_version": "aqs.persistent_executor.v1",
                "ok": True,
                "command": "execute_bundle",
                "persistent_executor_provenance": {
                    "execution_mode": "persistent_executor",
                    "bundle_hit": True,
                    "worker_session_id": "wrk_test",
                    "worker_warm": False,
                    "worker_start_time": "2026-04-06T00:00:00+00:00",
                    "worker_request_index": 1,
                    "compatibility_match_reason": "matched",
                    "compatibility_reject_reason": None,
                },
                "driver_timing_json": {
                    "worker_startup_s": 0.2,
                    "worker_request_dispatch_s": 0.001,
                    "worker_execute_s": 0.08,
                    "worker_reply_s": 0.001,
                    "session_request_index": 1,
                    "session_uptime_s": 1.0,
                },
                "bundle": {
                    "execution_run": {
                        "plan_id": request["selected_plan"]["plan_id"],
                        "workload_id": request["workload_manifest"]["ids"]["workload_id"],
                        "system_id": "sys_test",
                        "replicate_idx": 0,
                        "graph_mode": "off",
                        "status": "success",
                        "started_at": "2026-04-06T00:00:00+00:00",
                        "finished_at": "2026-04-06T00:00:01+00:00",
                        "wall_s": 0.08,
                        "ttfr_s": 0.07,
                        "steady_iter_ms": 5.0,
                        "gpu_seconds": 0.08,
                        "peak_mem_gb": 0.25,
                        "peak_workspace_gb": 2.7,
                        "output_digest": "out_test",
                        "execution_source": "cuquantum_tensornet_gpu",
                        "failure_detail_json": {},
                        "run_id": "run_test",
                    },
                    "accuracy_eval": {"status": "pass", "rows": []},
                    "profile_summary": None,
                    "linked_assets": [],
                    "driver_timing_json": {
                        "real_execute_s": 0.08,
                        "post_execution_s": 0.003,
                        "import_real_stack_s": 0.0,
                        "network_build_s": 0.01,
                        "pre_t_start_overhead_s": 0.001,
                    },
                },
            }

    class FakeWorkerProcess:
        def __init__(self, socket_path, *, replace_live_worker=False, max_requests=None, max_session_seconds=None):
            self.socket_path = socket_path

        def start(self):
            lifecycle["start"] += 1
            return {"ok": True, "worker_session_id": "wrk_test", "worker_startup_s": 0.2, "health": {}}

        def shutdown(self):
            lifecycle["shutdown"] += 1
            return {"ok": True, "command": "shutdown"}

    monkeypatch.setattr("aqs.embedded_session_client.collect_system_profile", lambda: system_profile)
    monkeypatch.setattr("aqs.embedded_session_client.capture_repo_metadata", lambda: repo_metadata)
    monkeypatch.setattr("aqs.embedded_session_client.PersistentExecutorClient", FakeClient)
    monkeypatch.setattr("aqs.embedded_session_client.PersistentWorkerProcess", FakeWorkerProcess)

    with PersistentSession(socket_path=str(tmp_path / "worker.sock"), spawn_temp_worker=True) as session:
        payload = session.execute_bundle(
            workload_manifest=WORKLOAD_MANIFEST_PATH,
            plan_bundle=str(bundle_path),
            system_manifest=SYSTEM_MANIFEST_PATH,
        )
        assert payload["selected_plan"]["plan_id"] == "plan_test"

    assert lifecycle == {"start": 1, "shutdown": 1}

    session = PersistentSession(socket_path=str(tmp_path / "worker.sock"), spawn_temp_worker=False)
    with pytest.raises(EmbeddedSessionError, match="shutdown is only available"):
        session.shutdown()


def test_persistent_session_requires_explicit_fallback(tmp_path, monkeypatch):
    repo_metadata = {"git_commit": "commit_test", "package_version": "0.5.0"}
    system_profile = {"system_id": "sys_test"}
    selected_plan = {"plan_id": "plan_test", "precision": "complex128", "workspace_gb": 2.7}
    bundle_path = tmp_path / "seed.bundle.json"
    _write_bundle(bundle_path, system_profile=system_profile, repo_metadata=repo_metadata, selected_plan=selected_plan)

    class RejectingClient:
        def __init__(self, socket_path, *, timeout_s=60.0):
            self.socket_path = socket_path

        def status(self):
            return {"ok": True, "worker_session_id": "wrk_test", "health": {}}

        def execute_bundle(self, request):
            return {
                "protocol_version": "aqs.persistent_executor.v1",
                "ok": False,
                "command": "execute_bundle",
                "persistent_executor_provenance": {
                    "execution_mode": "persistent_executor",
                    "bundle_hit": True,
                    "compatibility_reject_reason": "precision mismatch",
                },
                "driver_timing_json": {},
                "error": {
                    "reason_code": "persistent_executor_rejected",
                    "message": "precision mismatch",
                },
            }

    monkeypatch.setattr("aqs.embedded_session_client.collect_system_profile", lambda: system_profile)
    monkeypatch.setattr("aqs.embedded_session_client.capture_repo_metadata", lambda: repo_metadata)
    monkeypatch.setattr("aqs.embedded_session_client.PersistentExecutorClient", RejectingClient)

    with PersistentSession(socket_path=str(tmp_path / "worker.sock")) as session:
        with pytest.raises(EmbeddedSessionError, match="precision mismatch"):
            session.execute_bundle(
                workload_manifest=WORKLOAD_MANIFEST_PATH,
                plan_bundle=str(bundle_path),
                system_manifest=SYSTEM_MANIFEST_PATH,
            )


def test_persistent_session_allows_explicit_fallback(tmp_path, monkeypatch):
    repo_metadata = {"git_commit": "commit_test", "package_version": "0.5.0"}
    system_profile = {"system_id": "sys_test"}
    selected_plan = {"plan_id": "plan_test", "precision": "complex128", "workspace_gb": 2.7}
    bundle_path = tmp_path / "seed.bundle.json"
    _write_bundle(bundle_path, system_profile=system_profile, repo_metadata=repo_metadata, selected_plan=selected_plan)

    class RejectingClient:
        def __init__(self, socket_path, *, timeout_s=60.0):
            self.socket_path = socket_path

        def status(self):
            return {"ok": True, "worker_session_id": "wrk_test", "health": {}}

        def execute_bundle(self, request):
            raise RuntimeError("worker unavailable")

    def fake_execute_selected_plan(*args, **kwargs):
        return {
            "selected_plan": {"plan_id": "plan_test"},
            "selection_source": "plan_bundle_reuse",
            "execution_mode": "direct_executor",
            "persistent_executor_provenance": {},
            "execution_run": {"status": "success"},
            "accuracy_eval": {"status": "pass"},
            "driver_total_s": 0.12,
            "outer_driver_overhead_s": 0.01,
            "driver_timing_json": {
                "worker_execute_s": 0.0,
                "worker_request_dispatch_s": 0.0,
                "worker_reply_s": 0.0,
                "session_request_index": 0,
            },
        }

    monkeypatch.setattr("aqs.embedded_session_client.collect_system_profile", lambda: system_profile)
    monkeypatch.setattr("aqs.embedded_session_client.capture_repo_metadata", lambda: repo_metadata)
    monkeypatch.setattr("aqs.embedded_session_client.PersistentExecutorClient", RejectingClient)
    monkeypatch.setattr("aqs.embedded_session_client.execute_selected_plan", fake_execute_selected_plan)

    with PersistentSession(
        socket_path=str(tmp_path / "worker.sock"),
        allow_one_shot_fallback=True,
    ) as session:
        payload = session.execute_bundle(
            workload_manifest=WORKLOAD_MANIFEST_PATH,
            plan_bundle=str(bundle_path),
            system_manifest=SYSTEM_MANIFEST_PATH,
        )

    assert payload["selected_plan"]["plan_id"] == "plan_test"
    assert payload["persistent_executor_provenance"]["requested"] is True
    assert payload["persistent_executor_provenance"]["persistent_used"] is False
    assert payload["persistent_executor_provenance"]["fallback_used"] is True
    assert "worker unavailable" in payload["persistent_executor_provenance"]["fallback_reason"]
    assert session.summary()["fallback_count"] == 1
