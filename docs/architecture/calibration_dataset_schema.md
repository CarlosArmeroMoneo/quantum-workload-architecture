# Crossover Calibration Dataset Schema

Status: first transparent schema for v0.2 planning.

The v0.2 calibration question is: when do exact tensor-network quantum workloads move from launch/setup dominated to contraction-work dominated, and can Atlas predict that transition from workload and profiler evidence?

This schema is intentionally simple. It is not an ML feature store and it does not promote pending GCP, TPU, QPU, or local laptop evidence.

## Row Fields

| Field | Required | Meaning |
| --- | --- | --- |
| `run_id` | yes | Stable execution run identifier. |
| `workload_id` | yes | Workload manifest identifier or manifest path for pending rows. |
| `host_id` | yes | System manifest name. |
| `gpu_model` | no | Reported GPU model. |
| `evidence_tier` | yes | Tier from the evidence contract or `pending/unaccepted`. |
| `n_qubits` | yes | Qubit count when applicable. |
| `depth` | no | Circuit depth or structural depth proxy. |
| `tensor_count` | yes | Tensor count or structural proxy from the probe. |
| `largest_intermediate` | no | Largest intermediate from the contraction planner/probe. |
| `num_slices` | no | Number of contraction slices. |
| `predicted_ttfr_s` | no | Planner TTFR estimate. |
| `actual_ttfr_s` | no | Measured TTFR. |
| `ttfr_error_ratio` | no | `actual_ttfr_s / predicted_ttfr_s`; omitted when prediction is zero or missing. |
| `predicted_iter_ms` | no | Planner steady-iteration estimate. |
| `actual_iter_ms` | no | Measured steady-iteration time. |
| `iter_error_ratio` | no | `actual_iter_ms / predicted_iter_ms`; omitted when prediction is zero or missing. |
| `setup_share_pct` | yes | Load, conversion, planning, launch, and postprocess share. |
| `contract_share_pct` | yes | Contraction work share. |
| `profiler_kind` | no | `nsys`, `ncu`, `both`, or pending. |
| `interpretation_class` | generated | Output of the transparent classifier. |

## Interpretation Classes

- `launch_overhead_dominated`: setup share is at least 20 percent.
- `contraction_dominated`: contraction share is at least 60 percent.
- `model_miscalibrated`: TTFR or iteration error ratio is at least 3.
- `tiny_workload_overhead_risk`: qubits are at most 4 or tensor count is very small.
- `insufficient_evidence`: required classification fields are missing.
- `mixed_or_uncertain`: none of the above rules fire.

Thresholds live in `src/aqs/calibration.py` as constants so later reports can cite and revise them without hidden changes.
