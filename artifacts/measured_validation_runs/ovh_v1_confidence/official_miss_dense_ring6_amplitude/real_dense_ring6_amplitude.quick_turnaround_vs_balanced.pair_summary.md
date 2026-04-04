# Targeted TTFR Replicate Pair Summary

- Source summary: `/home/ubuntu/quantum-workload-architecture/artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v1/summary.json`
- Manifest: `/home/ubuntu/quantum-workload-architecture/workloads/manifests/imported/real_dense_ring6_amplitude.yaml`
- Pair: `quick_turnaround` vs `balanced`
- Baseline single-shot winner: `balanced`
- Replicate median winner: `quick_turnaround`
- Winner gap: `7.456 ms`
- Uncertainty band: `3.466 ms`
- Conclusion: `winner_flipped_vs_single_shot`

## Pair Table

| Template | Baseline TTFR (ms) | Replicate median TTFR (ms) |
| --- | ---: | ---: |
| `quick_turnaround` | 49.815 | 38.457 |
| `balanced` | 40.311 | 45.913 |
