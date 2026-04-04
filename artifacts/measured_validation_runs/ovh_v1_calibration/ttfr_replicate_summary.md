# TTFR Replicate Summary

- Payload count: `6`
- Comparison count: `3`
- Interpretation: median pairwise deltas are compared against the larger observed TTFR standard deviation from the two plans under comparison.

## Per-Plan Medians

| Workload | Repeat | Template | Single TTFR (ms) | Median TTFR (ms) | TTFR stdev (ms) | Planner median (ms) | Setup median (ms) |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| `wkl_19ca61869000401d` | 4 | `balanced` | 304.259 | 40.774 | 98.498 | 33.327 | 3.467 |
| `wkl_19ca61869000401d` | 4 | `quick_turnaround` | 373.437 | 39.286 | 124.301 | 33.219 | 3.350 |
| `wkl_5361a0b920fc4e05` | 1 | `balanced` | 24.825 | 12.277 | 4.746 | 8.078 | 1.990 |
| `wkl_5361a0b920fc4e05` | 1 | `quick_turnaround` | 30.259 | 12.371 | 6.756 | 8.203 | 1.950 |
| `wkl_888bce118ad39b04` | 2 | `balanced` | 47.580 | 38.119 | 21.723 | 32.054 | 3.335 |
| `wkl_888bce118ad39b04` | 2 | `deep_search` | 47.128 | 38.300 | 22.160 | 32.289 | 3.319 |

## Pairwise Comparison

| Workload | Left | Right | Median delta (ms) | Uncertainty band (ms) | Ratio | Verdict |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `wkl_19ca61869000401d` | `balanced` | `quick_turnaround` | 1.488 | 124.301 | 0.012 | `inconclusive_vs_variance` |
| `wkl_5361a0b920fc4e05` | `balanced` | `quick_turnaround` | -0.094 | 6.756 | 0.014 | `inconclusive_vs_variance` |
| `wkl_888bce118ad39b04` | `balanced` | `deep_search` | -0.181 | 22.160 | 0.008 | `inconclusive_vs_variance` |
