from pathlib import Path

import aqs.validation as validation_module
from aqs.validation import validate_planner_manifest


def test_validation_manifest_reports_holdout_and_regret(tmp_path, monkeypatch):
    selected_paths = [
        Path("workloads/manifests/validation/dense_universal_train.yaml"),
        Path("workloads/manifests/validation/qaoa_graph_heldout_barabasi.yaml"),
        Path("workloads/manifests/validation/qaoa_graph_train_ring.yaml"),
        Path("workloads/manifests/validation/trotter_1d_train_open.yaml"),
    ]
    monkeypatch.setattr(validation_module, "_resolve_repo_glob", lambda _glob_expr: selected_paths)
    monkeypatch.setattr(
        validation_module,
        "run_exact_tn_probe",
        lambda _manifest, _config: {
            "probe_id": "probe_validation_stub",
            "mode": "exact_tn",
            "objective": "ttfr",
            "precision": "complex128",
            "predicted_peak_gb": 4.0,
            "predicted_error": 0.0,
            "optimizer_cost": 4096.0,
            "largest_intermediate": 1024.0,
            "num_slices": 1,
        },
    )
    summary = validate_planner_manifest(
        'benchmarks/manifests/templates/tnep_planner_validation.yaml',
        outdir=tmp_path / 'validation',
    )
    assert summary['workload_count'] >= 4
    assert summary['heldout_workload_count'] >= 1
    assert 0.0 <= summary['top1_accuracy'] <= 1.0
    assert 0.0 <= summary['top1_within_1ms_rate'] <= 1.0
    assert 0.0 <= summary['top1_within_3pct_rate'] <= 1.0
    assert summary['mean_regret'] is None or summary['mean_regret'] >= 0.0
    assert summary['confidence_version'] == 'aqs.validation_confidence.v1'
    assert summary['selection_confidence_counts'].keys() == {'low', 'medium', 'high'}
    assert isinstance(summary.get('warnings'), list)
    if summary['heldout_workload_count'] < 5:
        assert any('heldout_workload_count=' in warning for warning in summary['warnings'])
    assert any(row['split_tag'] == 'heldout_family' for row in summary['results'])
    assert all('selection_confidence' in row for row in summary['results'])
    assert Path(tmp_path / 'validation' / 'summary.json').exists()
    assert any(row['regret'] is not None for row in summary['results'])
