from pathlib import Path

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
