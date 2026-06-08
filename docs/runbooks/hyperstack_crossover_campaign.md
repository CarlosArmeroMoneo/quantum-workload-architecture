# Hyperstack Crossover Campaign Runbook

Status: future budget campaign prep. No Hyperstack result is claimed by this repository today.

The campaign is capped at EUR 15 and is designed to answer one calibration question, not to run a broad sweep. A100 is preferred; RTX A6000 is the fallback if A100 is not available at the budget target.

## Credential Boundary

- Do not commit API tokens, SSH keys, shell history, or provider config.
- Use a local user login or local provider CLI session where possible.
- If a token is required, keep it in the shell environment or a local ignored file.
- Use least privilege and delete the VM as soon as each phase is complete.

## Phase 0: Environment Sanity

Budget cap: EUR 3.

1. Create one VM from `configs/systems/hyperstack_a100.template.yml` or the A6000 fallback.
2. SSH into the host.
3. Install the expected CUDA/cuQuantum and profiler environment.
4. Run `aqs doctor`.
5. Run one profiler smoke on `workloads/manifests/imported/real_ghz3_amplitude.yaml`.
6. Sync artifacts immediately.
7. Delete the VM if readiness fails.

Stop if profiler readiness fails, dependency import fails, or cost approaches the phase cap.

## Phase 1: First Accepted Run Candidate

Budget cap: EUR 5 additional.

Run `workloads/manifests/imported/real_dense_ring6_batched.yaml` with a real profiler summary and concrete artifact manifest. Sync artifacts before doing any next run.

Required artifacts:

- execution payload
- accuracy evaluation
- profile summary
- raw profiler artifact references
- artifact manifest with concrete paths
- system identity output

## Phase 2: One Medium Or Repeat Case

Use only remaining budget and only if Phase 1 produces an accepted candidate record. Select one workload from the campaign manifest; do not run both unless a new budget decision is made.

## Triage Link

Before creating the VM, run:

```bash
python scripts/triage_run_target.py \
  --workload workloads/manifests/imported/real_dense_ring6_batched.yaml \
  --target-class hyperstack \
  --evidence-goal calibration_campaign \
  --budget-cap-eur 15
```

Delete the VM when the phase completes, when any stop rule triggers, or when artifact acceptance is no longer possible inside the budget.
