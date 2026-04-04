# OVH Calibration Readout

This readout closes the current OVH calibration-infrastructure milestone. It uses the frozen `v1` real-host baseline plus follow-on diagnostics. It does not claim the planner is calibrated, and it does not recommend a ranking retune in this milestone.

## Inputs

- Frozen baseline: `docs/reports/ovh_v1_baseline.md`
- Selected-vs-oracle architecture comparison: `artifacts/measured_validation_runs/ovh_v1_calibration/selected_vs_oracle_arch.md`
- Residual export: `artifacts/measured_validation_runs/ovh_v1_calibration/validation_residuals.md`
- Calibration-only TTFR replicate summary: `artifacts/measured_validation_runs/ovh_v1_calibration/ttfr_replicate_summary.md`
- Merge-gate policy: `docs/reports/ovh_merge_gate_policy.md`
- Heldout expansion scaffolding: `docs/heldout_expansion_plan.md`

## Answers

### 1. What is the primary failure mode?

The current failure mode looks more like repeat-aware planner-overhead calibration plus near-tie uncertainty than a host-wide multiplicative speed-factor miss.

Evidence:

- The official baseline miss set is concentrated at repeats `1`, `2`, and `4`.
- The selected-vs-oracle comparison shows `0` primary-family shifts and `0` cases where oracle lowers `planner_roi`; both selected and oracle stay in the same `planner_roi`-dominated family across all five baseline workloads.
- The residual export shows the wrong-pick pattern is mostly `quick_turnaround -> balanced`, not a broad jump into a different candidate family.
- The residual export also says planning/setup dominates the miss signature on both the official top-2 slice and the top-3 diagnostic slice.

That combination points to calibration of overhead/confidence around low-repeat choices, not a missing major template family and not an obvious host-wide speed multiplier.

### 2. Does selected-vs-oracle evidence show that oracle often avoids planner_roi?

No.

- Selected primary families: `planner_roi` on `5/5` workloads
- Oracle primary families: `planner_roi` on `5/5` workloads
- Primary family shifts: `0`
- Oracle lowers `planner_roi` severity: `0`

The current selected-vs-oracle evidence says oracle usually wins inside the same broad architecture story rather than by escaping it.

### 3. Are TTFR differences large enough to rise above observed TTFR variance?

No, not in the calibration-only replicate probe.

The three measured pairwise comparisons all came back `inconclusive_vs_variance`:

- `real_ghz3_amplitude`: balanced vs quick-turnaround median delta `0.094 ms` against uncertainty band `6.756 ms`
- `real_qaoa_ring4_batched`: balanced vs quick-turnaround median delta `1.488 ms` against uncertainty band `124.301 ms`
- `real_dense_ring6_amplitude`: balanced vs deep-search median delta `0.181 ms` against uncertainty band `22.160 ms`

The delta-to-uncertainty ratios are only `0.014`, `0.012`, and `0.008`. That is far too small to justify a host-specific ranking tweak.

The replicate probe also shows why TTFR single-shots are not yet strong enough for small retunes on this host:

- The single-shot `qaoa` pair made `balanced` look better in the frozen baseline, but the replicate medians flipped the winner to `quick_turnaround`.
- The dense amplitude top-3 pair looked like a meaningful third-template edge in single-shot data, but the replicate medians reduced that gap to `0.181 ms`.

### 4. Is a retune justified now?

No.

The evidence is not overwhelming, and it does not isolate one localized ranking change that clearly improves the real-host signal beyond the observed TTFR uncertainty band.

## Recommendation

Do not retune ranking logic in this milestone.

The next action should be to add confidence-oriented reporting to measured validation and merge gates, for example:

- `top1_within_1ms`
- `top1_within_3pct`
- `high_confidence_top1_accuracy`
- `selection_confidence = low|medium|high`

That matches the current evidence better than a ranking change:

- misses stay within the same architecture family
- low-repeat choices are the stress point
- replicated TTFR uncertainty is still too large for small host-specific retunes

If a ranking change is reconsidered later, the most credible candidate is repeat-aware planner-overhead modeling for low-repeat workloads. That case is not strong enough yet to implement here.

## Stop Condition

This milestone stops after diagnostics and documentation:

- baseline frozen
- selected-vs-oracle comparison added and run on stored artifacts
- planner observability added without ranking change
- residual export added and run on stored artifacts
- calibration-only TTFR replicate mode added and exercised on the OVH host
- merge gates documented
- heldout expansion scaffolding documented

No ranking retune is landed in this branch.
