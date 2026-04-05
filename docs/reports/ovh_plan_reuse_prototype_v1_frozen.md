# OVH Plan Reuse Prototype v1 Frozen

## Scope

This note freezes `stack/24-ovh-plan-reuse-prototype` after merge as a performance-only baseline.

What it preserves:

- planner ranking behavior remained unchanged
- Gate A and Gate B semantics remained unchanged
- reusable plan bundles are opt-in and strict
- the result is a narrow performance result, not a calibration result

## Frozen Truths

- Bundle hits preserve the same `selected_plan.plan_id` as the paired fresh-selection seed.
- Bundle compatibility is strict and auditable.
- The prototype improved end-to-end OVH CLI wall time on the two low-repeat amplitude workloads.
- The medium-repeat control stayed roughly flat to slightly negative in the original prototype run.
- The remaining limiter is execute-side cold-start behavior after probe removal, not selected-plan identity.

## Reference Artifacts

- Prototype benchmark summary:
  - `artifacts/plan_reuse/ovh_plan_reuse_prototype_v1/ovh_plan_reuse_prototype_v1.json`
  - `artifacts/plan_reuse/ovh_plan_reuse_prototype_v1/ovh_plan_reuse_prototype_v1.md`
- Prototype readout:
  - `docs/reports/ovh_plan_reuse_prototype_readout.md`
- OVH runbook:
  - `docs/runbooks/ovh_cu13_real_execution.md`

## Interpretation Guardrail

This freeze point is intentionally narrow:

- yes: explicit frozen-plan reuse is a valid opt-in performance feature
- no: it does not change ranking correctness
- no: it does not change Gate A or Gate B
- no: it does not justify reopening calibration or planner-retune work

That frozen interpretation is the starting point for `stack/25-ovh-executor-overhead-investigation`.
