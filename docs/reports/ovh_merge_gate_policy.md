# OVH Merge-Gate Policy

This document defines the merge gates for future tensor-network planner changes on the OVH single-GPU validation host.

## Gate A: Official Benchmark

- Benchmark: the top-2 `require_real` OVH measured-validation slice
- Canonical summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v1/summary.json`
- Canonical confidence summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v1/confidence_summary.md`
- Purpose: deployment-style benchmark for the current planner menu under the official recommendation budget

## Gate B: Calibration Benchmark

- Benchmark: the OVH top-3 measured-validation slice
- Canonical summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v1/summary.json`
- Canonical confidence summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v1/confidence_summary.md`
- Purpose: calibration benchmark over the effective full current single-node candidate menu on this host

## Required Reporting Surface

Every future Gate A or Gate B run must publish both:

- `summary.json`
- `confidence_summary.json` and `confidence_summary.md`

The confidence artifacts must carry these additive metrics alongside the legacy metrics:

- `top1_within_1ms_rate`
- `top1_within_3pct_rate`
- `selection_confidence_counts`
- `high_confidence_top1_accuracy`

The legacy metrics must remain visible:

- `top1_accuracy`
- `mean_regret`
- `heldout_mean_regret`
- `heldout_workload_count`
- `warnings`

## Landing Rule

A future planner behavior change may land only if all of the following are true:

- It materially improves Gate B.
- It does not degrade Gate A.
- It does not worsen the expanded heldout slice once that slice exists.
- Any claimed TTFR gain clears the measured uncertainty band.
- At least one motivating miss is either `high` confidence or `replicate_stable`.

## Interpretation Notes

- Near-best but low-confidence misses are not enough.
- Single-shot misses that flip under replicates are not enough.
- Small low-repeat TTFR gains require stronger proof than before.
- Gate A remains the official deployment-style benchmark.
- Gate B is the calibration benchmark used to judge whether a proposed change is fixing a real planner decision issue rather than reshuffling near-ties.
- Until `heldout_workload_count >= 5`, heldout metrics remain descriptive and should not be treated as a sole merge blocker.
- The current evidence still keeps planner retuning blocked.
