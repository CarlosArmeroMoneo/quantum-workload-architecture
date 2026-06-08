# Run Triage Runbook

Status: offline planning tool. It does not launch GPU work or call cloud APIs.

Use the triage planner before using local GPU time, Hyperstack budget, or GCP quota.

## Example

```bash
python scripts/triage_run_target.py \
  --workload workloads/manifests/imported/real_dense_ring6_batched.yaml \
  --target-class hyperstack \
  --evidence-goal calibration_campaign \
  --budget-cap-eur 15
```

The JSON output includes a recommendation, reason codes, risk, required artifacts, and stop rules.

## Recommendation Values

- `local_preflight`: tiny local sanity work only.
- `hyperstack_budget`: bounded paid mini-campaign fits the declared budget.
- `gcp_wait_for_quota`: A100 acceptance work should wait for quota and gate readiness.
- `do_not_run`: artifact requirements, budget, target, or evidence goal are not ready.

## Policy

The policy file is `configs/experiments/run_triage_policy.yaml`. Local 6GB cannot be recommended for accepted profiler-backed publication evidence. GCP A100 remains acceptance-gated. Hyperstack is recommended only for tightly scripted, artifact-bound work inside the budget cap.
