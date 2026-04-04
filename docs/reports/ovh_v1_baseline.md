# OVH V1 Baseline

This report freezes the current OVH real-host measured-validation result as the `v1` baseline. It is descriptive only and does not claim the planner is calibrated.

## Baseline Artifacts

- Official top-2 `require_real` summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v1/summary.json`
- Official top-2 architecture aggregation: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v1/validation_arch.json`
- Full-menu top-3 diagnostic summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v1/summary.json`

## Frozen Baseline Claims

- The official `require_real` OVH slice ran cleanly on `ovh_gra9_rtx5000_28`.
- Strict top-1 is modest: the current baseline `top1_accuracy` is `0.4`.
- Mean regret is low: the current baseline `mean_regret` is `0.002755`.
- The current heldout signal is too thin to drive merge decisions by itself: `heldout_workload_count=1`.
- The top-3 diagnostic, which is effectively the full current single-node candidate menu on this host, found only one small third-rank winner:
  - `real_dense_ring6_amplitude.yaml`
  - best top-2: `balanced` at `0.048198861 s`
  - full-menu winner: `deep_search` at `0.04722993 s`
  - hidden third-template edge: `0.000969 s` or about `2.052%`
- The current selected-run architecture aggregation is dominated by `planner_roi`.

## Baseline Interpretation

- The current OVH result looks more like a calibration / confidence / overhead-modeling problem than a missing major candidate family.
- The top-3 pass does not show evidence that the official top-2 benchmark is hiding a large third-template winner on this host.
- The baseline is therefore suitable as the frozen `v1` real-host reference for future calibration diagnostics and merge gates.
