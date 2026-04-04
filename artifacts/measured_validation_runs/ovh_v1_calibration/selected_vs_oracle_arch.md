# Selected vs Oracle Architecture Comparison

- Source summary: `/home/ubuntu/quantum-workload-architecture/artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v1/summary.json`
- Dataset: `tnep_measured_real_exact_slice_ovh_rtx5000_v1`
- Workloads: `5`
- Primary family shifts: `0`
- Oracle lowers `planner_roi`: `0`

## Recurring Patterns

Selected primary families:
- `planner_roi`: 5

Oracle primary families:
- `planner_roi`: 5

Top per-workload comparison patterns:
- `selected and oracle analyses are materially similar`: 2
- `oracle lowers launch_overhead by 0.294; oracle TTFR lower by 9.504 ms`: 1
- `oracle lowers launch_overhead by 0.004; oracle TTFR lower by 0.748 ms`: 1
- `oracle TTFR lower by 3.522 ms`: 1

## Workloads

| Workload | Repeat | Selected -> Oracle | Selected Primary | Oracle Primary | Regret (ms) | Summary |
| --- | ---: | --- | --- | --- | ---: | --- |
| `real_dense_ring6_amplitude.yaml` | 2 | `quick_turnaround` -> `balanced` | `planner_roi` | `planner_roi` | 9.504 | oracle lowers launch_overhead by 0.294; oracle TTFR lower by 9.504 ms |
| `real_dense_ring6_batched.yaml` | 12 | `quick_turnaround` -> `quick_turnaround` | `planner_roi` | `planner_roi` | 0.000 | selected and oracle analyses are materially similar |
| `real_ghz3_amplitude.yaml` | 1 | `quick_turnaround` -> `balanced` | `planner_roi` | `planner_roi` | 0.748 | oracle lowers launch_overhead by 0.004; oracle TTFR lower by 0.748 ms |
| `real_grid_shape6_amplitude.yaml` | 3 | `quick_turnaround` -> `quick_turnaround` | `planner_roi` | `planner_roi` | 0.000 | selected and oracle analyses are materially similar |
| `real_qaoa_ring4_batched.yaml` | 4 | `quick_turnaround` -> `balanced` | `planner_roi` | `planner_roi` | 3.522 | oracle TTFR lower by 3.522 ms |
