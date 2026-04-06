# OVH Session Runner Prototype v1

## Scope

This branch extends the persistent-executor path with a thin client and a bundle-first session runner.

What stays unchanged:

- planner ranking behavior
- Gate A semantics
- Gate B semantics
- Gate P semantics
- calibration and confidence claims
- backend truth claims beyond the current single-GPU Qiskit/OpenQASM2 amplitude and `batched_amplitudes` path

Reference policy and plan:

- `docs/reports/ovh_gate_s_policy.md`
- `docs/reports/ovh_session_runner_prototype_plan.md`

Reference baseline:

- `docs/reports/ovh_persistent_executor_prototype_v1.md`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/summary.json`

## Artifact Package

Gate S artifacts live under:

- `artifacts/session_runner/ovh_session_runner_prototype_v1/summary.json`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/summary.md`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/per_request.csv`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/sequence_summary.json`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/sequence_summary.md`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/request_trace.jsonl`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/worker_health.jsonl`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/worker_health_summary.md`

## 1. Did the branch stay in the performance-only lane?

Yes.

- ranking remained unchanged
- Gate A remained unchanged
- Gate B remained unchanged
- Gate P remained unchanged
- no fallback was used in the canonical Gate S benchmark

Gate S is explicitly separate from Gate A, Gate B, and Gate P.

## 2. What did Gate S measure?

Gate S measured client/session packaging overhead above the already-warm persistent worker.

It compared:

- `persistent_warm_cli`
- `session_runner_existing_worker`
- `session_runner_autospawn_temp_worker`

It used the same canonical OVH trio as Gate P:

- `01_real_dense_ring6_amplitude.yaml`
- `06_star_graph_phase_amplitude_heldout_low.yaml`
- `08_parity_iqp_batched_heldout_medium.yaml`

## 3. Did the session runner beat the warm CLI path?

Yes, decisively.

Measured same-workload medians:

| Workload | Persistent Warm CLI ms | Session Runner Existing Worker ms | Existing-Worker Gain ms |
| --- | ---: | ---: | ---: |
| `01_real_dense_ring6_amplitude.yaml` | `659.080` | `52.429` | `606.651` |
| `06_star_graph_phase_amplitude_heldout_low.yaml` | `672.209` | `56.204` | `616.005` |
| `08_parity_iqp_batched_heldout_medium.yaml` | `653.156` | `51.414` | `601.742` |

This comfortably cleared the `> 150 ms` pass bar on all three workloads.

## 4. Did the mixed-session path stay fast and stable?

Yes.

On the mixed `01 -> 06 -> 08 -> 01 -> 06 -> 08` session:

- existing-worker median per-request wall: `54.206 ms`
- existing-worker median 6-request session total: about `376.004 ms`
- autospawn median per-request wall inside the session: about `45.090 ms`
- autospawn still pays a one-time worker-startup tax: about `1137.242 ms`

The important result is that the session runner removes a large remaining chunk of outer CLI/driver tax above the warm worker while preserving the same selected plan identity and correctness.

## 5. Did the worker stay in the same warm-execute regime?

Yes.

Median `worker_execute_s` values stayed in the same broad warm-worker regime:

- `persistent_warm_cli`: about `86.337 ms`
- `session_runner_existing_worker`: about `53.978 ms`
- `session_runner_autospawn_temp_worker`: about `48.220 ms`

Median dispatch plus reply stayed negligible:

- `persistent_warm_cli`: about `0.301 ms`
- `session_runner_existing_worker`: about `0.112 ms`
- `session_runner_autospawn_temp_worker`: about `0.100 ms`

So the session runner did not “win” by changing selection or execution semantics. It reduced the packaging overhead above the worker.

## 6. Did health stay boring enough for a follow-on branch?

Yes.

The health artifact package showed:

- RSS min: `532,783,104` bytes
- RSS max: `795,443,200` bytes
- net RSS delta across the recorded benchmark package: `16,035,840` bytes
- no obvious monotonic memory-leak pattern across the 8-request sessions

Selected plan identity and correctness stayed stable across equivalent bundle paths, and no silent fallback occurred.

## Decision

Gate S passed.

This justifies a follow-on performance-only packaging branch above the worker.

Recommended next branch:

- `stack/29-ovh-embedded-session-client-prototype`

Why:

- the worker and compatibility model are already good enough
- the session runner removed a large additional chunk of outer CLI/driver overhead
- the next remaining tax is now mostly about packaging and invocation ergonomics, not ranking or calibration

What this result does not justify:

- a planner-retune branch
- a calibration claim
- a broader backend claim
