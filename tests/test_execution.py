import json

import pytest

from aqs.execution import ExecutionError, execute_selected_plan


def test_execute_selected_plan_emits_measured_run(tmp_path):
    payload = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
    )
    run = payload['execution_run']
    assert payload['selected_plan']['mode'] == 'exact_tn'
    assert run['status'] == 'success'
    assert run['execution_source'] == 'measured_structural_cpu_hybrid'
    assert run['ttfr_s'] is not None and run['ttfr_s'] >= 0.0
    assert run['steady_iter_ms'] is not None and run['steady_iter_ms'] >= 0.0
    assert payload['repo_metadata']['package_version']
    timings = payload['driver_timing_json']
    assert {'bundle_lookup_s', 'bundle_compatibility_check_s', 'dispatch_real_executor_s', 'real_execute_s', 'post_execution_s'} <= set(timings)


def test_execute_selected_plan_supports_plan_override_and_replicate_lineage(tmp_path):
    baseline = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
    )
    plan_path = tmp_path / 'selected_plan.json'
    overridden_plan = dict(baseline["selected_plan"])
    overridden_plan["graph_mode"] = "steady_state"
    plan_path.write_text(json.dumps({"selected_plan": overridden_plan}), encoding='utf-8')

    overridden = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_json_path=str(plan_path),
        replicate_idx=1,
    )

    assert overridden['selection_source'] == 'plan_override'
    assert overridden['candidate_count'] == 0
    assert overridden['plan_override_path'].endswith('selected_plan.json')
    assert overridden['execution_run']['replicate_idx'] == 1
    assert overridden['execution_run']['graph_mode'] == 'steady_state'
    assert overridden['execution_run']['failure_detail_json']['graph_mode'] == 'steady_state'
    assert overridden['execution_run']['run_id'] != baseline['execution_run']['run_id']


def test_execute_selected_plan_tracks_graph_mode_in_lineage_and_profile():
    baseline = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
    )
    warm_only = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        graph_mode='warm_only',
    )

    assert baseline['execution_run']['graph_mode'] == 'off'
    assert warm_only['execution_run']['graph_mode'] == 'warm_only'
    assert warm_only['execution_run']['failure_detail_json']['graph_mode'] == 'warm_only'
    assert warm_only['profile_summary']['derived_signals_json']['graph_mode'] == 'warm_only'
    assert warm_only['execution_run']['run_id'] != baseline['execution_run']['run_id']


def test_execute_selected_plan_supports_plan_bundle_miss_then_hit(tmp_path):
    bundle_path = tmp_path / 'selected_plan.bundle.json'

    fresh = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
    )

    assert bundle_path.exists()
    assert fresh['selection_source'] in {'plan_rank', 'planner_top_pick'}
    assert fresh['plan_bundle_provenance']['cache_status'] == 'miss'
    assert fresh['plan_bundle_provenance']['write_status'] == 'written'
    assert fresh['driver_timing_json']['total_s'] >= fresh['driver_timing_json']['execute_plan_bundle_s']
    assert fresh['outer_driver_overhead_s'] >= 0.0
    assert fresh['driver_timing_json']['bundle_lookup_s'] >= 0.0
    assert fresh['driver_timing_json']['bundle_compatibility_check_s'] == 0.0

    reused = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
    )

    assert reused['selection_source'] == 'plan_bundle_reuse'
    assert reused['candidate_count'] == 0
    assert reused['probe'] is None
    assert reused['selected_plan']['plan_id'] == fresh['selected_plan']['plan_id']
    assert reused['plan_bundle_provenance']['cache_status'] == 'hit'
    assert reused['plan_bundle_provenance']['write_status'] == 'skipped_hit'
    assert reused['plan_bundle_provenance']['compatibility']['compatible'] is True
    assert reused['driver_timing_json']['probe_s'] == 0.0
    assert reused['driver_timing_json']['candidate_generation_s'] == 0.0
    assert reused['driver_timing_json']['bundle_lookup_s'] >= 0.0
    assert reused['driver_timing_json']['bundle_compatibility_check_s'] >= 0.0


def test_execute_selected_plan_rejects_incompatible_plan_bundle(tmp_path):
    bundle_path = tmp_path / 'selected_plan.bundle.json'
    execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
    )

    payload = json.loads(bundle_path.read_text(encoding='utf-8'))
    payload['bundle_scope']['workload_id'] = 'workload_mismatch'
    bundle_path.write_text(json.dumps(payload), encoding='utf-8')

    rejected = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
    )

    assert rejected['selection_source'] in {'plan_rank', 'planner_top_pick'}
    assert rejected['candidate_count'] > 0
    assert rejected['plan_bundle_provenance']['cache_status'] == 'rejected'
    assert rejected['plan_bundle_provenance']['write_status'] == 'skipped_rejected'
    assert rejected['plan_bundle_provenance']['compatibility']['compatible'] is False
    assert 'workload_id' in rejected['plan_bundle_provenance']['compatibility']['mismatched_fields']


