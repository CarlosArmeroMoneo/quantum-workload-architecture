# OVH Session Runner Prototype Plan

## Scope

This branch stays performance-only.

What stays unchanged:

- planner ranking
- Gate A semantics
- Gate B semantics
- Gate P semantics
- calibration and confidence reporting
- public backend claims

## Deliverables

Stack/28 adds two pieces together:

- a reusable thin persistent client that speaks directly to the local Unix-socket worker
- a bundle-first session runner that executes multiple compatible requests in one client process

## Gate S

Gate S is the new performance-only benchmark gate for session packaging overhead above the warm worker.

It compares:

- `persistent_warm_cli`
- `session_runner_existing_worker`
- `session_runner_autospawn_temp_worker`

It uses the same canonical OVH trio as Gate P.

## Session Manifest v1

The first session manifest format is intentionally narrow:

- `api_version: aqs.session.v1`
- `project: tnep`
- `mode: persistent_execute_sequence`
- bundle-first requests only
- strict reject by default
- optional explicit `--allow-one-shot-fallback`

## Tracked Seed Inputs

The branch also tracks a curated seed-bundle set for the canonical OVH trio under:

- `artifacts/plan_bundles/ovh_v2_seed/`

These are frozen benchmark inputs for the evidence chain.

Because compatibility stays strict, later reruns on a different repo commit may require regenerating fresh compatible bundles.

## Success Condition

The feature is considered successful only if it is:

- fast
- safe
- explicit
- boring to operate

If Gate S passes, the next branch should stay performance-only and package the remaining outer client/driver tax.

If Gate S fails, the next branch should still stay performance-only and target a lighter embedded client or another process model above the worker.
