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
    assert Path(tmp_path / 'measured_validation' / 'summary.json').exists()
