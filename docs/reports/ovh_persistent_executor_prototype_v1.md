# OVH Persistent Executor Prototype v1

## Scope

This branch productizes the stack/26 worker into a conservative local prototype.

What stays unchanged:

- planner ranking behavior
- Gate A semantics
- Gate B semantics
- calibration and confidence claims

What this branch adds:

- a first-class local worker lifecycle
- strict persistent compatibility and provenance
- Gate P as a separate performance-only benchmark gate
- sequence and health evidence on the canonical OVH trio

Reference policy and plan:

- `docs/reports/ovh_gate_p_policy.md`
- `docs/reports/ovh_persistent_executor_prototype_plan.md`

Reference artifacts:

- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/summary.json`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/summary.md`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/per_request.csv`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/sequence_summary.json`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/sequence_summary.md`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/worker_health.jsonl`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/socket_recovery_checks.json`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/compatibility_reject_matrix.json`

## 1. Did the first-class lifecycle stay safe and explicit?

Yes.

The worker is now a first-class local CLI surface:

```bash
python -m aqs persistent-executor serve --socket /tmp/aqs-ovh.sock
python -m aqs persistent-executor ping --socket /tmp/aqs-ovh.sock
python -m aqs persistent-executor status --socket /tmp/aqs-ovh.sock
python -m aqs persistent-executor shutdown --socket /tmp/aqs-ovh.sock
```

Operational safety checks all passed in `socket_recovery_checks.json`:

- live-socket refusal: passed
- stale-socket cleanup: passed
- graceful shutdown cleanup: passed
- restart on the same socket after clean shutdown: passed
- `--replace-live-worker` handoff: passed

The status payload now exposes:

- `worker_session_id`
- `worker_start_time`
- `worker_startup_s`
- `session_uptime_s`
- `request_count`
- runtime metadata
- health snapshots including PID, RSS, and GPU memory

Compatibility also stayed strict:

- every mismatch in `compatibility_reject_matrix.json` was rejected with a non-empty reason
- repo/package/version mismatches were rejected
- objective / precision / system mismatches were rejected
- selected-plan identity mismatches were rejected

No silent fallback was added. Persistent fallback remains explicit-only via `--allow-one-shot-fallback`.

## 2. Did Gate P pass on the canonical OVH trio?

Yes.

Gate P passed on all three canonical OVH workloads:

- `01_real_dense_ring6_amplitude.yaml`
- `06_star_graph_phase_amplitude_heldout_low.yaml`
- `08_parity_iqp_batched_heldout_medium.yaml`

Every workload cleared the conservative prototype bar:

- warm persistent gain > `1.0 s`
- persistent cold session total < one-shot bundle total
- warm `worker_execute_s < 120 ms`
- dispatch + reply < `5 ms`
- `import_real_stack_s` effectively zero after startup
- selected-plan identity stable
- correctness stable

## 3. How much faster were warm persistent requests than one-shot bundle hits?

Warm persistent bundle hits beat one-shot bundle hits by:

- `01_real_dense_ring6_amplitude.yaml`: `1484.999779 ms`
- `06_star_graph_phase_amplitude_heldout_low.yaml`: `1475.000959 ms`
- `08_parity_iqp_batched_heldout_medium.yaml`: `1480.914290 ms`

Measured medians:

| Workload | One-Shot Bundle CLI ms | Persistent Warm CLI ms | Warm Worker Execute ms |
| --- | ---: | ---: | ---: |
| `01_real_dense_ring6_amplitude.yaml` | `2145.002` | `660.002` | `92.863` |
| `06_star_graph_phase_amplitude_heldout_low.yaml` | `2116.880` | `641.879` | `90.304` |
| `08_parity_iqp_batched_heldout_medium.yaml` | `2075.396` | `594.481` | `77.937` |

This is a broad host/bootstrap win, not a narrow planner-regime win.

## 4. Did cold persistent sessions still beat one-shot bundle totals?

Yes.

Even when the one-time worker startup cost is included, the persistent cold session total still beat one-shot bundle hits:

- `01_real_dense_ring6_amplitude.yaml`: `274.549439 ms` better
- `06_star_graph_phase_amplitude_heldout_low.yaml`: `191.034090 ms` better
- `08_parity_iqp_batched_heldout_medium.yaml`: `159.250424 ms` better

Measured medians:

| Workload | One-Shot Bundle CLI ms | Persistent Cold Session Total ms | Worker Startup ms |
| --- | ---: | ---: | ---: |
| `01_real_dense_ring6_amplitude.yaml` | `2145.002` | `1870.452` | `1075.633` |
| `06_star_graph_phase_amplitude_heldout_low.yaml` | `2116.880` | `1925.846` | `1118.442` |
| `08_parity_iqp_batched_heldout_medium.yaml` | `2075.396` | `1916.145` | `1065.767` |

That means persistence is not just moving cost around inside the same request. It is amortizing a real per-process bootstrap tax.

## 5. Did the worker stay strict about plan identity, correctness, and compatibility?

Yes.

Across `fresh`, `plan_json`, `one_shot_bundle`, `persistent_cold_bundle`, and `persistent_warm_bundle`:

- `selected_plan_id` stayed stable on all three workloads
- correctness stayed stable on all three workloads
- persistent requests reported explicit provenance fields
- request dispatch plus reply stayed negligible:
  - `01`: `0.328 ms`
  - `06`: `0.299 ms`
  - `08`: `0.243 ms`

`import_real_stack_s` stayed effectively zero on persistent cold and warm requests after startup, which is the direct confirmation that the worker is eliminating the repeated real-stack import path rather than hiding it inside a renamed metric.

## 6. Did the health and sequence evidence stay boring enough for a follow-on branch?

Yes, with one important qualification.

The sequence summary stayed operationally stable:

- all same-workload sessions at lengths `1`, `2`, `4`, and `8` preserved plan identity and correctness
- the mixed `01 -> 06 -> 08 -> 01 -> 06 -> 08` session also preserved plan identity and correctness
- warm request medians stayed in the same broad range across longer sessions

The health log shows a predictable pattern:

- worker-start RSS: about `508 MB`
- after the first request: about `741 MB`
- after the second request: about `756 MB`
- later requests: essentially flat around `756-757 MB` through the 8-request sessions

So there is a real one-time residency jump as the worker becomes warm, but no obvious monotonic leak pattern across the longer sessions in this branch’s evidence.

That means the feature is fast, safe, and boring enough to justify a follow-on productization branch.

## Final Decision

- Gate P passed.
- Ranking remains unchanged.
- Gate A and Gate B remain unchanged.
- No calibration or planner-quality claim is justified from this branch.
- The feature should stay labeled local and experimental for now.

Recommended next branch:

- `stack/28-ovh-lighter-client-or-session-runner`

Why:

- the persistent worker already removed the dominant per-process real-stack bootstrap tax
- request transport is negligible
- the remaining fixed cost now sits above the worker in the outer CLI / driver layer

So the next useful work is still performance-only:

- lighter client/library invocation
- session batch runner ergonomics
- possibly tighter outer-driver packaging around the existing strict worker

It should not be a planner-retune or calibration branch.
