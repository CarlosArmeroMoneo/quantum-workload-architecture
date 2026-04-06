from __future__ import annotations

import json
from pathlib import Path

import pytest

from aqs.execution import _build_plan_bundle_scope
from aqs.manifest import load_yaml
from aqs.session_runner import SessionRunnerError, run_session


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


def _session_manifest(bundle_path: Path) -> dict:
    return {
        "api_version": "aqs.session.v1",
        "project": "tnep",
        "mode": "persistent_execute_sequence",
        "system_manifest": SYSTEM_MANIFEST_PATH,
        "objective": "ttfr",
        "probe_strategy": "real_if_available",
        "planner_budget": "balanced",
        "measurement_repeats": 3,
        "execution_intent": "require_real",
        "graph_mode": "off",
        "allow_distributed": False,
        "requests": [
            {
                "id": "run01",
                "workload_manifest": WORKLOAD_MANIFEST_PATH,
                "plan_bundle": str(bundle_path),
            }
        ],
    }


def test_run_session_existing_worker_round_trip(tmp_path, monkeypatch):
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

    monkeypatch.setattr("aqs.session_runner.collect_system_profile", lambda: system_profile)
    monkeypatch.setattr("aqs.session_runner.capture_repo_metadata", lambda: repo_metadata)
    monkeypatch.setattr("aqs.session_runner.PersistentExecutorClient", FakeClient)

    summary = run_session(
        session_manifest=_session_manifest(bundle_path),
        session_manifest_path=tmp_path / "session.yaml",
        socket_path=tmp_path / "worker.sock",
        outdir=tmp_path / "out",
    )

    assert summary["request_count"] == 1
    assert summary["fallback_count"] == 0
    assert summary["selected_plan_id_stable"] is True
    assert summary["correctness_stable"] is True
    assert summary["trace_rows"][0]["selected_plan_id"] == "plan_test"
    request_payload = json.loads((tmp_path / "out" / "requests" / "run01.execution.json").read_text(encoding="utf-8"))
    assert request_payload["selected_plan"]["plan_id"] == "plan_test"
    assert request_payload["execution_mode"] == "persistent_executor"


def test_run_session_requires_explicit_fallback(tmp_path, monkeypatch):
    repo_metadata = {"git_commit": "commit_test", "package_version": "0.5.0"}
    system_profile = {"system_id": "sys_test"}
    bundle_path = tmp_path / "seed.bundle.json"
    _write_bundle(
        bundle_path,
        system_profile=system_profile,
        repo_metadata=repo_metadata,
        selected_plan={"plan_id": "plan_test", "precision": "complex128", "workspace_gb": 2.7},
    )

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

    monkeypatch.setattr("aqs.session_runner.collect_system_profile", lambda: system_profile)
    monkeypatch.setattr("aqs.session_runner.capture_repo_metadata", lambda: repo_metadata)
    monkeypatch.setattr("aqs.session_runner.PersistentExecutorClient", RejectingClient)

    with pytest.raises(SessionRunnerError, match="precision mismatch"):
        run_session(
            session_manifest=_session_manifest(bundle_path),
            session_manifest_path=tmp_path / "session.yaml",
            socket_path=tmp_path / "worker.sock",
            outdir=tmp_path / "out",
        )


def test_run_session_allows_explicit_fallback_and_spawn_temp_worker(tmp_path, monkeypatch):
    repo_metadata = {"git_commit": "commit_test", "package_version": "0.5.0"}
    system_profile = {"system_id": "sys_test"}
    bundle_path = tmp_path / "seed.bundle.json"
    _write_bundle(
        bundle_path,
        system_profile=system_profile,
        repo_metadata=repo_metadata,
        selected_plan={"plan_id": "plan_test", "precision": "complex128", "workspace_gb": 2.7},
    )

    class RejectingClient:
        def __init__(self, socket_path, *, timeout_s=60.0):
            self.socket_path = socket_path

        def status(self):
            return {"ok": True, "worker_session_id": "wrk_test", "health": {}}

        def execute_bundle(self, request):
            raise RuntimeError("worker unavailable")

    class FakeWorkerProcess:
        def __init__(self, socket_path, *, replace_live_worker=False, max_requests=None, max_session_seconds=None):
            self.socket_path = socket_path
            self.replace_live_worker = replace_live_worker

        def start(self):
            return {"ok": True, "worker_session_id": "wrk_test", "health": {}}

        def shutdown(self):
            return {"ok": True}

    monkeypatch.setattr("aqs.session_runner.collect_system_profile", lambda: system_profile)
    monkeypatch.setattr("aqs.session_runner.capture_repo_metadata", lambda: repo_metadata)
    monkeypatch.setattr("aqs.session_runner.PersistentExecutorClient", RejectingClient)
    monkeypatch.setattr("aqs.session_runner.PersistentWorkerProcess", FakeWorkerProcess)
    monkeypatch.setattr(
        "aqs.session_runner.execute_selected_plan",
        lambda *args, **kwargs: {
            "workload_id": "wkl_test",
            "family_id": "dense_universal",
            "repeat_count_hint": 2,
            "system_name": "ovh_gra9_rtx5000_28",
            "system_manifest": load_yaml(SYSTEM_MANIFEST_PATH),
            "repo_metadata": repo_metadata,
            "probe": None,
            "selected_plan": {"plan_id": "plan_test", "precision": "complex128"},
            "selection_source": "plan_bundle_reuse",
            "execution_mode": "direct_executor",
            "plan_override_path": None,
            "plan_bundle_path": str(bundle_path),
            "plan_bundle_provenance": {"requested": True},
            "persistent_executor_provenance": {"requested": False},
            "driver_timing_json": {
                "worker_execute_s": 0.0,
                "worker_request_dispatch_s": 0.0,
                "worker_reply_s": 0.0,
                "session_request_index": 0,
            },
            "driver_total_s": 0.5,
            "outer_driver_overhead_s": 0.4,
            "profile_summary": None,
            "accuracy_eval": {"status": "pass", "rows": []},
            "execution_run": {
                "plan_id": "plan_test",
                "workload_id": "wkl_test",
                "system_id": "sys_test",
                "replicate_idx": 0,
                "graph_mode": "off",
                "status": "success",
                "started_at": "2026-04-06T00:00:00+00:00",
                "finished_at": "2026-04-06T00:00:01+00:00",
                "wall_s": 0.1,
                "ttfr_s": 0.08,
                "steady_iter_ms": 5.0,
                "gpu_seconds": 0.1,
                "peak_mem_gb": 0.1,
                "peak_workspace_gb": 2.7,
                "output_digest": "out_test",
                "execution_source": "cuquantum_tensornet_gpu",
                "failure_detail_json": {},
                "run_id": "run_test",
            },
            "linked_assets": [],
            "candidate_count": 3,
        },
    )

    summary = run_session(
        session_manifest=_session_manifest(bundle_path),
        session_manifest_path=tmp_path / "session.yaml",
        socket_path=tmp_path / "worker.sock",
        outdir=tmp_path / "out",
        spawn_temp_worker=True,
        allow_one_shot_fallback=True,
    )

    assert summary["spawn_temp_worker"] is True
    assert summary["fallback_count"] == 1
    assert summary["trace_rows"][0]["fallback_used"] is True
    assert "worker unavailable" in summary["trace_rows"][0]["fallback_reason"]
