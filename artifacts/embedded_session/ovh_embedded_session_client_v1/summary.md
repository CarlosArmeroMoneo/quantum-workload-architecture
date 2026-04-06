# OVH Embedded Session Client v1

- Gate S reference: `/home/ubuntu/quantum-workload-architecture/artifacts/session_runner/ovh_session_runner_prototype_v1/summary.json`
- Request rows: `1020`
- No ranking changes: `True`
- No fallback used: `True`

## Same-Workload Medians

| Workload | persistent_warm_cli ms | session_runner_existing_worker ms | embedded_session_existing_worker ms | embedded_session_autospawn_temp_worker ms |
| --- | ---: | ---: | ---: | ---: |
| `01_real_dense_ring6_amplitude.yaml` | `651.811` | `53.187` | `53.937` | `47.364` |
| `06_star_graph_phase_amplitude_heldout_low.yaml` | `659.576` | `56.234` | `57.035` | `51.529` |
| `08_parity_iqp_batched_heldout_medium.yaml` | `653.635` | `51.565` | `51.492` | `49.892` |

## Mixed Session

- Existing worker mixed per-request median ms: `55.606`
- Autospawn mixed per-request median ms: `49.235`
- Pass bars met: `True`

## Decision

- Recommendation: `embedded session client is worth productizing as the reusable local fast path; pivot next to second-platform validation`
