# Validation Confidence Summary

- Source summary: `/home/ubuntu/quantum-workload-architecture/artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v1/summary.json`
- Dataset: `tnep_measured_real_exact_slice_ovh_rtx5000_v1`
- Confidence version: `aqs.validation_confidence.v1`
- Workloads: `5`
- top1_accuracy: `0.4`
- mean_regret: `0.002755`
- heldout_mean_regret: `0.0`
- top1_within_1ms_rate: `0.6`
- top1_within_3pct_rate: `0.4`
- high_confidence_top1_accuracy: `None`
- selection_confidence_counts: `{'low': 2, 'medium': 3, 'high': 0}`

## Workloads

| Workload | Selected | Winner | Runner-up | Winner gap (ms) | top1<=1ms | top1<=3pct | Confidence | Replicate Stability |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| `real_dense_ring6_amplitude.yaml` | `quick_turnaround` | `balanced` | `quick_turnaround` | 9.504 | `False` | `False` | `medium` | `winner_flipped_vs_single_shot` |
| `real_dense_ring6_batched.yaml` | `quick_turnaround` | `quick_turnaround` | `balanced` | 67.639 | `True` | `True` | `medium` | `None` |
| `real_ghz3_amplitude.yaml` | `quick_turnaround` | `balanced` | `quick_turnaround` | 0.748 | `True` | `False` | `low` | `None` |
| `real_grid_shape6_amplitude.yaml` | `quick_turnaround` | `quick_turnaround` | `balanced` | 0.506 | `True` | `True` | `low` | `None` |
| `real_qaoa_ring4_batched.yaml` | `quick_turnaround` | `balanced` | `quick_turnaround` | 3.522 | `False` | `False` | `medium` | `None` |

## Notes

- `top1_within_1ms_rate` and `top1_within_3pct_rate` are additive to `top1_accuracy`; they do not replace it.
- `selection_confidence_counts` bucket workloads as low / medium / high using the current near-tie thresholds `0.001 s` or `3%`.
- Heldout metrics remain descriptive while `heldout_workload_count=1` is below `5`.
