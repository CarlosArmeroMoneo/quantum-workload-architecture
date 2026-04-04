from pathlib import Path

from aqs.measured_validation import validate_measured_manifest


def test_measured_validation_reports_summary(tmp_path):
    summary = validate_measured_manifest(
        'benchmarks/manifests/templates/tnep_measured_exact_slice.yaml',
        outdir=tmp_path / 'measured_validation',
    )
    assert summary['evaluation_source'] == 'measured'
    assert summary['workload_count'] >= 2
    assert 0.0 <= summary['top1_accuracy'] <= 1.0
    assert 0.0 <= summary['top1_within_1ms_rate'] <= 1.0
    assert 0.0 <= summary['top1_within_3pct_rate'] <= 1.0
    assert summary['confidence_version'] == 'aqs.validation_confidence.v1'
    assert summary['selection_confidence_counts'].keys() == {'low', 'medium', 'high'}
    assert summary['stable_selected_miss_count'] >= 0
    assert summary['selected_dominated_by_top2_count'] >= 0
    assert summary['anchor_candidate_count'] >= 0
    assert isinstance(summary['anchor_candidate_workloads'], list)
    assert isinstance(summary.get('warnings'), list)
    assert Path(summary['summary_path']).exists()
    assert Path(summary['confidence_summary_json_path']).exists()
    assert Path(summary['confidence_summary_path']).exists()
    if summary['heldout_workload_count'] < 5:
        assert any('heldout_workload_count=' in warning for warning in summary['warnings'])
    assert all('selection_confidence' in row for row in summary['results'])
    assert Path(tmp_path / 'measured_validation' / 'summary.json').exists()
    assert Path(tmp_path / 'measured_validation' / 'confidence_summary.json').exists()
    assert Path(tmp_path / 'measured_validation' / 'confidence_summary.md').exists()
