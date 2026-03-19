import json
from pathlib import Path

from aqs.arch import analyze_execution_json, analyze_execution_payload, analyze_measured_validation_summary
from aqs.execution import execute_selected_plan
from aqs.measured_validation import validate_measured_manifest


def test_arch_analyze_execution_payload_emits_nominations():
    payload = execute_selected_plan(
        'workloads/manifests/imported/qiskit_qasm2_ghz3.yaml',
        'configs/systems/cpu_probe.yml',
        measurement_repeats=2,
        allow_distributed=False,
    )
    analysis = analyze_execution_payload(payload)
    assert analysis['source_kind'] == 'execution_payload'
    assert analysis['source_run_id'] == payload['execution_run']['run_id']
    assert len(analysis['nominations']) >= 1
    assert analysis['nominations'][0]['counterfactual_knobs']


def test_arch_analyze_measured_validation_summary_aggregates(tmp_path):
    summary = validate_measured_manifest(
        'benchmarks/manifests/templates/tnep_measured_exact_slice.yaml',
        outdir=tmp_path / 'measured_validation',
    )
    analysis = analyze_measured_validation_summary(summary)
    assert analysis['source_kind'] == 'measured_validation_summary'
    assert analysis['workload_count'] >= 2
    assert Path(tmp_path / 'measured_validation' / 'summary.json').exists()
    assert analysis['ranked_bottleneck_families']


def test_analyze_execution_json_uses_adjacent_profile_summary_when_embedded_is_null(tmp_path):
    payload_path = tmp_path / 'real_dense_ring6_batched.ncu.deadbeef.execution.json'
    profile_path = tmp_path / 'real_dense_ring6_batched.ncu.deadbeef.profile_summary.json'

    payload = {
        'workload_id': 'wkl_real',
        'family_id': 'dense_universal',
        'repeat_count_hint': 12,
        'selected_plan': {
            'mode': 'exact_tn',
            'predicted_ttfr_s': 0.05,
        },
        'execution_run': {
            'run_id': 'run_real_adjacent',
            'ttfr_s': 0.09,
            'wall_s': 0.12,
            'failure_detail_json': {},
        },
        'profile_summary': None,
        'probe': {'raw_info_json': {'family_id': 'dense_universal'}},
        'system_manifest': {'gpu_mem_gb': 15.0},
    }
    profile_summary = {
        'profile_id': 'prof_adjacent',
        'profile_version': 'aqs.profile.real.v1',
        'profiler_kind': 'nsys',
        'nvtx_phase_times_json': {
            'load_circuit': 0.02,
            'convert_to_einsum': 0.01,
            'postprocess': 0.004,
            'contract_path': 0.008,
            'contract_first': 0.05,
            'contract_warm': 0.02,
        },
        'top_kernels_json': [],
        'dram_util_pct': None,
        'sm_util_pct': None,
        'occupancy_pct': None,
        'comm_time_pct': 0.0,
        'derived_signals_json': {'profile_source': 'real_nsys_profile'},
    }
    payload_path.write_text(json.dumps(payload), encoding='utf-8')
    profile_path.write_text(json.dumps(profile_summary), encoding='utf-8')

    analysis = analyze_execution_json(payload_path)

    assert analysis['source_profile_id'] == 'prof_adjacent'
    assert any(row['nomination_source'] == 'real_profiler_analysis' for row in analysis['nominations'])
    assert any(row['bottleneck_family'] == 'launch_overhead' for row in analysis['nominations'])


def test_arch_real_profile_falls_back_to_execution_phase_times_when_summary_is_sparse():
    payload = {
        'workload_id': 'wkl_sparse',
        'family_id': 'dense_universal',
        'repeat_count_hint': 12,
        'selected_plan': {
            'mode': 'exact_tn',
            'predicted_ttfr_s': 0.06,
        },
        'execution_run': {
            'run_id': 'run_sparse',
            'ttfr_s': 0.08,
            'wall_s': 0.11,
            'failure_detail_json': {
                'phase_times': {
                    'load_circuit': 0.018,
                    'convert_to_einsum': 0.01,
                    'postprocess': 0.002,
                    'contract_path': 0.007,
                    'contract_first': 0.03,
                    'contract_warm': 0.015,
                }
            },
        },
        'profile_summary': {
            'profile_id': 'prof_sparse',
            'profile_version': 'aqs.profile.real.v1',
            'profiler_kind': 'ncu',
            'nvtx_phase_times_json': {},
            'top_kernels_json': [],
            'dram_util_pct': None,
            'sm_util_pct': None,
            'occupancy_pct': None,
            'comm_time_pct': 0.0,
            'derived_signals_json': {'profile_source': 'real_ncu_profile'},
        },
        'probe': {'raw_info_json': {'family_id': 'dense_universal'}},
        'system_manifest': {'gpu_mem_gb': 15.0},
    }

    analysis = analyze_execution_payload(payload)

    launch = next(row for row in analysis['nominations'] if row['bottleneck_family'] == 'launch_overhead')
    assert analysis['source_profile_id'] == 'prof_sparse'
    assert launch['nomination_source'] == 'real_profiler_analysis'
    assert launch['supporting_profile_ids'] == ['prof_sparse']
    assert launch['nomination_reason_json']['setup_share_pct'] > 20.0
