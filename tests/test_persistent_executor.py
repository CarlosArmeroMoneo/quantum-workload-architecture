from __future__ import annotations

import threading
import time

import pytest

from aqs.execution import EXECUTION_VERSION, PLAN_BUNDLE_VERSION
from aqs.execution_real import REAL_EXECUTION_STACK_VERSION
from aqs.persistent_executor import (
    PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
    PersistentExecutorClient,
    PersistentRealExecutorWorker,
)
from aqs.utils import canonical_json, sha256_text


def _manifest_digest(payload):
    return sha256_text(canonical_json(payload))


def _test_manifest() -> dict[str, object]:
    return {
        "api_version": "aqs.workload.v1",
        "family_id": "test_family",
        "source_format": "qiskit",
        "semantic_target": "amplitude",
        "execution_target": {"kind": "amplitude", "bitstring": "00"},
        "repeat_count_hint": 1,
        "ids": {"workload_id": "wkl_test"},
        "source": {"loader": "qasm2_inline", "text": "OPENQASM 2.0;"},
    }


def _test_system_manifest() -> dict[str, object]:
    return {
        "system_name": "sys_test",
    }


def _test_plan() -> dict[str, object]:
    return {
        "plan_id": "plan_test",
        "mode": "exact_tn",
        "precision": "complex128",
        "workspace_gb": 1.0,
    }


def _test_config(**overrides) -> dict[str, object]:
    base = {
        "objective": "ttfr",
        "precision": "complex128",
        "probe_strategy": "real_if_available",
        "measurement_repeats": 2,
        "ttfr_repeats": 1,
        "execution_intent": "require_real",
        "replicate_idx": 7,
        "graph_mode": "off",
        "prewarm_mode": "none",
    }
    base.update(overrides)
    return base


def _request_context(
    manifest: dict[str, object],
    system_manifest: dict[str, object],
    plan: dict[str, object],
    *,
    selection_source: str,
    bundle_hit: bool,
    system_id: str = "sys_fake",
    objective: str = "ttfr",
    precision: str = "complex128",
    graph_mode: str = "off",
    execution_intent: str = "require_real",
    allow_distributed: bool = False,
    repo_commit: str = "commit_fake",
    package_version: str = "0.0-test",
) -> dict[str, object]:
    return {
        "workload_manifest_digest": _manifest_digest(manifest),
        "workload_id": manifest["ids"]["workload_id"],
        "system_manifest_digest": _manifest_digest(system_manifest),
        "system_name": system_manifest["system_name"],
        "system_id": system_id,
        "objective": objective,
        "precision": precision,
        "graph_mode": graph_mode,
        "execution_intent": execution_intent,
        "allow_distributed": allow_distributed,
        "bundle_schema_version": PLAN_BUNDLE_VERSION,
        "execution_stack_version": EXECUTION_VERSION,
        "real_execution_stack_version": REAL_EXECUTION_STACK_VERSION,
        "repo_commit": repo_commit,
        "package_version": package_version,
        "selected_plan_id": plan["plan_id"],
        "selection_source": selection_source,
        "bundle_hit": bundle_hit,
    }


