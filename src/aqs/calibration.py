from __future__ import annotations

from typing import Any


SETUP_DOMINATED_THRESHOLD_PCT = 20.0
CONTRACTION_DOMINATED_THRESHOLD_PCT = 60.0
MISCALIBRATION_ERROR_RATIO = 3.0
TINY_WORKLOAD_MAX_QUBITS = 4
TINY_TENSOR_COUNT_MAX = 8

REQUIRED_CLASSIFICATION_FIELDS = (
    "run_id",
    "workload_id",
    "host_id",
    "evidence_tier",
    "n_qubits",
    "tensor_count",
    "setup_share_pct",
    "contract_share_pct",
)

INSUFFICIENT_EVIDENCE = "insufficient_evidence"
MODEL_MISCALIBRATED = "model_miscalibrated"
TINY_WORKLOAD_OVERHEAD_RISK = "tiny_workload_overhead_risk"
LAUNCH_OVERHEAD_DOMINATED = "launch_overhead_dominated"
CONTRACTION_DOMINATED = "contraction_dominated"
MIXED_OR_UNCERTAIN = "mixed_or_uncertain"


def safe_ratio(actual: Any, predicted: Any) -> float | None:
    try:
        actual_value = float(actual)
        predicted_value = float(predicted)
    except (TypeError, ValueError):
        return None
    if predicted_value <= 0.0:
        return None
    return actual_value / predicted_value


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def missing_required_fields(record: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in REQUIRED_CLASSIFICATION_FIELDS:
        if record.get(field) is None:
            missing.append(field)
    return missing


def error_ratios(record: dict[str, Any]) -> dict[str, float | None]:
    ttfr_ratio = _as_float(record.get("ttfr_error_ratio"))
    if ttfr_ratio is None:
        ttfr_ratio = safe_ratio(record.get("actual_ttfr_s"), record.get("predicted_ttfr_s"))

    iter_ratio = _as_float(record.get("iter_error_ratio"))
    if iter_ratio is None:
        iter_ratio = safe_ratio(record.get("actual_iter_ms"), record.get("predicted_iter_ms"))

    return {
        "ttfr_error_ratio": ttfr_ratio,
        "iter_error_ratio": iter_ratio,
    }


def classify_calibration_record(record: dict[str, Any]) -> str:
    if missing_required_fields(record):
        return INSUFFICIENT_EVIDENCE

    ratios = error_ratios(record)
    if any(value is not None and value >= MISCALIBRATION_ERROR_RATIO for value in ratios.values()):
        return MODEL_MISCALIBRATED

    n_qubits = _as_float(record.get("n_qubits"))
    tensor_count = _as_float(record.get("tensor_count"))
    if (n_qubits is not None and n_qubits <= TINY_WORKLOAD_MAX_QUBITS) or (
        tensor_count is not None and tensor_count <= TINY_TENSOR_COUNT_MAX
    ):
        return TINY_WORKLOAD_OVERHEAD_RISK

    setup_share = _as_float(record.get("setup_share_pct"))
    if setup_share is not None and setup_share >= SETUP_DOMINATED_THRESHOLD_PCT:
        return LAUNCH_OVERHEAD_DOMINATED

    contract_share = _as_float(record.get("contract_share_pct"))
    if contract_share is not None and contract_share >= CONTRACTION_DOMINATED_THRESHOLD_PCT:
        return CONTRACTION_DOMINATED

    return MIXED_OR_UNCERTAIN


def annotate_calibration_record(record: dict[str, Any]) -> dict[str, Any]:
    annotated = dict(record)
    for key, value in error_ratios(record).items():
        if annotated.get(key) is None and value is not None:
            annotated[key] = round(value, 6)
    annotated["interpretation_class"] = classify_calibration_record(annotated)
    return annotated
