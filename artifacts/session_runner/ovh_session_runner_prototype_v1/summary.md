# OVH Session Runner Prototype v1

- Gate P reference: `/home/ubuntu/quantum-workload-architecture/artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/summary.json`
- Gate S request rows: `765`
- No ranking changes: `True`
- No fallback used: `True`

## Same-Workload Medians

| Workload | persistent_warm_cli ms | session_runner_existing_worker ms | session_runner_autospawn_temp_worker ms | existing_worker gain vs CLI ms |
| --- | ---: | ---: | ---: | ---: |
| `01_real_dense_ring6_amplitude.yaml` | `659.080` | `52.429` | `51.832` | `606.651` |
| `06_star_graph_phase_amplitude_heldout_low.yaml` | `672.209` | `56.204` | `51.795` | `616.005` |
| `08_parity_iqp_batched_heldout_medium.yaml` | `653.156` | `51.414` | `45.900` | `601.742` |

## Mixed Session

- Existing worker mixed per-request median ms: `54.206`
- Pass bars met: `True`

## Decision

- Recommendation: `worth productizing further as a lighter client/session packaging path`
