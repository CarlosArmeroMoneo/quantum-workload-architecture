# OVH v2 Expanded Evaluation Baseline

This document freezes the expanded OVH evaluation stack after heldout expansion and anchor discovery, before any robustness or overhead-ROI follow-on work.

## Frozen artifacts

Gate A, expanded official top-2 slice:

- `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v2/summary.json`
- `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v2/confidence_summary.json`
- `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v2/confidence_summary.md`

Gate B, expanded top-3 calibration slice:

- `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/summary.json`
- `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/confidence_summary.json`
- `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/confidence_summary.md`

Anchor-discovery follow-on:

- `artifacts/anchor_discovery_runs/ovh_anchor_discovery_v1/gate_a_anchor_summary/confidence_summary.json`
- `artifacts/anchor_discovery_runs/ovh_anchor_discovery_v1/gate_a_anchor_summary/confidence_summary.md`
- `artifacts/anchor_discovery_runs/ovh_anchor_discovery_v1/gate_b_anchor_summary/confidence_summary.json`
- `artifacts/anchor_discovery_runs/ovh_anchor_discovery_v1/gate_b_anchor_summary/confidence_summary.md`
- `docs/reports/ovh_anchor_discovery_v1_readout.md`

## Baseline interpretation

- Coverage is solved for now on the OVH single-GPU exact-TN slice.
- Gate A remains strong enough that the official planner budget is not obviously broken.
- Gate B remains harsher, but it is still mainly a low/medium-confidence disagreement story.
- The miss-anchor layer found:
  - `selected_dominated_by_top2_count = 0`
  - `anchor_candidate_count = 0`
- Every interleaved anchor-discovery pair finished `inconclusive_vs_variance`, including the positive control.
- Planner ranking behavior is unchanged throughout this stack.

## Frozen conclusion

The expanded OVH v2 evaluation baseline is informative and stable enough to support robustness and overhead follow-on work, but it does not justify a planner-retune branch.

The next question is not broader coverage or broader ranking search. The next question is whether low-repeat TTFR differences are certifiable on this host and whether fresh-plan overhead is large enough to justify a plan-reuse or executor-overhead branch instead.
