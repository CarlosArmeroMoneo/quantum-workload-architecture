# Targeted TTFR Replicate Pair Summary

- Source summary: `/home/ubuntu/quantum-workload-architecture/artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/summary.json`
- Manifest: `/home/ubuntu/quantum-workload-architecture/workloads/manifests/imported/ovh_v2/01_real_dense_ring6_amplitude.yaml`
- Pair: `quick_turnaround` vs `deep_search`
- Pair mode: `interleaved`
- Baseline single-shot winner: `deep_search`
- Replicate median winner: `quick_turnaround`
- Winner gap: `1.714 ms`
- Uncertainty band: `23.928 ms`
- Conclusion: `inconclusive_vs_variance`
- Delta definition: `right_minus_left_ttfr_s`
- Delta median: `4.076 ms`
- Delta 95% CI: `[-8.043, 39.813] ms`

## Pair Table

| Template | Baseline TTFR (ms) | Replicate median TTFR (ms) |
| --- | ---: | ---: |
| `quick_turnaround` | 46.559 | 57.144 |
| `deep_search` | 37.822 | 58.858 |

## Interleaved Delta Summary

- `per_block_deltas_s` records `right_ttfr_s - left_ttfr_s` for each `A/B` block.
- Delta mean: `15.885 ms`
- Delta stdev: `36.625 ms`
