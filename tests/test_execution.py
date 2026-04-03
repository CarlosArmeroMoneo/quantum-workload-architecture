import json

from aqs.execution import execute_selected_plan


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


def test_execute_selected_plan_supports_plan_override_and_replicate_lineage(tmp_path):
    baseline = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
    )
    plan_path = tmp_path / 'selected_plan.json'
    plan_path.write_text(json.dumps({"selected_plan": baseline["selected_plan"]}), encoding='utf-8')

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
    assert overridden['execution_run']['run_id'] != baseline['execution_run']['run_id']
