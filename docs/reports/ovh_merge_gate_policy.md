# OVH Merge-Gate Policy

This document defines the merge gates for future tensor-network planner changes on the OVH single-GPU validation host.

## Gate A: Official Benchmark

- Benchmark: the top-2 `require_real` OVH measured-validation slice
- Canonical artifact: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v1/summary.json`
- Purpose: deployment-style benchmark for the current planner menu under the official recommendation budget

## Gate B: Calibration Benchmark

- Benchmark: the OVH top-3 measured-validation slice
- Canonical artifact: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v1/summary.json`
- Purpose: calibration benchmark over the effective full current single-node candidate menu on this host

## Landing Rule

A future planner change may land only if all of the following are true:

- It materially improves Gate B.
- It does not degrade Gate A.
- It does not worsen the expanded heldout slice once that slice exists.
- Any TTFR gain exceeds the measured uncertainty band once calibration-only TTFR replicates are available.

## Interpretation Notes

- Gate A remains the official benchmark for deployment-style planner behavior.
- Gate B is the diagnostic benchmark used to decide whether a change is fixing calibration or merely reshuffling near-ties.
- Until `heldout_workload_count >= 5`, heldout metrics are descriptive and should not be treated as a sole merge blocker.
- Host-specific evidence should prefer manifest-level calibration controls over GPU-name string special cases wherever possible.
