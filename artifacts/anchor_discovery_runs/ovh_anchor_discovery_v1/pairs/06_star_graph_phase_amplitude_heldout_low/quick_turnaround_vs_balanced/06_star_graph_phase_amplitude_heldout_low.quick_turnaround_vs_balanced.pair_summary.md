# Targeted TTFR Replicate Pair Summary

- Source summary: `/home/ubuntu/quantum-workload-architecture/artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/summary.json`
- Manifest: `/home/ubuntu/quantum-workload-architecture/workloads/manifests/imported/ovh_v2/06_star_graph_phase_amplitude_heldout_low.yaml`
- Pair: `quick_turnaround` vs `balanced`
- Pair mode: `interleaved`
- Baseline single-shot winner: `balanced`
- Replicate median winner: `quick_turnaround`
- Winner gap: `0.700 ms`
- Uncertainty band: `15.470 ms`
- Conclusion: `inconclusive_vs_variance`
- Delta definition: `right_minus_left_ttfr_s`
- Delta median: `1.690 ms`
- Delta 95% CI: `[-10.879, 20.060] ms`

## Pair Table

| Template | Baseline TTFR (ms) | Replicate median TTFR (ms) |
| --- | ---: | ---: |
| `quick_turnaround` | 41.607 | 60.488 |
| `balanced` | 40.985 | 61.188 |

## Interleaved Delta Summary

- `per_block_deltas_s` records `right_ttfr_s - left_ttfr_s` for each `A/B` block.
- Delta mean: `4.591 ms`
- Delta stdev: `23.678 ms`
