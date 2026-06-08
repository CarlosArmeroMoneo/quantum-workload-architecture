# Launch-Overhead Counterfactual Runbook

Status: planning only. No new result is claimed here.

Use `configs/experiments/launch_overhead_counterfactual_v0_2.yaml` to run a bounded paired-arm experiment against the existing OVH `launch_overhead` nomination.

## Run Order

1. Reconfirm the baseline workload and host identity.
2. Run `baseline_repeat_1`.
3. Run only one reuse arm at a time.
4. Sync execution payloads and profiler summaries immediately.
5. Stop when a stop criterion triggers or when the selected paired arms are complete.

## Required Metrics

- `ttfr_s`
- `steady_iter_ms`
- `setup_share_pct`
- `contract_share_pct`
- correctness pass
- profile summary exists
- nomination change

## Stop Criteria

- Correctness failure.
- Profiler evidence missing.
- TTFR improvement under 10 percent.
- Budget cap reached.
- Setup work moved outside the measured region.

If a stop criterion triggers, keep the original OVH nomination unchanged and report the arm as stopped, pending, or rejected.
