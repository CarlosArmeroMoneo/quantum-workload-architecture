from aqs.execution import execute_selected_plan


def test_execute_selected_plan_emits_profile_summary():
    payload = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
    )
    profile = payload['profile_summary']
    assert profile['profiler_kind'] == 'synthetic'
    assert 'path_search' in profile['nvtx_phase_times_json']
    assert 'derived_signals_json' in profile
    derived = profile['derived_signals_json']
    assert derived['profile_source'] == 'synthetic_phase_profile'
    assert derived['planner_share_pct'] >= 0.0
    assert derived['contract_share_pct'] >= 0.0
