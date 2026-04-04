# Validation Confidence Summary

- Source summary: `/home/ubuntu/quantum-workload-architecture/artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v1/summary.json`
- Dataset: `tnep_measured_real_exact_slice_ovh_rtx5000_top3_v1`
- Confidence version: `aqs.validation_confidence.v1`
- Workloads: `5`
- top1_accuracy: `0.2`
- mean_regret: `0.014848`
- heldout_mean_regret: `0.000369`
- top1_within_1ms_rate: `0.4`
- top1_within_3pct_rate: `0.4`
- high_confidence_top1_accuracy: `None`
- selection_confidence_counts: `{'low': 3, 'medium': 2, 'high': 0}`

## Workloads

| Workload | Selected | Winner | Runner-up | Winner gap (ms) | top1<=1ms | top1<=3pct | Confidence | Replicate Stability |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| `real_dense_ring6_amplitude.yaml` | `quick_turnaround` | `deep_search` | `balanced` | 0.969 | `False` | `False` | `low` | `None` |
| `real_dense_ring6_batched.yaml` | `quick_turnaround` | `balanced` | `deep_search` | 2.809 | `False` | `False` | `medium` | `None` |
| `real_ghz3_amplitude.yaml` | `quick_turnaround` | `balanced` | `deep_search` | 0.476 | `False` | `False` | `low` | `None` |
| `real_grid_shape6_amplitude.yaml` | `quick_turnaround` | `balanced` | `quick_turnaround` | 0.369 | `True` | `True` | `low` | `None` |
| `real_qaoa_ring4_batched.yaml` | `quick_turnaround` | `quick_turnaround` | `balanced` | 4.362 | `True` | `True` | `medium` | `None` |

## Notes

- `top1_within_1ms_rate` and `top1_within_3pct_rate` are additive to `top1_accuracy`; they do not replace it.
- `selection_confidence_counts` bucket workloads as low / medium / high using the current near-tie thresholds `0.001 s` or `3%`.
- Heldout metrics remain descriptive while `heldout_workload_count=1` is below `5`.
