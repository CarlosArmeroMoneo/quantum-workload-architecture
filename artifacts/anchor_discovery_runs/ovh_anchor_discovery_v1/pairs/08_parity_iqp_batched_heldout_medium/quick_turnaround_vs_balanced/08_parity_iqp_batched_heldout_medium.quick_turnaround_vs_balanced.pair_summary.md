# Targeted TTFR Replicate Pair Summary

- Source summary: `/home/ubuntu/quantum-workload-architecture/artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/summary.json`
- Manifest: `/home/ubuntu/quantum-workload-architecture/workloads/manifests/imported/ovh_v2/08_parity_iqp_batched_heldout_medium.yaml`
- Pair: `quick_turnaround` vs `balanced`
- Pair mode: `interleaved`
- Baseline single-shot winner: `quick_turnaround`
- Replicate median winner: `quick_turnaround`
- Winner gap: `5.432 ms`
- Uncertainty band: `74.134 ms`
- Conclusion: `inconclusive_vs_variance`
- Delta definition: `right_minus_left_ttfr_s`
- Delta median: `3.210 ms`
- Delta 95% CI: `[-106.161, 42.107] ms`

## Pair Table

| Template | Baseline TTFR (ms) | Replicate median TTFR (ms) |
| --- | ---: | ---: |
| `quick_turnaround` | 36.355 | 47.102 |
| `balanced` | 40.895 | 52.533 |

## Interleaved Delta Summary

- `per_block_deltas_s` records `right_ttfr_s - left_ttfr_s` for each `A/B` block.
- Delta mean: `-32.027 ms`
- Delta stdev: `113.471 ms`