@pytest.fixture
def fake_worker(monkeypatch, tmp_path):
    socket_path = tmp_path / "persistent.sock"
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "aqs.persistent_executor.capture_repo_metadata",
        lambda: {
            "git_commit": "commit_fake",
            "package_version": "0.0-test",
        },
    )
    monkeypatch.setattr(
        "aqs.persistent_executor.initialize_real_execution_runtime",
        lambda touch_context=True: {
            "system_profile": {
                "system_id": "sys_fake",
                "gpu_present": True,
                "cupy_present": True,
                "cuquantum_present": True,
                "qiskit_present": True,
            },
            "cupy": object(),
            "Network": object(),
            "CircuitToEinsum": object(),
            "startup_s": 0.321,
            "started_at": "2026-04-05T00:00:00+00:00",
        },
    )

    def fake_execute_real_plan_candidate_with_runtime(manifest, plan, *, runtime, config):
        calls.append(
            {
                "manifest": manifest,
                "plan_id": plan["plan_id"],
                "replicate_idx": config.replicate_idx,
                "import_real_stack_s": float(runtime.get("request_import_real_stack_s") or 0.0),
            }
        )
        request_index = len(calls)
        return {
            "execution_run": {
                "plan_id": plan["plan_id"],
                "workload_id": manifest["ids"]["workload_id"],
                "system_id": "sys_fake",
                "replicate_idx": config.replicate_idx,
                "graph_mode": config.graph_mode,
                "status": "success",
                "started_at": "2026-04-05T00:00:00+00:00",
                "finished_at": "2026-04-05T00:00:01+00:00",
                "wall_s": 0.111 + (request_index * 0.001),
                "ttfr_s": 0.101,
                "steady_iter_ms": 9.5,
                "gpu_seconds": 0.111,
                "peak_mem_gb": 0.25,
                "peak_workspace_gb": 1.0,
                "output_digest": "out_test",
                "execution_source": "cuquantum_tensornet_gpu",
                "failure_detail_json": {
                    "graph_mode": config.graph_mode,
                    "import_real_stack_s": float(runtime.get("request_import_real_stack_s") or 0.0),
                },
                "run_id": f"run_test_{request_index}",
            },
            "accuracy_eval": {"status": "pass", "rows": []},
            "profile_summary": None,
            "linked_assets": [],
            "driver_timing_json": {
                "real_execute_s": 0.111,
                "post_execution_s": 0.004,
                "pre_execute_request_validation_s": 0.002,
                "import_real_stack_s": float(runtime.get("request_import_real_stack_s") or 0.0),
                "network_build_s": 0.013,
                "pre_t_start_overhead_s": 0.002,
            },
        }

    monkeypatch.setattr(
        "aqs.persistent_executor.execute_real_plan_candidate_with_runtime",
        fake_execute_real_plan_candidate_with_runtime,
    )

    worker = PersistentRealExecutorWorker(socket_path)
    thread = threading.Thread(target=worker.serve_forever, daemon=True)
    thread.start()

    client = PersistentExecutorClient(socket_path, timeout_s=2.0)
    deadline = time.time() + 2.0
    last_error = None
    while time.time() < deadline:
        try:
            ping = client.ping()
            if ping.get("ok"):
                break
        except Exception as exc:  # pragma: no cover - retry loop guard
            last_error = exc
            time.sleep(0.02)
    else:  # pragma: no cover - startup guard
        raise RuntimeError(f"worker did not become ready: {last_error}")

    yield {
        "socket_path": str(socket_path),
        "client": client,
        "thread": thread,
        "calls": calls,
    }

    try:
        client.shutdown()
    except Exception:
        pass
    thread.join(timeout=2.0)


def test_persistent_worker_startup_and_shutdown_protocol(fake_worker):
    ping = fake_worker["client"].ping()
    assert ping["ok"] is True
    assert ping["worker_session_id"].startswith("wrk_")
    shutdown = fake_worker["client"].shutdown()
    assert shutdown["ok"] is True


def test_persistent_worker_execute_bundle_round_trip(fake_worker):
    manifest = _test_manifest()
    system_manifest = _test_system_manifest()
    plan = _test_plan()
    response = fake_worker["client"].request(
        {
            "protocol_version": PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
            "command": "execute_bundle",
            "request_context": _request_context(manifest, system_manifest, plan, selection_source="plan_bundle_reuse", bundle_hit=True),
            "workload_manifest": manifest,
            "system_manifest": system_manifest,
            "selected_plan": plan,
            "allow_distributed": False,
            "config": _test_config(),
        }
    )

    assert response["ok"] is True
    assert response["bundle"]["execution_run"]["status"] == "success"
    provenance = response["persistent_executor_provenance"]
    assert provenance["execution_mode"] == "persistent_executor"
    assert provenance["bundle_hit"] is True
    assert provenance["worker_warm"] is False
    assert provenance["worker_request_index"] == 1
    assert provenance["compatibility_match_reason"]


