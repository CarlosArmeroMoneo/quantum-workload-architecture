# Targeted TTFR Replicate Pair Summary

- Source summary: `/home/ubuntu/quantum-workload-architecture/artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v2/summary.json`
- Manifest: `/home/ubuntu/quantum-workload-architecture/workloads/manifests/imported/ovh_v2/01_real_dense_ring6_amplitude.yaml`
- Pair: `quick_turnaround` vs `quick_turnaround`
- Pair mode: `interleaved`
- Baseline single-shot winner: `quick_turnaround`
- Replicate median winner: `quick_turnaround`
- Winner gap: `0.790 ms`
- Uncertainty band: `11.687 ms`
- Conclusion: `inconclusive_vs_variance`
- Delta definition: `right_minus_left_ttfr_s`
- Delta median: `-2.561 ms`
- Delta 95% CI: `[-8.484, 14.891] ms`

## Pair Table

| Template | Baseline TTFR (ms) | Replicate median TTFR (ms) |
| --- | ---: | ---: |
| `quick_turnaround` | 48.753 | 60.190 |
| `quick_turnaround` | 48.753 | 59.401 |

## Interleaved Delta Summary

- `per_block_deltas_s` records `right_ttfr_s - left_ttfr_s` for each `A/B` block.
- Delta mean: `3.203 ms`
- Delta stdev: `17.889 ms`
