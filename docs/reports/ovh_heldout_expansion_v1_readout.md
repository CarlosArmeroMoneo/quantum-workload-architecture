# OVH Heldout Expansion v1 Readout

This report closes the OVH heldout-expansion milestone. It expands the real-host-compatible imported corpus first, materializes a heldout-expanded `ovh_v2` validation corpus second, and reruns Gate A and Gate B without changing planner behavior.

## Inputs

- Intake inventory: `docs/ovh_heldout_input_inventory.md`
- Expanded Gate A manifest: `benchmarks/manifests/templates/tnep_measured_real_exact_slice_ovh_rtx5000_v2.yaml`
- Expanded Gate B manifest: `benchmarks/manifests/templates/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2.yaml`
- Expanded Gate A summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v2/summary.json`
- Expanded Gate A confidence summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v2/confidence_summary.md`
- Expanded Gate B summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/summary.json`
- Expanded Gate B confidence summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/confidence_summary.md`
- Frozen baseline reference: `docs/reports/ovh_v1_baseline.md`
- Merge-gate policy: `docs/reports/ovh_merge_gate_policy.md`

## 1. Did stack/18 successfully remove the input-corpus blocker?

Yes.

`stack/18` added four new real-host-compatible imported source families:

- `star_graph_phase`
- `ladder_brickwork`
- `parity_iqp`
- `spin_chain_phase`

All four were validated in `implemented` and `real` modes, and all four passed a real OVH `execution_intent=require_real` smoke execution.

## 2. Did stack/19 raise `heldout_workload_count` to at least 5?

Yes.

The expanded `ovh_v2` corpus includes the frozen five baseline workloads plus four new `heldout_family` manifests, and both rerun summaries now report:

- `heldout_workload_count = 5`

## 3. Were Gate A and Gate B rerun with default confidence artifacts?

Yes.

The expanded reruns produced:

Gate A:

- `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v2/summary.json`
- `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v2/confidence_summary.json`
- `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v2/confidence_summary.md`

Gate B:

- `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/summary.json`
- `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/confidence_summary.json`
- `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v2/confidence_summary.md`

## 4. Did the expanded slice surface any high-confidence or replicate-stable motivating miss?

No.

The expanded reruns still do not produce a motivating miss that satisfies the current retune gate.

Observed state:

- Gate A: `selection_confidence_counts = {'low': 4, 'medium': 5, 'high': 0}`
- Gate B: `selection_confidence_counts = {'low': 6, 'medium': 3, 'high': 0}`
- `high_confidence_top1_accuracy = None` for both expanded gates
- `replicate_stability` is absent for the expanded rerun rows because no pair-specific replicate evidence was attached to these new workloads

The most material expanded Gate A miss remains `01_real_dense_ring6_amplitude.yaml`:

- selected: `quick_turnaround`
- winner: `balanced`
- regret: `0.009865 s`
- confidence: `medium`

Expanded Gate B exposes more misses, including new heldout rows, but they remain low or medium confidence only. The new heldout low-repeat amplitude miss on `06_star_graph_phase_amplitude_heldout_low.yaml` is real, but still low-confidence:

- selected: `quick_turnaround`
- winner: `deep_search`
- regret: `0.000852 s`
- confidence: `low`

## 5. Is a planner-retune branch justified now?

No.

The expanded slice improves evaluation honesty and heldout coverage, but it still does not produce a qualifying retune anchor under the documented policy:

- no motivating miss is `high` confidence
- no motivating miss is `replicate_stable`
- the existing official miss story still does not clear the current evidence bar for ranking surgery

## 6. If not, what remains blocked and why?

Retuning remains blocked because the expanded coverage improved breadth, not certainty.

What remains blocked:

- a motivating miss that is `high` confidence or backed by stable replicate evidence
- stronger evidence that a ranking change, rather than planner/setup-overhead mitigation, is the best next lever

Current best-supported reading:

- coverage is now meaningfully better
- heldout metrics are now substantial enough to include in gate decisions
- planner retuning is still not justified
- performance work, if pursued, should remain on a separate branch and separate track

## Summary Metrics

Expanded Gate A:

- `workload_count = 9`
- `heldout_workload_count = 5`
- `top1_accuracy = 0.777778`
- `mean_regret = 0.001111`
- `heldout_mean_regret = 0.0`
- `top1_within_1ms_rate = 0.888889`
- `top1_within_3pct_rate = 0.888889`

Expanded Gate B:

- `workload_count = 9`
- `heldout_workload_count = 5`
- `top1_accuracy = 0.333333`
- `mean_regret = 0.007459`
- `heldout_mean_regret = 0.000254`
- `top1_within_1ms_rate = 0.666667`
- `top1_within_3pct_rate = 0.666667`

## Verdict

- `stack/18` succeeded: the input-corpus blocker is removed
- `stack/19` succeeded: the heldout slice now reaches `heldout_workload_count >= 5`
- Gate A and Gate B reran with default confidence artifacts
- no legitimate planner-retune anchor appears yet
- the next planner-retune branch is still blocked until a miss is either `high` confidence or `replicate_stable`
