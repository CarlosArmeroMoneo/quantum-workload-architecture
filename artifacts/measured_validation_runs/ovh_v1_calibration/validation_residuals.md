# Validation Residual Export

- Candidate rows: `25`
- Datasets: `['tnep_measured_real_exact_slice_ovh_rtx5000_top3_v1', 'tnep_measured_real_exact_slice_ovh_rtx5000_v1']`

## Interpretation

## `tnep_measured_real_exact_slice_ovh_rtx5000_top3_v1`

- Wrong-pick selected rows: `4` of `5`
- Are misses concentrated at repeat counts 1-4? `3` yes vs `1` above 4
- Are misses mostly balanced vs deep_search? `{'quick_turnaround -> deep_search': 1, 'quick_turnaround -> balanced': 3}`
- Is the dominant error in planning/setup or steady contraction? `planning/setup dominates`
- Are wrong picks near-ties or clear misses? `1` near-ties vs `3` clear misses
- Verified third-rank winners: `1` on `['real_dense_ring6_amplitude.yaml']`
- Interpretation note: wrong-pick rows in a top-3 diagnostic are not automatically third-rank winners; a large miss can still be a rank-2 win.

| Workload | Repeat | Selected | Oracle | Regret (ms) | Primary Architecture Family |
| --- | ---: | --- | --- | ---: | --- |
| `real_dense_ring6_amplitude.yaml` | 2 | `quick_turnaround` | `deep_search` | 10.677 | `planner_roi` |
| `real_dense_ring6_batched.yaml` | 12 | `quick_turnaround` | `balanced` | 60.910 | `planner_roi` |
| `real_ghz3_amplitude.yaml` | 1 | `quick_turnaround` | `balanced` | 2.286 | `planner_roi` |
| `real_grid_shape6_amplitude.yaml` | 3 | `quick_turnaround` | `balanced` | 0.369 | `planner_roi` |

## `tnep_measured_real_exact_slice_ovh_rtx5000_v1`

- Wrong-pick selected rows: `3` of `5`
- Are misses concentrated at repeat counts 1-4? `3` yes vs `0` above 4
- Are misses mostly balanced vs deep_search? `{'quick_turnaround -> balanced': 3}`
- Is the dominant error in planning/setup or steady contraction? `planning/setup dominates`
- Are wrong picks near-ties or clear misses? `1` near-ties vs `2` clear misses
- Verified third-rank winners: `0` on `[]`
- Interpretation note: wrong-pick rows in a top-3 diagnostic are not automatically third-rank winners; a large miss can still be a rank-2 win.
- Selected-run aggregate from validation_arch: `['planner_roi', 'reuse_cache', 'launch_overhead']`

| Workload | Repeat | Selected | Oracle | Regret (ms) | Primary Architecture Family |
| --- | ---: | --- | --- | ---: | --- |
| `real_dense_ring6_amplitude.yaml` | 2 | `quick_turnaround` | `balanced` | 9.504 | `planner_roi` |
| `real_ghz3_amplitude.yaml` | 1 | `quick_turnaround` | `balanced` | 0.748 | `planner_roi` |
| `real_qaoa_ring4_batched.yaml` | 4 | `quick_turnaround` | `balanced` | 3.522 | `planner_roi` |

