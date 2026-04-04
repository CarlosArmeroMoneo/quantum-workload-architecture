# Targeted TTFR Replicate Pair Summary

- Source summary: `/home/ubuntu/quantum-workload-architecture/artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/summary.json`
- Manifest: `/home/ubuntu/quantum-workload-architecture/workloads/manifests/imported/ovh_v2/06_star_graph_phase_amplitude_heldout_low.yaml`
- Pair: `quick_turnaround` vs `deep_search`
- Pair mode: `interleaved`
- Baseline single-shot winner: `deep_search`
- Replicate median winner: `quick_turnaround`
- Winner gap: `2.932 ms`
- Uncertainty band: `13.783 ms`
- Conclusion: `inconclusive_vs_variance`
- Delta definition: `right_minus_left_ttfr_s`
- Delta median: `2.932 ms`
- Delta 95% CI: `[-6.883, 20.682] ms`

## Pair Table

| Template | Baseline TTFR (ms) | Replicate median TTFR (ms) |
| --- | ---: | ---: |
| `quick_turnaround` | 41.607 | 59.024 |
| `deep_search` | 40.755 | 61.957 |

## Interleaved Delta Summary

- `per_block_deltas_s` records `right_ttfr_s - left_ttfr_s` for each `A/B` block.
- Delta mean: `6.899 ms`
- Delta stdev: `21.096 ms`
