# Validation Confidence Summary

- Source summary: `/home/ubuntu/quantum-workload-architecture/artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/summary.json`
- Dataset: `tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2`
- Confidence version: `aqs.validation_confidence.v1`
- Workloads: `9`
- top1_accuracy: `0.333333`
- mean_regret: `0.007459`
- heldout_mean_regret: `0.000254`
- top1_within_1ms_rate: `0.666667`
- top1_within_3pct_rate: `0.666667`
- high_confidence_top1_accuracy: `None`
- selection_confidence_counts: `{'low': 6, 'medium': 3, 'high': 0}`
- stable_selected_miss_count: `0`
- selected_dominated_by_top2_count: `0`
- anchor_candidate_count: `0`
- anchor_candidate_workloads: `[]`

## Workloads

| Workload | Selected | Winner | Runner-up | Winner gap (ms) | top1<=1ms | top1<=3pct | Confidence | Replicate Stability |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| `01_real_dense_ring6_amplitude.yaml` | `quick_turnaround` | `deep_search` | `balanced` | 0.620 | `False` | `False` | `low` | `None` |
| `02_real_dense_ring6_batched.yaml` | `quick_turnaround` | `deep_search` | `balanced` | 0.105 | `False` | `False` | `low` | `None` |
| `03_real_ghz3_amplitude.yaml` | `quick_turnaround` | `balanced` | `deep_search` | 0.039 | `True` | `True` | `low` | `None` |
| `04_real_grid_shape6_amplitude.yaml` | `quick_turnaround` | `deep_search` | `quick_turnaround` | 0.420 | `True` | `True` | `low` | `None` |
| `05_real_qaoa_ring4_batched.yaml` | `quick_turnaround` | `deep_search` | `balanced` | 0.495 | `False` | `False` | `low` | `None` |
| `06_star_graph_phase_amplitude_heldout_low.yaml` | `quick_turnaround` | `deep_search` | `balanced` | 0.230 | `True` | `True` | `low` | `None` |
| `07_ladder_brickwork_amplitude_heldout_medium.yaml` | `quick_turnaround` | `quick_turnaround` | `deep_search` | 5.146 | `True` | `True` | `medium` | `None` |
| `08_parity_iqp_batched_heldout_medium.yaml` | `quick_turnaround` | `quick_turnaround` | `balanced` | 4.540 | `True` | `True` | `medium` | `None` |
| `09_spin_chain_phase_batched_heldout_high.yaml` | `quick_turnaround` | `quick_turnaround` | `balanced` | 5.700 | `True` | `True` | `medium` | `None` |

## Miss-Anchor Triage

| Workload | Selected gap (ms) | Selected vs winner | Selected vs runner-up | Dominated by top2 | Miss anchor | Retune anchor |
| --- | ---: | --- | --- | --- | --- | --- |
| `01_real_dense_ring6_amplitude.yaml` | 8.737 | `None` | `None` | `False` | `low` | `False` |
| `02_real_dense_ring6_batched.yaml` | 54.003 | `None` | `None` | `False` | `low` | `False` |
| `03_real_ghz3_amplitude.yaml` | 0.156 | `None` | `None` | `False` | `low` | `False` |
| `04_real_grid_shape6_amplitude.yaml` | 0.420 | `None` | `None` | `False` | `low` | `False` |
| `05_real_qaoa_ring4_batched.yaml` | 2.964 | `None` | `None` | `False` | `low` | `False` |
| `06_star_graph_phase_amplitude_heldout_low.yaml` | 0.852 | `None` | `None` | `False` | `low` | `False` |
| `07_ladder_brickwork_amplitude_heldout_medium.yaml` | 0.000 | `None` | `None` | `False` | `low` | `False` |
| `08_parity_iqp_batched_heldout_medium.yaml` | 0.000 | `None` | `None` | `False` | `low` | `False` |
| `09_spin_chain_phase_batched_heldout_high.yaml` | 0.000 | `None` | `None` | `False` | `low` | `False` |

## Notes

- `top1_within_1ms_rate` and `top1_within_3pct_rate` are additive to `top1_accuracy`; they do not replace it.
- `selection_confidence_counts` bucket workloads as low / medium / high using the current near-tie thresholds `0.001 s` or `3%`.
- Heldout metrics have reached the documented minimum because `heldout_workload_count=5` meets or exceeds `5`.
- `selected_dominated_by_top2` only turns true when interleaved pairwise evidence shows the selected plan is slower than both the measured winner and the measured runner-up outside the paired uncertainty band.
