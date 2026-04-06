# OVH Gate S Policy

## Purpose

Gate S is the session-packaging performance gate for the canonical OVH host.

It answers one narrow question:

Can we materially reduce the remaining outer client/session overhead above the already-warm persistent worker?

## Separation From Other Gates

Gate S is separate from:

- Gate A
- Gate B
- Gate P

Gate A and Gate B remain the ranking and calibration evaluation surfaces.

Gate P remains the persistent-worker performance gate.

Gate S is strictly about client/session packaging overhead above the warm worker.

## What Gate S Is Not

Gate S is not:

- a planner-ranking gate
- a calibration gate
- a confidence-reporting gate
- a backend-capability expansion gate

Passing Gate S does not change:

- planner-ranking claims
- Gate A semantics
- Gate B semantics
- public backend truth claims

## Canonical OVH Gate S Trio

Gate S uses the same canonical OVH trio established by Gate P:

- `workloads/manifests/imported/ovh_v2/01_real_dense_ring6_amplitude.yaml`
- `workloads/manifests/imported/ovh_v2/06_star_graph_phase_amplitude_heldout_low.yaml`
- `workloads/manifests/imported/ovh_v2/08_parity_iqp_batched_heldout_medium.yaml`

## Gate S Modes

Gate S compares these performance-only modes:

- `persistent_warm_cli`
- `session_runner_existing_worker`
- `session_runner_autospawn_temp_worker`

The comparison is intentionally bundle-first and uses strict compatible bundle hits only.

## Safety And Provenance

Gate S keeps the same conservative rules established in stack/24 through stack/27:

- strict bundle compatibility
- explicit provenance
- no silent fallback
- same selected plan identity across equivalent bundle paths
- correctness must remain stable

## Pass Bars

Gate S is considered a success only if the measured artifact package shows:

- no ranking changes
- no Gate A / Gate B changes
- no new backend claims
- `selected_plan_id` unchanged across equivalent bundle paths
- correctness unchanged across equivalent bundle paths
- `session_runner_existing_worker` beats `persistent_warm_cli` by at least `150 ms` median on each canonical workload
- mixed 6-request session median per-request wall stays under `500 ms`
- `worker_execute_s` stays in the warm-worker regime, about `< 120 ms`
- `worker_request_dispatch_s + worker_reply_s < 5 ms`
- no obvious monotonic memory-leak pattern
- no silent fallback

## Artifact Package

The canonical Gate S artifact package lives under:

- `artifacts/session_runner/ovh_session_runner_prototype_v1/summary.json`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/summary.md`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/per_request.csv`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/sequence_summary.json`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/sequence_summary.md`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/request_trace.jsonl`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/worker_health.jsonl`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/worker_health_summary.md`

## Interpretation Guardrail

A Gate S win is a performance-packaging win.

It is not a planner or calibration win.
