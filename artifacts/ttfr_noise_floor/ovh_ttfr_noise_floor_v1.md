# OVH TTFR Noise Floor v1

- Pair summaries: `2`
- Max null-pair CI half-width: `48.093 ms`
- Median null-pair CI half-width: `29.89 ms`
- Interpretation: The null-pair uncertainty band is on the order of the 1-5 ms winner gaps we care about, so exact TTFR top-1 in that regime should stay descriptive-only on this host.

## Null Pairs

| Workload | Pair | Delta mean (ms) | Delta median (ms) | Delta stdev (ms) | CI half-width (ms) | Left median (ms) | Right median (ms) | Conclusion |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `01_real_dense_ring6_amplitude.yaml` | `quick_turnaround vs quick_turnaround` | 3.203 | -2.561 | 17.889 | 11.687 | 60.190 | 59.401 | `inconclusive_vs_variance` |
| `08_parity_iqp_batched_heldout_medium.yaml` | `quick_turnaround vs quick_turnaround` | -23.231 | 1.280 | 73.611 | 48.093 | 62.208 | 65.618 | `inconclusive_vs_variance` |

## Paths

- `/home/ubuntu/quantum-workload-architecture/artifacts/ttfr_noise_floor/ovh_ttfr_noise_floor_v1/pairs/01_real_dense_ring6_amplitude/quick_turnaround_null_pair/01_real_dense_ring6_amplitude.quick_turnaround_vs_quick_turnaround.pair_summary.json`
- `/home/ubuntu/quantum-workload-architecture/artifacts/ttfr_noise_floor/ovh_ttfr_noise_floor_v1/pairs/08_parity_iqp_batched_heldout_medium/quick_turnaround_null_pair/08_parity_iqp_batched_heldout_medium.quick_turnaround_vs_quick_turnaround.pair_summary.json`
