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
