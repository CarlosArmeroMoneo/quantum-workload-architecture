# OVH Persistent Executor Investigation v1

## Scope

This branch keeps planner ranking unchanged and treats [ovh_plan_reuse_prototype_v1_frozen.md](/home/ubuntu/quantum-workload-architecture/docs/reports/ovh_plan_reuse_prototype_v1_frozen.md) as the frozen predecessor baseline.

What changed in this milestone:

- a single opt-in persistent real-execution worker was added
- strict bundle/request compatibility stayed in place
- the worker imports and initializes the real stack once per session
- session-aware timing/provenance were added so one-shot and persistent bundle hits can be compared directly

This is a performance-only result. It is not a calibration or ranking result.

## Reference Artifacts

- Persistent benchmark summary:
  - [ovh_persistent_executor_investigation_v1.json](/home/ubuntu/quantum-workload-architecture/artifacts/persistent_executor/ovh_persistent_executor_investigation_v1/ovh_persistent_executor_investigation_v1.json)
  - [ovh_persistent_executor_investigation_v1.md](/home/ubuntu/quantum-workload-architecture/artifacts/persistent_executor/ovh_persistent_executor_investigation_v1/ovh_persistent_executor_investigation_v1.md)
- Frozen predecessor baseline:
  - [ovh_plan_reuse_prototype_v1_frozen.md](/home/ubuntu/quantum-workload-architecture/docs/reports/ovh_plan_reuse_prototype_v1_frozen.md)
- Prior one-shot overhead readout:
  - [ovh_executor_overhead_investigation_v1.md](/home/ubuntu/quantum-workload-architecture/docs/reports/ovh_executor_overhead_investigation_v1.md)

## 1. Does persistent execution eliminate most of the one-shot bundle-hit penalty?

Yes, on this OVH host it eliminates the dominant per-request bootstrap penalty.

Warm persistent bundle hits beat one-shot bundle hits by:

- `01_real_dense_ring6_amplitude.yaml`: `1421.073 ms`
- `06_star_graph_phase_amplitude_heldout_low.yaml`: `1467.793 ms`
- `08_parity_iqp_batched_heldout_medium.yaml`: `1398.725 ms`

Even the first cold request in a brand-new persistent session still beat the one-shot bundle-hit baseline once worker startup was included:

- `01`: `217.177 ms` better in session-total wall
- `06`: `224.613 ms` better in session-total wall
- `08`: `171.419 ms` better in session-total wall

That means the session model is not just moving cost around inside the same request. It is amortizing a real per-process tax.

## 2. How much does `import_real_stack_s` shrink on warm requests?

It collapses from about `0.89-0.93 s` on one-shot bundle hits to `0.0 s` on both persistent cold and persistent warm requests.

Measured one-shot medians:

- `01`: `892.559 ms`
- `06`: `932.414 ms`
- `08`: `895.629 ms`

Measured persistent medians:

- cold request: `0.0 ms` on all three workloads
- warm request: `0.0 ms` on all three workloads

The bootstrap tax did not disappear. It moved into one session-level startup cost:

- `01` worker startup: `1086.793 ms`
- `06` worker startup: `1097.707 ms`
- `08` worker startup: `1062.419 ms`

That is the exact behavior this branch was meant to test.

## 3. Where does the remaining fixed cost sit?

After session startup is amortized, the remaining cost is mostly split between:

- outer CLI / driver overhead outside the worker: about `154-186 ms`
- worker-side execute time: about `80-90 ms`

Warm persistent medians:

| Workload | Outer Overhead ms | Worker Execute ms | Network Build ms | Inner Wall ms |
| --- | ---: | ---: | ---: | ---: |
| `01_real_dense_ring6_amplitude.yaml` | `185.685` | `80.535` | `14.942` | `77.844` |
| `06_star_graph_phase_amplitude_heldout_low.yaml` | `154.841` | `89.402` | `16.852` | `86.820` |
| `08_parity_iqp_batched_heldout_medium.yaml` | `177.769` | `85.558` | `17.255` | `83.052` |

Request dispatch and reply are negligible:

- dispatch: about `0.28-0.32 ms`
- reply: about `0.003 ms`

So the worker answered the main question cleanly:

- the dominant one-shot penalty was per-process stack/bootstrap
- after that is amortized, the remaining fixed cost is not request transport
- the next remaining outer tax is above the worker, in the per-invocation CLI / driver layer

## 4. Do `01` and `06` become materially better in end-to-end wall time?

Yes.

Warm persistent request CLI wall:

- `01`: `644.897 ms`
- `06`: `638.334 ms`

One-shot bundle-hit CLI wall:

- `01`: `2065.971 ms`
- `06`: `2106.126 ms`

The result is materially better even before comparing against the noisier ranking-facing TTFR deltas. This is the right kind of evidence for a performance branch.

## 5. Does `08` remain neutral enough to show the feature is targeting the right regime?

No. `08` improved strongly too.

- one-shot bundle-hit CLI wall: `2021.989 ms`
- warm persistent CLI wall: `623.264 ms`
- warm gain: `1398.725 ms`

That means the surviving story is broader than low-repeat amplitude. The feature is attacking host/process/bootstrap overhead on this OVH machine, not only a narrow workload regime.

This is still a good result. It just changes the interpretation:

- yes: persistent execution is a promising general performance lever on this host
- no: it should not be framed as a regime-specific planner fix

## 6. What is the next branch?

Recommended next branch:

- `stack/27-ovh-persistent-executor-prototype`

Why:

- ranking is still unchanged
- Gate A and Gate B remain untouched
- strict compatibility and provenance were preserved
- selected plan identity stayed stable
- correctness stayed stable
- the worker turned a narrow one-shot reuse win into a broad, repeatable end-to-end latency win

## Final Decision

- Persistent execution is worth productizing as a performance feature.
- No planner retune branch is justified by this work.
- No new calibration claim should be made from this branch.
- If a later branch needs more performance after worker productization, the next investigation target should be the remaining outer CLI / driver process cost rather than planner ranking logic.