def test_persistent_worker_execute_plan_json_round_trip(fake_worker):
    manifest = _test_manifest()
    system_manifest = _test_system_manifest()
    plan = _test_plan()
    response = fake_worker["client"].request(
        {
            "protocol_version": PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
            "command": "execute_plan_json",
            "request_context": _request_context(manifest, system_manifest, plan, selection_source="plan_override", bundle_hit=False),
            "workload_manifest": manifest,
            "system_manifest": system_manifest,
            "selected_plan": plan,
            "allow_distributed": False,
            "config": _test_config(),
        }
    )

    assert response["ok"] is True
    assert response["persistent_executor_provenance"]["bundle_hit"] is False
    assert response["bundle"]["execution_run"]["plan_id"] == "plan_test"


@pytest.mark.parametrize(
    ("field", "context_overrides", "config_overrides"),
    [
        ("system_id", {"system_id": "sys_other"}, {}),
        ("objective", {"objective": "steady_state"}, {"objective": "ttfr"}),
        ("precision", {"precision": "complex64"}, {"precision": "complex128"}),
        ("graph_mode", {"graph_mode": "steady_state"}, {"graph_mode": "off"}),
    ],
)
def test_persistent_worker_rejects_mismatched_request_fields(fake_worker, field, context_overrides, config_overrides):
    manifest = _test_manifest()
    system_manifest = _test_system_manifest()
    plan = _test_plan()
    response = fake_worker["client"].request(
        {
            "protocol_version": PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
            "command": "execute_bundle",
            "request_context": _request_context(
                manifest,
                system_manifest,
                plan,
                selection_source="plan_bundle_reuse",
                bundle_hit=True,
                **context_overrides,
            ),
            "workload_manifest": manifest,
            "system_manifest": system_manifest,
            "selected_plan": plan,
            "allow_distributed": False,
            "config": _test_config(**config_overrides),
        }
    )

    assert response["ok"] is False
    assert response["error"]["reason_code"] == "persistent_executor_rejected"
    assert response["persistent_executor_provenance"]["compatibility_reject_reason"]
    assert response["persistent_executor_provenance"]["bundle_hit"] is True
    assert field in response["persistent_executor_provenance"]["compatibility_reject_reason"]


@pytest.mark.parametrize("field", ["bundle_schema_version", "execution_stack_version", "real_execution_stack_version"])
def test_persistent_worker_rejects_version_mismatches(fake_worker, field):
    manifest = _test_manifest()
    system_manifest = _test_system_manifest()
    plan = _test_plan()
    request_context = _request_context(manifest, system_manifest, plan, selection_source="plan_bundle_reuse", bundle_hit=True)
    request_context[field] = "mismatch"
    response = fake_worker["client"].request(
        {
            "protocol_version": PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
            "command": "execute_bundle",
            "request_context": request_context,
            "workload_manifest": manifest,
            "system_manifest": system_manifest,
            "selected_plan": plan,
            "allow_distributed": False,
            "config": _test_config(),
        }
    )

    assert response["ok"] is False
    assert response["error"]["reason_code"] == "persistent_executor_rejected"
    assert field in response["persistent_executor_provenance"]["compatibility_reject_reason"]


def test_persistent_worker_emits_cold_and_warm_provenance(fake_worker):
    manifest = _test_manifest()
    system_manifest = _test_system_manifest()
    plan = _test_plan()
    request = {
        "protocol_version": PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
        "command": "execute_bundle",
        "request_context": _request_context(manifest, system_manifest, plan, selection_source="plan_bundle_reuse", bundle_hit=True),
        "workload_manifest": manifest,
        "system_manifest": system_manifest,
        "selected_plan": plan,
        "allow_distributed": False,
        "config": _test_config(),
    }

    cold = fake_worker["client"].request(request)
    warm = fake_worker["client"].request(request)

    assert cold["ok"] is True
    assert warm["ok"] is True
    assert cold["persistent_executor_provenance"]["worker_warm"] is False
    assert warm["persistent_executor_provenance"]["worker_warm"] is True
    assert cold["persistent_executor_provenance"]["worker_request_index"] == 1
    assert warm["persistent_executor_provenance"]["worker_request_index"] == 2
    assert cold["bundle"]["driver_timing_json"]["import_real_stack_s"] == 0.0
    assert warm["bundle"]["driver_timing_json"]["import_real_stack_s"] == 0.0
