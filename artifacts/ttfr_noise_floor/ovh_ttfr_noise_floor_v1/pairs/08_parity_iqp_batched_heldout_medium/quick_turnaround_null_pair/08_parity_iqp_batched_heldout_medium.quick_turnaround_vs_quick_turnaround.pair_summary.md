# Targeted TTFR Replicate Pair Summary

- Source summary: `/home/ubuntu/quantum-workload-architecture/artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v2/summary.json`
- Manifest: `/home/ubuntu/quantum-workload-architecture/workloads/manifests/imported/ovh_v2/08_parity_iqp_batched_heldout_medium.yaml`
- Pair: `quick_turnaround` vs `quick_turnaround`
- Pair mode: `interleaved`
- Baseline single-shot winner: `quick_turnaround`
- Replicate median winner: `quick_turnaround`
- Winner gap: `3.410 ms`
- Uncertainty band: `48.093 ms`
- Conclusion: `inconclusive_vs_variance`
- Delta definition: `right_minus_left_ttfr_s`
- Delta median: `1.280 ms`
- Delta 95% CI: `[-71.323, 24.862] ms`

## Pair Table

| Template | Baseline TTFR (ms) | Replicate median TTFR (ms) |
| --- | ---: | ---: |
| `quick_turnaround` | 36.997 | 62.208 |
| `quick_turnaround` | 36.997 | 65.618 |

## Interleaved Delta Summary

- `per_block_deltas_s` records `right_ttfr_s - left_ttfr_s` for each `A/B` block.
- Delta mean: `-23.231 ms`
- Delta stdev: `73.611 ms`
