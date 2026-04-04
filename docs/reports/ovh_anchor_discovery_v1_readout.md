# OVH Anchor Discovery v1 Readout

## 1. Was the heldout-threshold summary bug fixed?

Yes.

- The confidence-summary renderer now treats `heldout_workload_count >= 5` as meeting the documented minimum.
- Regression coverage was added for the `heldout_workload_count == 5` boundary in `tests/test_validation_confidence.py`.
- The expanded confidence summaries were rerendered from stored summaries only:
  - `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v2/confidence_summary.md`
  - `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/confidence_summary.md`

## 2. Did the miss-anchor layer identify any `selected_dominated_by_top2` workloads?

No.

- Anchor-aware Gate B summary:
  - `artifacts/anchor_discovery_runs/ovh_anchor_discovery_v1/gate_b_anchor_summary/confidence_summary.json`
  - `artifacts/anchor_discovery_runs/ovh_anchor_discovery_v1/gate_b_anchor_summary/confidence_summary.md`
- Result:
  - `selected_dominated_by_top2_count = 0`
  - `stable_selected_miss_count = 0`
  - `anchor_candidate_count = 0`

## 3. Which workloads, if any, are `retune_anchor_candidate = true`?

None.

- `anchor_candidate_workloads = []` in both:
  - `artifacts/anchor_discovery_runs/ovh_anchor_discovery_v1/gate_a_anchor_summary/confidence_summary.json`
  - `artifacts/anchor_discovery_runs/ovh_anchor_discovery_v1/gate_b_anchor_summary/confidence_summary.json`

## 4. Does any miss now satisfy the current landing rule?

No.

The targeted interleaved pair set did not produce a single replicate-stable motivating miss. Every measured pair concluded `inconclusive_vs_variance`, including the positive-control workload where `quick_turnaround` already wins in the stored summary.

Targeted pair outcomes:

- `01_real_dense_ring6_amplitude.yaml`
  - `quick_turnaround vs balanced`: inconclusive; replicate median winner `quick_turnaround`; delta 95% CI `[-15.585, 31.067] ms`
  - `quick_turnaround vs deep_search`: inconclusive; replicate median winner `quick_turnaround`; delta 95% CI `[-8.043, 39.813] ms`
  - `balanced vs deep_search`: inconclusive; replicate median winner `balanced`; delta 95% CI `[-6.091, 22.845] ms`
- `06_star_graph_phase_amplitude_heldout_low.yaml`
  - `quick_turnaround vs deep_search`: inconclusive; replicate median winner `quick_turnaround`; delta 95% CI `[-6.883, 20.682] ms`
  - `quick_turnaround vs balanced`: inconclusive; replicate median winner `quick_turnaround`; delta 95% CI `[-10.879, 20.060] ms`
- `02_real_dense_ring6_batched.yaml`
  - `quick_turnaround vs deep_search`: inconclusive; replicate median winner `quick_turnaround`; delta 95% CI `[-74.398, 36.146] ms`
  - `quick_turnaround vs balanced`: inconclusive; replicate median winner `quick_turnaround`; delta 95% CI `[-84.425, 37.438] ms`
- Positive control: `08_parity_iqp_batched_heldout_medium.yaml`
  - `quick_turnaround vs balanced`: inconclusive; replicate median winner `quick_turnaround`; delta 95% CI `[-106.161, 42.107] ms`

## 5. If yes, what narrow regime-specific retune branch is justified?

No retune branch is justified.

The anchor-discovery fork resolves to Outcome B: no selected-plan miss is currently replicate-stable enough to support planner-ranking surgery.

## 6. If not, should ranking work pause in favor of `stack/22-ovh-low-repeat-overhead-roi`?

Yes.

Current best-supported interpretation:

- Gate A still says the official planner budget is doing well on the expanded OVH slice.
- Gate B still disagrees more often, but anchor quality is too weak to turn those disagreements into retune evidence.
- The miss-centric layer closes the previous blind spot: none of the targeted workloads shows the selected plan stably dominated by both alternatives.
- Because even the positive control remained inside the interleaved uncertainty band, the next valuable branch should be performance-only ROI work rather than more ranking work.

Recommended next branch:

- `stack/22-ovh-low-repeat-overhead-roi`

That branch should stay explicitly separate from calibration/ranking claims and focus on fresh-plan vs frozen-plan decomposition for:

- `01_real_dense_ring6_amplitude.yaml`
- `06_star_graph_phase_amplitude_heldout_low.yaml`
