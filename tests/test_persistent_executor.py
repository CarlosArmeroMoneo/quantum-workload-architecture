from __future__ import annotations

from contextlib import contextmanager
import socket
import threading
import time

import pytest

from aqs.execution import EXECUTION_VERSION, PLAN_BUNDLE_VERSION
from aqs.execution_real import REAL_EXECUTION_STACK_VERSION
from aqs.persistent_client import PersistentClientError
from aqs.persistent_executor import (
    PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
    PersistentExecutorClient,
    PersistentExecutorError,
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


def _request_payload(
    *,
    manifest: dict[str, object] | None = None,
    system_manifest: dict[str, object] | None = None,
    plan: dict[str, object] | None = None,
    command: str = "execute_bundle",
    context_overrides: dict[str, object] | None = None,
    config_overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    manifest = manifest or _test_manifest()
    system_manifest = system_manifest or _test_system_manifest()
    plan = plan or _test_plan()
    selection_source = "plan_bundle_reuse" if command == "execute_bundle" else "plan_override"
    bundle_hit = command == "execute_bundle"
    request_context = _request_context(
        manifest,
        system_manifest,
        plan,
        selection_source=selection_source,
        bundle_hit=bundle_hit,
    )
    if context_overrides:
        request_context.update(context_overrides)
    return {
        "protocol_version": PERSISTENT_EXECUTOR_PROTOCOL_VERSION,
        "command": command,
        "request_context": request_context,
        "workload_manifest": manifest,
        "system_manifest": system_manifest,
        "selected_plan": plan,
        "allow_distributed": False,
        "config": _test_config(**(config_overrides or {})),
    }


def _wait_for_client(socket_path, *, timeout_s: float = 2.0) -> PersistentExecutorClient:
    client = PersistentExecutorClient(socket_path, timeout_s=timeout_s)
    deadline = time.time() + timeout_s
    last_error = None
    while time.time() < deadline:
        try:
            ping = client.ping()
            if ping.get("ok"):
                return client
        except Exception as exc:  # pragma: no cover - startup retry guard
            last_error = exc
            time.sleep(0.02)
    raise RuntimeError(f"worker did not become ready: {last_error}")


def _wait_for_socket_gone(socket_path, *, timeout_s: float = 2.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not socket_path.exists():
            return
        time.sleep(0.02)
    raise AssertionError(f"socket path still exists after {timeout_s}s: {socket_path}")


def _patch_fake_worker_runtime(monkeypatch, calls: list[dict[str, object]]) -> None:
    class FakeDevice:
        id = 0

    class FakeRuntime:
        @staticmethod
        def memGetInfo():
            return 123_456_789, 987_654_321

    class FakeCuda:
        Device = FakeDevice
        runtime = FakeRuntime

    class FakeCuPy:
        cuda = FakeCuda

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
            "cupy": FakeCuPy(),
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


@contextmanager
def _running_fake_worker(monkeypatch, tmp_path, *, socket_name: str = "persistent.sock", **worker_kwargs):
    calls: list[dict[str, object]] = []
    _patch_fake_worker_runtime(monkeypatch, calls)

    socket_path = tmp_path / socket_name
    worker = PersistentRealExecutorWorker(socket_path, **worker_kwargs)
    thread = threading.Thread(target=worker.serve_forever, daemon=True)
    thread.start()
    client = _wait_for_client(socket_path)
    try:
        yield {
            "socket_path": socket_path,
            "client": client,
            "thread": thread,
            "worker": worker,
            "calls": calls,
        }
    finally:
        try:
            if socket_path.exists():
                client.shutdown()
        except Exception:
            pass
        thread.join(timeout=2.0)


@pytest.fixture
def fake_worker(monkeypatch, tmp_path):
    with _running_fake_worker(monkeypatch, tmp_path) as state:
        yield state


def test_persistent_worker_startup_status_and_shutdown_protocol(fake_worker):
    ping = fake_worker["client"].ping()
    status = fake_worker["client"].status()

    assert ping["ok"] is True
    assert ping["worker_session_id"].startswith("wrk_")
    assert status["ok"] is True
    assert status["runtime_metadata"]["execution_stack_version"] == EXECUTION_VERSION
    assert status["runtime_metadata"]["real_execution_stack_version"] == REAL_EXECUTION_STACK_VERSION
    assert status["runtime_metadata"]["bundle_schema_version"] == PLAN_BUNDLE_VERSION
    assert status["runtime_metadata"]["system_id"] == "sys_fake"
    assert status["health"]["worker_pid"] > 0
    assert status["health"]["request_count"] == 0
    assert status["health"]["device_id"] == 0
    assert status["health"]["gpu_mem_free_bytes"] == 123_456_789
    assert status["health"]["gpu_mem_total_bytes"] == 987_654_321
    assert status["session_bounds"] == {"max_requests": None, "max_session_seconds": None}

    shutdown = fake_worker["client"].shutdown()
    assert shutdown["ok"] is True
    fake_worker["thread"].join(timeout=2.0)
    _wait_for_socket_gone(fake_worker["socket_path"])


def test_persistent_worker_execute_bundle_round_trip(fake_worker):
    response = fake_worker["client"].execute_bundle(_request_payload())

    assert response["ok"] is True
    assert response["bundle"]["execution_run"]["status"] == "success"
    provenance = response["persistent_executor_provenance"]
    assert provenance["execution_mode"] == "persistent_executor"
    assert provenance["bundle_hit"] is True
    assert provenance["worker_warm"] is False
    assert provenance["worker_request_index"] == 1
    assert provenance["compatibility_match_reason"]


def test_persistent_worker_execute_plan_json_round_trip(fake_worker):
    response = fake_worker["client"].execute_plan_json(_request_payload(command="execute_plan_json"))

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
        ("repo_commit", {"repo_commit": "commit_other"}, {}),
        ("package_version", {"package_version": "1.2.3"}, {}),
    ],
)
def test_persistent_worker_rejects_mismatched_request_fields(fake_worker, field, context_overrides, config_overrides):
    response = fake_worker["client"].request(
        _request_payload(context_overrides=context_overrides, config_overrides=config_overrides)
    )

    assert response["ok"] is False
    assert response["error"]["reason_code"] == "persistent_executor_rejected"
    assert response["persistent_executor_provenance"]["compatibility_reject_reason"]
    assert response["persistent_executor_provenance"]["bundle_hit"] is True
    assert field in response["persistent_executor_provenance"]["compatibility_reject_reason"]


@pytest.mark.parametrize("field", ["bundle_schema_version", "execution_stack_version", "real_execution_stack_version"])
def test_persistent_worker_rejects_version_mismatches(fake_worker, field):
    request_context = dict(_request_payload()["request_context"])
    request_context[field] = "mismatch"
    payload = _request_payload()
    payload["request_context"] = request_context
    response = fake_worker["client"].request(payload)

    assert response["ok"] is False
    assert response["error"]["reason_code"] == "persistent_executor_rejected"
    assert field in response["persistent_executor_provenance"]["compatibility_reject_reason"]


def test_persistent_worker_emits_cold_and_warm_provenance(fake_worker):
    request = _request_payload()

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


def test_persistent_worker_refuses_live_socket_without_replace(monkeypatch, tmp_path):
    with _running_fake_worker(monkeypatch, tmp_path, socket_name="live.sock") as state:
        competing = PersistentRealExecutorWorker(state["socket_path"])
        with pytest.raises(PersistentExecutorError, match="live persistent executor already listening"):
            competing.serve_forever()


def test_persistent_worker_cleans_up_stale_socket(monkeypatch, tmp_path):
    stale_path = tmp_path / "stale.sock"
    stale_path.write_text("stale", encoding="utf-8")

    with _running_fake_worker(monkeypatch, tmp_path, socket_name="stale.sock") as state:
        assert state["worker"].startup_socket_action == "stale_socket_removed"
        assert state["client"].ping()["ok"] is True


def test_persistent_worker_shutdown_cleans_socket_and_allows_restart(monkeypatch, tmp_path):
    socket_path = tmp_path / "restart.sock"
    with _running_fake_worker(monkeypatch, tmp_path, socket_name="restart.sock") as first:
        first_session_id = first["client"].status()["worker_session_id"]
        first["client"].shutdown()
        first["thread"].join(timeout=2.0)
        _wait_for_socket_gone(socket_path)

    with _running_fake_worker(monkeypatch, tmp_path, socket_name="restart.sock") as second:
        second_session_id = second["client"].status()["worker_session_id"]
        assert second_session_id != first_session_id


def test_persistent_worker_replace_live_worker(monkeypatch, tmp_path):
    with _running_fake_worker(monkeypatch, tmp_path, socket_name="replace.sock") as first:
        socket_path = first["socket_path"]
        first_session_id = first["client"].status()["worker_session_id"]

        replacement = PersistentRealExecutorWorker(socket_path, replace_live_worker=True)
        replacement_thread = threading.Thread(target=replacement.serve_forever, daemon=True)
        replacement_thread.start()
        deadline = time.time() + 2.0
        replacement_client = None
        replacement_status = None
        while time.time() < deadline:
            client = _wait_for_client(socket_path)
            try:
                status = client.status()
            except Exception:
                time.sleep(0.05)
                continue
            if status["worker_session_id"] != first_session_id:
                replacement_client = client
                replacement_status = status
                break
            time.sleep(0.05)
        assert replacement_client is not None
        assert replacement_status is not None

        assert replacement_status["worker_session_id"] != first_session_id
        assert replacement.startup_socket_action == "replaced_live_worker"

        replacement_client.shutdown()
        replacement_thread.join(timeout=2.0)
        _wait_for_socket_gone(socket_path)


def test_persistent_worker_max_requests_stops_after_active_request(monkeypatch, tmp_path):
    with _running_fake_worker(monkeypatch, tmp_path, socket_name="maxreq.sock", max_requests=1) as state:
        response = state["client"].request(_request_payload())
        assert response["ok"] is True
        state["thread"].join(timeout=2.0)
        _wait_for_socket_gone(state["socket_path"])
        assert state["worker"].stop_reason == "max_requests_reached"


def test_persistent_worker_max_session_seconds_stops_cleanly(monkeypatch, tmp_path):
    with _running_fake_worker(monkeypatch, tmp_path, socket_name="maxtime.sock", max_session_seconds=0.15) as state:
        state["thread"].join(timeout=2.0)
        _wait_for_socket_gone(state["socket_path"])
        assert state["worker"].stop_reason == "max_session_seconds_reached"


def test_persistent_client_structured_error_on_malformed_response(tmp_path):
    socket_path = tmp_path / "malformed.sock"

    def fake_server():
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(socket_path))
            server.listen(1)
            conn, _ = server.accept()
            with conn:
                conn.recv(4096)
                conn.sendall(b"[]\n")

    thread = threading.Thread(target=fake_server, daemon=True)
    thread.start()
    deadline = time.time() + 1.0
    while time.time() < deadline and not socket_path.exists():
        time.sleep(0.01)

    client = PersistentExecutorClient(socket_path, timeout_s=1.0)
    with pytest.raises(PersistentClientError, match="JSON object"):
        client.ping()
    thread.join(timeout=1.0)
