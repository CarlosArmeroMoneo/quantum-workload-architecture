# OVH Gate P Policy

## Purpose

Gate P is the persistent-execution performance gate for the canonical OVH host.

It exists to answer a narrow runtime-architecture question:

- can strict, opt-in persistent execution reduce end-to-end latency by amortizing real-stack bootstrap across multiple compatible requests?

Gate P is separate from Gate A and Gate B.

## What Gate P Is Not

Gate P is not:

- a planner-ranking benchmark
- a calibration benchmark
- a confidence/anchor benchmark
- a replacement for Gate A or Gate B

Passing Gate P does not change any ranking claim.
Passing Gate P does not change Gate A or Gate B semantics.

## Canonical OVH Gate P Trio

Gate P uses exactly these current OVH workloads:

- `workloads/manifests/imported/ovh_v2/01_real_dense_ring6_amplitude.yaml`
- `workloads/manifests/imported/ovh_v2/06_star_graph_phase_amplitude_heldout_low.yaml`
- `workloads/manifests/imported/ovh_v2/08_parity_iqp_batched_heldout_medium.yaml`

These are intentionally reused from the stack/24 and stack/26 evidence chain so the persistent-worker result can be compared against the frozen one-shot bundle baseline without changing the benchmark question.

## Mode Definitions

Gate P compares these performance-only modes:

- `one_shot_bundle`
- `persistent_cold`
- `persistent_warm`

The supporting benchmark harness also records `fresh` and `plan_json` runs so the cost split stays interpretable, but the core Gate P comparison is still:

- one-shot bundle hit
- first request in a fresh persistent session
- warm request in an already-started persistent session

## Success Criteria

Gate P is judged on outer end-to-end latency and strict safety, not on TTFR ranking claims.

Current conservative pass bar:

- warm persistent gain > `1.0 s` versus `one_shot_bundle` on each OVH workload
- persistent cold session total < one-shot bundle total on each OVH workload
- warm `worker_execute_s < 120 ms`
- `worker_request_dispatch_s + worker_reply_s < 5 ms`
- `import_real_stack_s` remains effectively zero after worker startup
- `selected_plan_id` stays unchanged across equivalent fresh / override / one-shot bundle / persistent bundle paths
- correctness behavior stays unchanged

## Safety Rules

- persistent execution remains opt-in
- compatibility checks stay strict
- incompatible bundle or request reuse must fail clearly
- one-shot fallback is explicit-only and must carry clear provenance when used
- local Unix socket only in this prototype
- no ranking or calibration conclusion may be derived from Gate P alone

## Reference Chain

- one-shot reusable-bundle baseline:
  - `docs/reports/ovh_plan_reuse_prototype_v1_frozen.md`
- persistent-executor investigation baseline:
  - `docs/reports/ovh_persistent_executor_investigation_v1.md`
- current prototype plan:
  - `docs/reports/ovh_persistent_executor_prototype_plan.md`
