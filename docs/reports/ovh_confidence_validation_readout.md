# OVH Confidence Validation Readout

This report closes the post-calibration-infrastructure milestone. It preserves the frozen OVH `v1` baseline, adds confidence-aware interpretation, and keeps planner retuning blocked unless the evidence isolates a real correctness issue. No ranking logic change is landed here.

## Inputs

- Frozen baseline: `docs/reports/ovh_v1_baseline.md`
- Reconcile note: `docs/reports/ovh_top3_reconcile_note.md`
- Merge-gate policy: `docs/reports/ovh_merge_gate_policy.md`
- Selected-vs-oracle architecture comparison: `artifacts/measured_validation_runs/ovh_v1_calibration/selected_vs_oracle_arch.md`
- Residual export: `artifacts/measured_validation_runs/ovh_v1_calibration/validation_residuals.md`
- Official top-2 confidence summary: `artifacts/measured_validation_runs/ovh_v1_confidence/official_top2/confidence_summary.md`
- Targeted official-miss replicate pair: `artifacts/measured_validation_runs/ovh_v1_confidence/official_miss_dense_ring6_amplitude/real_dense_ring6_amplitude.quick_turnaround_vs_balanced.pair_summary.md`
- Heldout expansion plan: `docs/heldout_expansion_plan.md`

## 1. Did the reconcile audit change any baseline claim?

No baseline claim changed materially.

The reconcile audit found a wording issue, not a data-integrity bug:

- `real_dense_ring6_batched.yaml` is a genuine large top-3 wrong-pick row
- but it is a `quick_turnaround -> balanced` miss, not a verified third-rank winner
- the only verified third-rank winner in the audited top-3 slice remains `real_dense_ring6_amplitude.yaml` at `0.000969 s`, about `2.052%`

So the frozen baseline claim stays:

- official top-2 `require_real` OVH slice ran cleanly
- `top1_accuracy = 0.4`
- `mean_regret = 0.002755`
- `heldout_workload_count = 1`
- selected-run architecture aggregation is dominated by `planner_roi`

## 2. How many workloads are low / medium / high confidence?

For the official top-2 OVH slice:

- low confidence: `2`
- medium confidence: `3`
- high confidence: `0`

The current confidence split comes from `artifacts/measured_validation_runs/ovh_v1_confidence/official_top2/confidence_summary.md`.

## 3. What are `top1_within_1ms_rate` and `top1_within_3pct_rate`?

For the official top-2 OVH slice:

- `top1_within_1ms_rate = 0.6`
- `top1_within_3pct_rate = 0.4`
- `high_confidence_top1_accuracy = None`

These metrics add near-tie honesty and confidence bucketing without replacing the existing official metrics.

## 4. Did the targeted official-miss replicate probe stay inconclusive or produce a stable winner?

It did **not** produce a stable confirmation of the stored single-shot miss.

The targeted replicate probe on `real_dense_ring6_amplitude.yaml` for `quick_turnaround` vs `balanced` produced:

- baseline single-shot winner: `balanced`
- replicate median winner: `quick_turnaround`
- replicate winner gap: `7.456 ms`
- replicate uncertainty band: `3.466 ms`
- pair conclusion: `winner_flipped_vs_single_shot`

That means the official miss pair is not stable enough to justify a retune from the current single-shot baseline alone.

## 5. Is any planner retune justified now?

No.

The current best-supported conclusion is:

- confidence-aware reporting is justified now
- planner retuning is not justified now

The core reasons are:

- selected and oracle still stay in the same broad architecture story
- selected and oracle remain `planner_roi` on `5/5` audited workloads
- oracle lowers `planner_roi` severity `0` times in the current evidence
- the official miss pair flips winner under targeted TTFR replicates
- heldout coverage is still too small to support merge decisions by itself

## Track A: Evaluation Honesty / Confidence

- keep `top1_accuracy` and `mean_regret`
- add `top1_within_1ms_rate`
- add `top1_within_3pct_rate`
- add `selection_confidence_counts`
- keep targeted TTFR replicates opt-in and pair-focused

## Track B: Performance Opportunity

- the bigger opportunity still looks like low-repeat planner/setup overhead
- current evidence does not show a missing major template family
- ranking reshuffling is not yet the best-supported primary lever
- any future planner-ROI mitigation should be a separate optimization milestone, not folded into confidence reporting

## Recommendation

- merge the calibration-infrastructure branch and freeze it as the reference baseline
- keep retuning blocked
- use confidence-aware validation for future merge decisions
- expand heldout coverage next
- treat low-repeat planner/setup mitigation as a later, separate follow-up track
