# OVH Embedded Session Client v1

## Scope

This branch packages the proven OVH fast path into a reusable local Python API above the persistent worker.

What stays unchanged:

- planner ranking behavior
- Gate A semantics
- Gate B semantics
- Gate P semantics
- Gate S semantics
- calibration and confidence claims
- backend truth claims beyond the current single-GPU Qiskit/OpenQASM2 amplitude and `batched_amplitudes` path

Frozen predecessor baseline:

- Gate S branch/tag: `ovh-v3-session-runner-fast-path`
- Gate S summary: `artifacts/session_runner/ovh_session_runner_prototype_v1/summary.json`

## Artifact Package

Embedded-session artifacts live under:

- `artifacts/embedded_session/ovh_embedded_session_client_v1/summary.json`
- `artifacts/embedded_session/ovh_embedded_session_client_v1/summary.md`
- `artifacts/embedded_session/ovh_embedded_session_client_v1/per_request.csv`
- `artifacts/embedded_session/ovh_embedded_session_client_v1/sequence_summary.json`
- `artifacts/embedded_session/ovh_embedded_session_client_v1/sequence_summary.md`
- `artifacts/embedded_session/ovh_embedded_session_client_v1/request_trace.jsonl`
- `artifacts/embedded_session/ovh_embedded_session_client_v1/worker_health.jsonl`
- `artifacts/embedded_session/ovh_embedded_session_client_v1/worker_health_summary.md`

## 1. Did the branch stay performance-only?

Yes.

- ranking remained unchanged
- Gate A remained unchanged
- Gate B remained unchanged
- Gate P remained unchanged
- Gate S remained unchanged
- no fallback was used in the canonical benchmark package

This is a local performance/API result, not a calibration or ranking result.

## 2. How did the embedded client compare on the canonical OVH trio?

Same-workload medians:

| Workload | Persistent Warm CLI ms | Session Runner Existing Worker ms | Embedded Existing Worker ms | Embedded Autospawn ms |
| --- | ---: | ---: | ---: | ---: |
| `01_real_dense_ring6_amplitude.yaml` | `651.811` | `53.187` | `53.937` | `47.364` |
| `06_star_graph_phase_amplitude_heldout_low.yaml` | `659.576` | `56.234` | `57.035` | `51.529` |
| `08_parity_iqp_batched_heldout_medium.yaml` | `653.635` | `51.565` | `51.492` | `49.892` |

Interpretation:

- the embedded existing-worker path stayed inside the Gate S performance envelope on all three workloads
- it was within the allowed `10-15%` band relative to the frozen session-runner path
- the autospawn variant stayed in the same fast regime and was slightly lower in this measured package

## 3. Did mixed sessions stay fast and boring?

Yes.

On the mixed `01 -> 06 -> 08 -> 01 -> 06 -> 08` session:

- embedded existing-worker median per-request wall: `55.606 ms`
- embedded autospawn median per-request wall: `49.235 ms`

That keeps the embedded client in the same practical regime as Gate S and comfortably under the `60 ms` target.

## 4. Did worker-side behavior stay stable?

Yes.

- median `worker_execute_s`: `0.051888 s`
- dispatch plus reply stayed below the `5 ms` bar
- no selected-plan drift appeared across equivalent bundle paths
- no correctness drift appeared across equivalent bundle paths
- no silent fallback occurred

Health stayed boring enough for a packaging branch:

- RSS min: `532,733,952` bytes
- RSS max: `795,631,616` bytes
- RSS delta: `16,236,544` bytes
- monotonic RSS increase: `False`

## Decision

This branch succeeded.

Why:

- it turned the OVH fast path into a reusable local Python API
- it preserved the same selected-plan identity and correctness behavior
- it stayed in the Gate S latency envelope without broadening claims

Recommended next branch:

- `stack/30-second-platform-validation`

Reason:

- the OVH local packaging path is now largely solved
- the next high-value question is portability of the runtime/session architecture win, not more OVH-local latency chasing
