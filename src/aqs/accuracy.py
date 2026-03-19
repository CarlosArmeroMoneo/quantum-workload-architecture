from __future__ import annotations

from typing import Any

import numpy as np

from .utils import canonical_json, sha256_text

ACCURACY_VERSION = "aqs.accuracy.v1"


def _coerce_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value)


def _eval_id(run_id: str, metric_name: str) -> str:
    return "eval_" + sha256_text(canonical_json({"run_id": run_id, "metric_name": metric_name, "version": ACCURACY_VERSION}))[:16]


def build_accuracy_eval(
    run_id: str,
    execution_target: dict[str, Any],
    observed: Any,
    reference: Any,
    *,
    abs_threshold: float = 1.0e-12,
    rel_threshold: float = 1.0e-12,
) -> dict[str, Any]:
    observed_np = _coerce_numpy(observed)
    reference_np = _coerce_numpy(reference)
    diff = observed_np - reference_np
    rows: list[dict[str, Any]] = []

    if execution_target["kind"] == "amplitude":
        abs_err = float(np.max(np.abs(diff)))
        ref_norm = float(np.max(np.abs(reference_np)))
        rel_err = abs_err if ref_norm == 0.0 else float(abs_err / ref_norm)
        for metric_name, metric_value, threshold in (
            ("amplitude_abs_err", abs_err, abs_threshold),
            ("amplitude_rel_err", rel_err, rel_threshold),
        ):
            rows.append(
                {
                    "eval_id": _eval_id(run_id, metric_name),
                    "run_id": run_id,
                    "reference_run_id": None,
                    "metric_name": metric_name,
                    "metric_value": metric_value,
                    "threshold": threshold,
                    "pass": metric_value <= threshold,
                    "evaluation_version": ACCURACY_VERSION,
                }
            )
    elif execution_target["kind"] == "batched_amplitudes":
        abs_err = float(np.max(np.abs(diff)))
        metric_name = "batched_amplitude_max_abs_err"
        rows.append(
            {
                "eval_id": _eval_id(run_id, metric_name),
                "run_id": run_id,
                "reference_run_id": None,
                "metric_name": metric_name,
                "metric_value": abs_err,
                "threshold": abs_threshold,
                "pass": abs_err <= abs_threshold,
                "evaluation_version": ACCURACY_VERSION,
            }
        )
    else:
        raise ValueError(f"Unsupported accuracy target {execution_target['kind']!r}")

    return {
        "run_id": run_id,
        "status": "pass" if all(bool(row["pass"]) for row in rows) else "fail",
        "evaluation_version": ACCURACY_VERSION,
        "primary_metric": rows[0]["metric_name"] if rows else None,
        "rows": rows,
    }


__all__ = ["ACCURACY_VERSION", "build_accuracy_eval"]
