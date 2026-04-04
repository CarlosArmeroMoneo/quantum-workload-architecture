# OVH Top-3 Reconcile Note

This note reconciles the apparent tension between the frozen OVH baseline report and the residual-export narrative for the top-3 diagnostic.

## Audit Target

- Summary audited: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v1/summary.json`
- Workload row audited: `real_dense_ring6_batched.yaml`

## Result

The batched top-3 row is a real large miss, but it is **not** a verified third-rank winner.

The raw summary row shows:

- selected plan: `quick_turnaround`
- measured winner: `balanced`
- measured runner-up: `deep_search`
- recommendation ranks: `quick_turnaround=1`, `balanced=2`, `deep_search=3`

So the true reconcile outcome is:

- the batched case was **not** actually a third-rank winner
- the residual export was describing a real top-3 wrong-pick row, not claiming that every top-3 wrong pick was a third-rank win
- the baseline statement that the top-3 diagnostic found **one small verified third-rank winner** on `real_dense_ring6_amplitude.yaml` remains correct

## Wording Fix

The residual export now explicitly distinguishes:

- wrong-pick rows in the top-3 diagnostic
- verified third-rank winners

This is a wording / interpretation fix, not a summary-corruption or evaluation-matching bug.
