from pathlib import Path

from aqs.validation import validate_planner_manifest


def test_validation_manifest_reports_holdout_and_regret(tmp_path):
    summary = validate_planner_manifest(
        'benchmarks/manifests/templates/tnep_planner_validation.yaml',
        outdir=tmp_path / 'validation',
    )
    assert summary['workload_count'] >= 4
    assert summary['heldout_workload_count'] >= 1
    assert 0.0 <= summary['top1_accuracy'] <= 1.0
    assert summary['mean_regret'] is None or summary['mean_regret'] >= 0.0
    assert any(row['split_tag'] == 'heldout_family' for row in summary['results'])
    assert Path(tmp_path / 'validation' / 'summary.json').exists()
    assert any((row['regret'] or 0.0) > 0.0 for row in summary['results'])