def test_execute_selected_plan_rejects_plan_bundle_with_execution_stack_version_mismatch(tmp_path):
    bundle_path = tmp_path / 'selected_plan.bundle.json'
    execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
    )

    payload = json.loads(bundle_path.read_text(encoding='utf-8'))
    payload['bundle_scope']['execution_stack_version'] = 'aqs.execution.v1'
    bundle_path.write_text(json.dumps(payload), encoding='utf-8')

    rejected = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
    )

    assert rejected['plan_bundle_provenance']['cache_status'] == 'rejected'
    assert 'execution_stack_version' in rejected['plan_bundle_provenance']['compatibility']['mismatched_fields']


def test_execute_selected_plan_keeps_selected_plan_id_stable_across_fresh_override_and_bundle_hit(tmp_path):
    fresh = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
    )
    fresh_plan_id = fresh['selected_plan']['plan_id']

    plan_path = tmp_path / 'selected_plan.json'
    plan_path.write_text(json.dumps({'selected_plan': dict(fresh['selected_plan'])}), encoding='utf-8')
    overridden = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_json_path=str(plan_path),
    )

    bundle_path = tmp_path / 'selected_plan.bundle.json'
    seed_bundle = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
    )
    reused = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
    )

    assert overridden['selected_plan']['plan_id'] == fresh_plan_id
    assert seed_bundle['selected_plan']['plan_id'] == fresh_plan_id
    assert reused['selected_plan']['plan_id'] == fresh_plan_id


def test_execute_selected_plan_keeps_selected_plan_id_stable_on_persistent_bundle_hit(tmp_path, monkeypatch):
    fresh = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
    )
    bundle_path = tmp_path / 'selected_plan.bundle.json'
    execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
    )

    class FakePersistentClient:
        def __init__(self, socket_path, *, timeout_s=60.0):
            self.socket_path = socket_path
            self.timeout_s = timeout_s

        def request(self, payload):
            selected_plan = dict(payload["selected_plan"])
            return {
                "ok": True,
                "persistent_executor_provenance": {
                    "execution_mode": "persistent_executor",
                    "bundle_hit": True,
                    "worker_session_id": "wrk_test",
                    "worker_warm": True,
                    "worker_start_time": "2026-04-05T00:00:00+00:00",
                    "worker_request_index": 2,
                    "compatibility_match_reason": "request fingerprint matched the current worker environment",
                    "compatibility_reject_reason": None,
                },
                "driver_timing_json": {
                    "worker_startup_s": 0.25,
                    "worker_request_dispatch_s": 0.01,
                    "worker_execute_s": 0.11,
                    "worker_reply_s": 0.002,
                    "session_request_index": 2,
                    "session_uptime_s": 1.5,
                },
                "bundle": {
                    "execution_run": {
                        "plan_id": selected_plan["plan_id"],
                        "workload_id": "wkl_ghz3_qasm2_imported",
                        "system_id": "sys_cpu_probe",
                        "replicate_idx": 0,
                        "graph_mode": "off",
                        "status": "success",
                        "started_at": "2026-04-05T00:00:00+00:00",
                        "finished_at": "2026-04-05T00:00:01+00:00",
                        "wall_s": 0.11,
                        "ttfr_s": 0.10,
                        "steady_iter_ms": 5.0,
                        "gpu_seconds": 0.11,
                        "peak_mem_gb": None,
                        "peak_workspace_gb": 0.0,
                        "output_digest": "out_test",
                        "execution_source": "cuquantum_tensornet_gpu",
                        "failure_detail_json": {},
                        "run_id": "run_test",
                    },
                    "accuracy_eval": {"status": "pass", "rows": []},
                    "profile_summary": None,
                    "linked_assets": [],
                    "driver_timing_json": {
                        "real_execute_s": 0.11,
                        "post_execution_s": 0.003,
                        "pre_execute_request_validation_s": 0.001,
                        "import_real_stack_s": 0.0,
                        "network_build_s": 0.01,
                        "pre_t_start_overhead_s": 0.001,
                    },
                },
            }

        def execute_bundle(self, payload):
            return self.request(payload)

        def execute_plan_json(self, payload):
            return self.request(payload)

    monkeypatch.setattr("aqs.persistent_client.PersistentExecutorClient", FakePersistentClient)

    persistent = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
        persistent_worker_socket=str(tmp_path / 'worker.sock'),
    )

    assert persistent['selected_plan']['plan_id'] == fresh['selected_plan']['plan_id']
    assert persistent['selection_source'] == 'plan_bundle_reuse'
    assert persistent['execution_mode'] == 'persistent_executor'
    assert persistent['persistent_executor_provenance']['worker_session_id'] == 'wrk_test'
    assert persistent['driver_timing_json']['worker_execute_s'] == 0.11


def test_execute_selected_plan_requires_explicit_override_or_bundle_for_persistent_mode(tmp_path):
    with pytest.raises(ExecutionError):
        execute_selected_plan(
            'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
            'configs/systems/cpu_probe.yml',
            measurement_repeats=2,
            allow_distributed=False,
            persistent_worker_socket=str(tmp_path / 'worker.sock'),
        )


