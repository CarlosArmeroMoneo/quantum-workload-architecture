# Targeted TTFR Replicate Pair Summary

- Source summary: `/home/ubuntu/quantum-workload-architecture/artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/summary.json`
- Manifest: `/home/ubuntu/quantum-workload-architecture/workloads/manifests/imported/ovh_v2/02_real_dense_ring6_batched.yaml`
- Pair: `quick_turnaround` vs `deep_search`
- Pair mode: `interleaved`
- Baseline single-shot winner: `deep_search`
- Replicate median winner: `quick_turnaround`
- Winner gap: `1.536 ms`
- Uncertainty band: `55.272 ms`
- Conclusion: `inconclusive_vs_variance`
- Delta definition: `right_minus_left_ttfr_s`
- Delta median: `6.692 ms`
- Delta 95% CI: `[-74.398, 36.146] ms`

## Pair Table

| Template | Baseline TTFR (ms) | Replicate median TTFR (ms) |
| --- | ---: | ---: |
| `quick_turnaround` | 96.255 | 73.211 |
| `deep_search` | 42.252 | 74.747 |

## Interleaved Delta Summary

- `per_block_deltas_s` records `right_ttfr_s - left_ttfr_s` for each `A/B` block.
- Delta mean: `-19.126 ms`
- Delta stdev: `84.600 ms`
