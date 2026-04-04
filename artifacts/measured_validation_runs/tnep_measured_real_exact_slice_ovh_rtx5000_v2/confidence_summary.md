# Validation Confidence Summary

- Source summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v2/summary.json`
- Dataset: `tnep_measured_real_exact_slice_ovh_rtx5000_v2`
- Confidence version: `aqs.validation_confidence.v1`
- Workloads: `9`
- top1_accuracy: `0.777778`
- mean_regret: `0.001111`
- heldout_mean_regret: `0.0`
- top1_within_1ms_rate: `0.888889`
- top1_within_3pct_rate: `0.888889`
- high_confidence_top1_accuracy: `None`
- selection_confidence_counts: `{'low': 4, 'medium': 5, 'high': 0}`

## Workloads

| Workload | Selected | Winner | Runner-up | Winner gap (ms) | top1<=1ms | top1<=3pct | Confidence | Replicate Stability |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| `01_real_dense_ring6_amplitude.yaml` | `quick_turnaround` | `balanced` | `quick_turnaround` | 9.865 | `False` | `False` | `medium` | `None` |
| `02_real_dense_ring6_batched.yaml` | `quick_turnaround` | `quick_turnaround` | `balanced` | 65.476 | `True` | `True` | `medium` | `None` |
| `03_real_ghz3_amplitude.yaml` | `quick_turnaround` | `balanced` | `quick_turnaround` | 0.130 | `True` | `True` | `low` | `None` |
| `04_real_grid_shape6_amplitude.yaml` | `quick_turnaround` | `quick_turnaround` | `balanced` | 0.010 | `True` | `True` | `low` | `None` |
| `05_real_qaoa_ring4_batched.yaml` | `quick_turnaround` | `quick_turnaround` | `balanced` | 0.114 | `True` | `True` | `low` | `None` |
| `06_star_graph_phase_amplitude_heldout_low.yaml` | `quick_turnaround` | `quick_turnaround` | `balanced` | 0.128 | `True` | `True` | `low` | `None` |
| `07_ladder_brickwork_amplitude_heldout_medium.yaml` | `quick_turnaround` | `quick_turnaround` | `balanced` | 5.601 | `True` | `True` | `medium` | `None` |
| `08_parity_iqp_batched_heldout_medium.yaml` | `quick_turnaround` | `quick_turnaround` | `balanced` | 5.046 | `True` | `True` | `medium` | `None` |
| `09_spin_chain_phase_batched_heldout_high.yaml` | `quick_turnaround` | `quick_turnaround` | `balanced` | 4.036 | `True` | `True` | `medium` | `None` |

## Notes

- `top1_within_1ms_rate` and `top1_within_3pct_rate` are additive to `top1_accuracy`; they do not replace it.
- `selection_confidence_counts` bucket workloads as low / medium / high using the current near-tie thresholds `0.001 s` or `3%`.
- Heldout metrics remain descriptive while `heldout_workload_count=5` is below `5`.
