# Targeted TTFR Replicate Pair Summary

- Source summary: `/home/ubuntu/quantum-workload-architecture/artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/summary.json`
- Manifest: `/home/ubuntu/quantum-workload-architecture/workloads/manifests/imported/ovh_v2/02_real_dense_ring6_batched.yaml`
- Pair: `quick_turnaround` vs `balanced`
- Pair mode: `interleaved`
- Baseline single-shot winner: `balanced`
- Replicate median winner: `quick_turnaround`
- Winner gap: `4.293 ms`
- Uncertainty band: `60.931 ms`
- Conclusion: `inconclusive_vs_variance`
- Delta definition: `right_minus_left_ttfr_s`
- Delta median: `6.419 ms`
- Delta 95% CI: `[-84.425, 37.438] ms`

## Pair Table

| Template | Baseline TTFR (ms) | Replicate median TTFR (ms) |
| --- | ---: | ---: |
| `quick_turnaround` | 96.255 | 56.313 |
| `balanced` | 42.357 | 60.605 |

## Interleaved Delta Summary

- `per_block_deltas_s` records `right_ttfr_s - left_ttfr_s` for each `A/B` block.
- Delta mean: `-23.494 ms`
- Delta stdev: `93.262 ms`
