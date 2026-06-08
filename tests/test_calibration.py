from __future__ import annotations

from aqs.calibration import (
    CONTRACTION_DOMINATED,
    INSUFFICIENT_EVIDENCE,
    LAUNCH_OVERHEAD_DOMINATED,
    MODEL_MISCALIBRATED,
    TINY_WORKLOAD_OVERHEAD_RISK,
    annotate_calibration_record,
    classify_calibration_record,
)


def _base_record() -> dict[str, object]:
    return {
        "run_id": "run_test",
        "workload_id": "wkl_test",
        "host_id": "host_test",
        "evidence_tier": "Tier 2",
        "n_qubits": 8,
        "tensor_count": 24,
        "setup_share_pct": 10.0,
        "contract_share_pct": 50.0,
        "predicted_ttfr_s": 1.0,
        "actual_ttfr_s": 1.0,
        "predicted_iter_ms": 10.0,
        "actual_iter_ms": 10.0,
    }


def test_calibration_classifier_setup_dominated_case():
    record = _base_record()
    record["setup_share_pct"] = 25.0
    assert classify_calibration_record(record) == LAUNCH_OVERHEAD_DOMINATED


def test_calibration_classifier_contraction_dominated_case():
    record = _base_record()
    record["contract_share_pct"] = 70.0
    assert classify_calibration_record(record) == CONTRACTION_DOMINATED


def test_calibration_classifier_model_miscalibrated_case():
    record = _base_record()
    record["actual_iter_ms"] = 31.0
    annotated = annotate_calibration_record(record)
    assert annotated["iter_error_ratio"] == 3.1
    assert annotated["interpretation_class"] == MODEL_MISCALIBRATED


def test_calibration_classifier_tiny_workload_risk_case():
    record = _base_record()
    record["n_qubits"] = 3
    record["tensor_count"] = 6
    assert classify_calibration_record(record) == TINY_WORKLOAD_OVERHEAD_RISK


def test_calibration_classifier_missing_fields():
    record = _base_record()
    record.pop("setup_share_pct")
    assert classify_calibration_record(record) == INSUFFICIENT_EVIDENCE


def test_calibration_zero_prediction_values_do_not_crash():
    record = _base_record()
    record["predicted_ttfr_s"] = 0.0
    record["actual_ttfr_s"] = 1.0
    record["setup_share_pct"] = 25.0
    annotated = annotate_calibration_record(record)
    assert "ttfr_error_ratio" not in annotated
    assert annotated["interpretation_class"] == LAUNCH_OVERHEAD_DOMINATED
