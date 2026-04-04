# OVH Confidence Defaulting Readout

This report closes the post-confidence-validation milestone. It merges the confidence branch after the metric fix, makes confidence-aware validation the default reporting surface, and keeps planner retuning blocked.

## Inputs

- Frozen baseline: `docs/reports/ovh_v1_baseline.md`
- Confidence readout: `docs/reports/ovh_confidence_validation_readout.md`
- Merge-gate policy: `docs/reports/ovh_merge_gate_policy.md`
- Variance methodology v2: `docs/reports/ttfr_variance_methodology_v2.md`
- Heldout expansion milestone: `docs/heldout_expansion_plan.md`
- Gate A confidence summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v1/confidence_summary.md`
- Gate B confidence summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v1/confidence_summary.md`
- Targeted official-miss replicate pair: `artifacts/measured_validation_runs/ovh_v1_confidence/official_miss_dense_ring6_amplitude/real_dense_ring6_amplitude.quick_turnaround_vs_balanced.pair_summary.md`

## 1. Was the confidence metric bug fixed and tested?

Yes.

The `high_confidence_top1_accuracy` bug was fixed and regression-tested so the metric counts only high-confidence rows in both the numerator and denominator. The regression coverage now includes:

- one high-confidence correct row plus one medium correct row
- one high-confidence wrong row plus one medium correct row
- zero high-confidence rows

## 2. Was the branch merged without changing ranking behavior?

Yes.

`stack/16-ovh-confidence-validation` was merged after the metric fix, and this follow-on milestone keeps ranking behavior unchanged.

## 3. Are confidence summaries now mandatory for Gate A and Gate B?

Yes.

The default validation paths now emit:

- `summary.json`
- `confidence_summary.json`
- `confidence_summary.md`

The additive confidence metrics remain visible beside the legacy metrics:

- `top1_within_1ms_rate`
- `top1_within_3pct_rate`
- `selection_confidence_counts`
- `high_confidence_top1_accuracy`

## 4. Is heldout expansion the next benchmark milestone?

Yes.

The next benchmark milestone is explicitly `OVH Heldout Expansion v1`, with the goal of reaching `heldout_workload_count >= 5` using real-host-compatible imported workloads from genuinely new family IDs.

## 5. Is replicate methodology v2 defined for future close-call decisions?

Yes.

The targeted pair runner now defines an interleaved methodology upgrade:

- `pair_mode=sequential`: current lightweight default
- `pair_mode=interleaved`: `A/B/A/B/...` execution with per-block deltas and a delta-based confidence interval

This upgrade is designed for future close-call retune disputes and is documented, but it is not used here to approve a planner change.

## 6. Is any planner retune justified now?

No.

The current evidence still supports:

- a strong frozen OVH reference baseline
- confidence-aware evaluation honesty as the default reporting surface
- heldout expansion as the next benchmark milestone
- stronger replicate methodology before approving small TTFR-based retunes

It does **not** support a ranking or speed-factor retune now.

## Track Separation

Track A: evaluation / decision quality

- confidence-aware validation
- heldout expansion
- stronger replicate methodology
- only then any future retune consideration

Track B: performance opportunity

- low-repeat planner/setup mitigation
- reuse or caching of planning artifacts
- execution-side overhead reduction where the evidence supports it

Current evidence still points more strongly to planner/setup overhead than to a missing major template family, so Track B should not be merged under the banner of planner calibration.

## Conclusion

- merge the confidence branch after the bug fix
- keep the frozen OVH baseline as the reference
- make confidence-aware validation the default reporting surface
- expand heldout next
- use replicate methodology v2 for future close-call disputes
- keep planner retuning blocked for now