def test_execute_selected_plan_persistent_request_failure_can_fallback_to_direct_execution(tmp_path, monkeypatch):
    fresh = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
    )
    bundle_path = tmp_path / 'selected_plan.bundle.json'
    execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
    )

    class FailingPersistentClient:
        def __init__(self, socket_path, *, timeout_s=60.0):
            self.socket_path = socket_path
            self.timeout_s = timeout_s

        def request(self, payload):
            raise RuntimeError('worker unavailable')

        def execute_bundle(self, payload):
            return self.request(payload)

        def execute_plan_json(self, payload):
            return self.request(payload)

    monkeypatch.setattr('aqs.persistent_client.PersistentExecutorClient', FailingPersistentClient)

    payload = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
        persistent_worker_socket=str(tmp_path / 'worker.sock'),
        allow_one_shot_fallback=True,
    )

    assert payload['execution_mode'] == 'direct_executor'
    assert payload['selected_plan']['plan_id'] == fresh['selected_plan']['plan_id']
    assert payload['persistent_executor_provenance']['requested'] is True
    assert payload['persistent_executor_provenance']['persistent_used'] is False
    assert payload['persistent_executor_provenance']['fallback_used'] is True
    assert 'worker unavailable' in payload['persistent_executor_provenance']['fallback_reason']
    assert payload['execution_run']['status'] == 'success'


def test_execute_selected_plan_persistent_rejection_can_fallback_to_direct_execution(tmp_path, monkeypatch):
    bundle_path = tmp_path / 'selected_plan.bundle.json'
    execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
    )

    class RejectingPersistentClient:
        def __init__(self, socket_path, *, timeout_s=60.0):
            self.socket_path = socket_path
            self.timeout_s = timeout_s

        def request(self, payload):
            return {
                'ok': False,
                'persistent_executor_provenance': {
                    'execution_mode': 'persistent_executor',
                    'bundle_hit': True,
                    'worker_session_id': 'wrk_test',
                    'worker_warm': True,
                    'worker_start_time': '2026-04-05T00:00:00+00:00',
                    'worker_request_index': 2,
                    'compatibility_match_reason': None,
                    'compatibility_reject_reason': 'request compatibility fingerprint did not match the worker session: objective',
                },
                'driver_timing_json': {
                    'worker_startup_s': 0.25,
                    'worker_request_dispatch_s': 0.01,
                    'worker_execute_s': 0.0,
                    'worker_reply_s': 0.002,
                    'session_request_index': 2,
                    'session_uptime_s': 1.5,
                },
                'error': {
                    'reason_code': 'persistent_executor_rejected',
                    'message': 'request compatibility fingerprint did not match the worker session: objective',
                },
            }

        def execute_bundle(self, payload):
            return self.request(payload)

        def execute_plan_json(self, payload):
            return self.request(payload)

    monkeypatch.setattr('aqs.persistent_client.PersistentExecutorClient', RejectingPersistentClient)

    payload = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
        persistent_worker_socket=str(tmp_path / 'worker.sock'),
        allow_one_shot_fallback=True,
    )

    assert payload['execution_mode'] == 'direct_executor'
    assert payload['persistent_executor_provenance']['persistent_used'] is False
    assert payload['persistent_executor_provenance']['fallback_used'] is True
    assert 'objective' in payload['persistent_executor_provenance']['compatibility_reject_reason']
    assert 'objective' in payload['persistent_executor_provenance']['fallback_reason']
    assert payload['execution_run']['status'] == 'success'


def test_execute_selected_plan_persistent_request_failure_is_not_silent_without_fallback(tmp_path, monkeypatch):
    bundle_path = tmp_path / 'selected_plan.bundle.json'
    execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
        plan_bundle_path=str(bundle_path),
    )

    class FailingPersistentClient:
        def __init__(self, socket_path, *, timeout_s=60.0):
            self.socket_path = socket_path
            self.timeout_s = timeout_s

        def request(self, payload):
            raise RuntimeError('worker unavailable')

        def execute_bundle(self, payload):
            return self.request(payload)

        def execute_plan_json(self, payload):
            return self.request(payload)

    monkeypatch.setattr('aqs.persistent_client.PersistentExecutorClient', FailingPersistentClient)

    with pytest.raises(ExecutionError, match='worker unavailable'):
        execute_selected_plan(
            'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
            'configs/systems/cpu_probe.yml',
            measurement_repeats=2,
            allow_distributed=False,
            plan_bundle_path=str(bundle_path),
            persistent_worker_socket=str(tmp_path / 'worker.sock'),
        )


def test_execute_selected_plan_rejects_plan_json_and_plan_bundle_together(tmp_path):
    plan_path = tmp_path / 'selected_plan.json'
    plan_path.write_text(json.dumps({'selected_plan': {'plan_id': 'plan_test'}}), encoding='utf-8')

    with pytest.raises(ExecutionError):
        execute_selected_plan(
            'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
            'configs/systems/cpu_probe.yml',
            measurement_repeats=2,
            allow_distributed=False,
            plan_json_path=str(plan_path),
            plan_bundle_path=str(tmp_path / 'selected_plan.bundle.json'),
        )
