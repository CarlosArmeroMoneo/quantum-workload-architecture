# OVH Measured Validation Follow-On

This follow-on report captures the April 4, 2026 measured-validation pass on `ovh_gra9_rtx5000_28` after the evidence package was refreshed. It uses only measured outputs from the OVH host and keeps the negative calibration result intact.

## Scope

- Official require-real slice manifest: `benchmarks/manifests/templates/tnep_measured_real_exact_slice_ovh_rtx5000_v1.yaml`
- Top-3 diagnostic manifest: `benchmarks/manifests/templates/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v1.yaml`
- Host manifest: `configs/systems/ovh_gra9_rtx5000_28.yml`
- Baseline measured summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v1/summary.json`
- Baseline architecture summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v1/validation_arch.json`
- Top-3 measured summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_top3_v1/summary.json`
- Post-calibration trial summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v1_postcal/summary.json`
- Post-calibration architecture summary: `artifacts/measured_validation_runs/tnep_measured_real_exact_slice_ovh_rtx5000_v1_postcal/validation_arch.json`

## Official Slice

- The OVH measured-validation slice ran cleanly under `execution_intent=require_real`.
- Baseline summary metrics:
  - `top1_accuracy = 0.4`
  - `mean_regret = 0.002755`
  - `heldout_mean_regret = 0.0`
  - `workload_count = 5`
  - `heldout_workload_count = 1`
- The selected-vs-oracle deltas were nontrivial but small in absolute TTFR terms:
  - `real_dense_ring6_amplitude.yaml`: selected `quick_turnaround`, oracle `balanced`, regret `0.009504 s`
  - `real_ghz3_amplitude.yaml`: selected `quick_turnaround`, oracle `balanced`, regret `0.000748 s`
  - `real_qaoa_ring4_batched.yaml`: selected `quick_turnaround`, oracle `balanced`, regret `0.003522 s`

## Architecture Readout

- `validation_arch.json` now reflects measured runtime phase timings embedded in the real execution payloads, not just profiler-side summaries.
- Recurring bottleneck families in the baseline pass:
  - `planner_roi`: `5/5` workloads
  - `reuse_cache`: `1/5` workloads
  - `launch_overhead`: `1/5` workloads
- The dominant recurring signal is that path search and one-time orchestration still consume most TTFR on this host for these small exact-TN cases.

## Top-3 Diagnostic

- The top-3 diagnostic did not show a major hidden third-template winner, but it did show one real third-rank edge case.
- `deep_search` won `1/5` workloads: `real_dense_ring6_amplitude.yaml`.
- On that workload, the best top-2 candidate was `balanced` at `0.048198861 s`, while the top-3 winner `deep_search` ran at `0.04722993 s`.
- The hidden third-template edge was `0.000969 s`, about `2.052%` over the top-3 winner. That is real, but not large enough to call a major hidden third-template miss.

## Calibration Attempt

- A one-line planner retune was tested locally to stop charging path-search time linearly with `hyper_samples`.
- That retune was motivated by measured OVH runs where `contract_path` time stayed in a narrow band across `hyper_samples=1,2,8,24`, instead of scaling linearly with search budget.
- The retune was measured, but it was not kept as a repo default because the rerun was mixed:
  - `top1_accuracy` stayed flat at `0.4`
  - `mean_regret` improved slightly from `0.002755` to `0.00258`
  - `heldout_mean_regret` worsened from `0.0` to `0.000485`
  - The selected template shifted heavily toward `deep_search`, which was not robust enough on this five-workload slice to justify changing the default planner
- The default planner code therefore remains unchanged. The post-calibration artifacts are kept only as measured evidence of an inconclusive calibration trial.

## Verdict

- `Yes`: the OVH require-real measured-validation slice itself is a real success.
- `Yes`: the evidence package now includes a measured `summary.json`, a recurring-family `validation_arch.json`, and a real top-3 diagnostic.
- `No`: this is not yet the clearest full calibration-success package because the post-calibration rerun did not deliver a clean, defensible metric improvement.
- The honest state is: strong measured validation evidence exists on the OVH host, but planner calibration remains open.
