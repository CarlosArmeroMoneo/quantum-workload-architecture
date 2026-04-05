# OVH Plan Reuse Prototype Readout

## Scope

This branch is a performance-only prototype for explicit frozen-plan reuse on the canonical OVH host.

What it does:

- adds a first-class reusable `--plan-bundle` flow to `python -m aqs tnep execute`
- keeps planner ranking unchanged
- keeps Gate A and Gate B semantics unchanged
- measures outer end-to-end latency on the real OVH host

What it does not do:

- no planner retune
- no calibration claim
- no speed-factor or GPU-name tuning

## Safety And Provenance

The new bundle path is opt-in and strict in v1.

- A bundle reuses only when the workload manifest path, workload digest, workload ID, system manifest path, system manifest digest, system ID, objective, probe strategy, planner budget, and distributed setting all match exactly.
- Missing bundles are safe misses: the planner runs normally and writes a reusable bundle only after a successful execution.
- Incompatible bundles are rejected explicitly and left untouched.
- Payloads now include:
  - `plan_bundle_path`
  - `plan_bundle_provenance`
  - `driver_timing_json`
  - `driver_total_s`
  - `outer_driver_overhead_s`

Ranking behavior stayed unchanged throughout this branch.

## Measured OVH Results

Canonical benchmark artifact set:

- `artifacts/plan_reuse/ovh_plan_reuse_prototype_v1/ovh_plan_reuse_prototype_v1.json`
- `artifacts/plan_reuse/ovh_plan_reuse_prototype_v1/ovh_plan_reuse_prototype_v1.md`

Measured with:

- host: `configs/systems/ovh_gra9_rtx5000_28.yml`
- execution intent: `require_real`
- probe strategy: `real_if_available`
- planner budget: `balanced`
- measurement repeats: `3`
- benchmark repeats: `3`
- workloads:
  - `workloads/manifests/imported/ovh_v2/01_real_dense_ring6_amplitude.yaml`
  - `workloads/manifests/imported/ovh_v2/06_star_graph_phase_amplitude_heldout_low.yaml`
  - `workloads/manifests/imported/ovh_v2/08_parity_iqp_batched_heldout_medium.yaml`

Observed CLI-wall medians:

- `01_real_dense_ring6_amplitude.yaml`
  - fresh: `2094.026 ms`
  - reused: `1955.080 ms`
  - delta: `138.946 ms` (`6.64%`)
- `06_star_graph_phase_amplitude_heldout_low.yaml`
  - fresh: `2065.271 ms`
  - reused: `2018.693 ms`
  - delta: `46.577 ms` (`2.26%`)
- `08_parity_iqp_batched_heldout_medium.yaml`
  - fresh: `2146.894 ms`
  - reused: `2153.985 ms`
  - delta: `-7.092 ms` (`-0.33%`)

All reused executions were exact bundle hits, and every reused run kept the same `selected_plan.plan_id` as its paired fresh run.

## Interpretation

The plan-bundle prototype is real, safe, and useful, but the benefit is narrower than the earlier fresh-vs-frozen ROI pass suggested.

- The bundle path removes probe and candidate-generation time as intended.
- The outer end-to-end win is positive on the two low-repeat amplitude workloads.
- The benefit is not universal: the medium-repeat control was slightly negative.
- The main reason is visible in the new driver timings:
  - fresh runs pay heavy probe time
  - reused runs pay zero probe time
  - but reused runs absorb much larger `execute_plan_bundle_s` time because cold real-executor initialization shifts into the reused execute phase once the probe is skipped

So the prototype proves:

- explicit plan reuse can safely cut some canonical OVH CLI latency

And it does not prove:

- a broad plan-reuse win across all workloads
- any ranking or calibration improvement

## Decision

No planner-retune branch is justified from this result.

Recommended next branch:

- `stack/25-ovh-executor-overhead-investigation`

Why:

- the current bundle path already removes planning/probe work cleanly
- the remaining limiter is executor-side cold-start / initialization cost, not ranking
- the control workload shows that plan reuse alone is not a universal win

Current best-supported conclusion:

- keep ranking work blocked
- keep Gate A / Gate B semantics unchanged
- continue on a performance-only path focused on executor overhead
