# Targeted TTFR Replicate Pair Summary

- Source summary: `/home/ubuntu/quantum-workload-architecture/artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/summary.json`
- Manifest: `/home/ubuntu/quantum-workload-architecture/workloads/manifests/imported/ovh_v2/01_real_dense_ring6_amplitude.yaml`
- Pair: `balanced` vs `deep_search`
- Pair mode: `interleaved`
- Baseline single-shot winner: `deep_search`
- Replicate median winner: `balanced`
- Winner gap: `2.649 ms`
- Uncertainty band: `14.468 ms`
- Conclusion: `inconclusive_vs_variance`
- Delta definition: `right_minus_left_ttfr_s`
- Delta median: `5.100 ms`
- Delta 95% CI: `[-6.091, 22.845] ms`

## Pair Table

| Template | Baseline TTFR (ms) | Replicate median TTFR (ms) |
| --- | ---: | ---: |
| `balanced` | 38.443 | 55.805 |
| `deep_search` | 37.822 | 58.454 |

## Interleaved Delta Summary

- `per_block_deltas_s` records `right_ttfr_s - left_ttfr_s` for each `A/B` block.
- Delta mean: `8.377 ms`
- Delta stdev: `22.145 ms`
