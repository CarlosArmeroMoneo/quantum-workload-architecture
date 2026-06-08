# Quantum Workload Atlas Project Overview

Quantum Workload Atlas is a profiler-backed evidence system for quantum tensor-network workloads on accelerators. It connects workload structure, exact-TN planning, real cuQuantum execution, Nsight evidence, model calibration, and architecture-facing recommendations.

## Released Slice

**v0.1 First Real Profiler-Backed Slice** freezes the first public evidence package around the OVH Tier 3 profiler-backed exact-TN result.

- Release: [v0.1-first-real-profiler-slice](https://github.com/CarlosArmeroMoneo/quantum-workload-architecture/releases/tag/v0.1-first-real-profiler-slice)
- Canonical result: OVH RTX 5000 `real_dense_ring6_batched`.
- Claim boundary: GCP A100 remains pending until confirmed A100 artifacts are pinned.

## Main Result

```text
real_dense_ring6_batched -> cuquantum_tensornet_gpu -> Nsight Compute summary -> launch_overhead nomination
```

Evidence starts here:

- How to review this project: [docs/reports/how_to_review_this_project.md](docs/reports/how_to_review_this_project.md)
- Public release audit: [docs/reports/public_release_audit.md](docs/reports/public_release_audit.md)
- Public evidence index: [docs/reports/first_real_profiler_slice_index.md](docs/reports/first_real_profiler_slice_index.md)
- Evidence contract: [docs/architecture/evidence_contract.md](docs/architecture/evidence_contract.md)
- Profiler signal taxonomy: [docs/architecture/profiler_signal_taxonomy.md](docs/architecture/profiler_signal_taxonomy.md)
- Current profiler-kernel taxonomy report: [docs/reports/profiler_kernel_taxonomy_current_evidence.md](docs/reports/profiler_kernel_taxonomy_current_evidence.md)
- Evidence catalog: [docs/reports/public_evidence_catalog.md](docs/reports/public_evidence_catalog.md)
- Technical report: [docs/reports/quantum_workload_atlas_v0_1_report.md](docs/reports/quantum_workload_atlas_v0_1_report.md)
- Calibration report: [docs/reports/model_calibration_current_evidence.md](docs/reports/model_calibration_current_evidence.md)
- Calibration table: [docs/reports/model_calibration_table.md](docs/reports/model_calibration_table.md)
- Crossover calibration schema: [docs/architecture/calibration_dataset_schema.md](docs/architecture/calibration_dataset_schema.md)
- Workload scale ladder: [docs/architecture/workload_scale_ladder.md](docs/architecture/workload_scale_ladder.md)
- v0.2 crossover calibration skeleton: [docs/reports/quantum_workload_atlas_v0_2_crossover_calibration.md](docs/reports/quantum_workload_atlas_v0_2_crossover_calibration.md)
- v0.2 release notes: [docs/reports/v0_2_crossover_release_notes.md](docs/reports/v0_2_crossover_release_notes.md)
- Local 6GB preflight runbook: [docs/runbooks/local_6gb_preflight.md](docs/runbooks/local_6gb_preflight.md)
- Run triage runbook: [docs/runbooks/run_triage.md](docs/runbooks/run_triage.md)
- Experiment card template: [docs/experiments/experiment_card_template.md](docs/experiments/experiment_card_template.md)
- Launch-overhead counterfactual: [docs/experiments/launch_overhead_counterfactual.md](docs/experiments/launch_overhead_counterfactual.md)
- v0.1 release notes: [docs/reports/v0_1_first_real_profiler_slice_release_notes.md](docs/reports/v0_1_first_real_profiler_slice_release_notes.md)
- Next PR roadmap: [docs/reports/next_pr_roadmap.md](docs/reports/next_pr_roadmap.md)
- TPU sister-workload lane: [docs/architecture/tpu_sister_workload_lane.md](docs/architecture/tpu_sister_workload_lane.md)

## What To Notice

- Real `cuquantum_tensornet_gpu` execution is tracked with accuracy checks.
- Nsight Systems/Compute artifacts are reduced into structured summaries.
- The architecture nomination uses `real_profiler_analysis`, not synthetic scoring.
- Prediction-error ratios are visible instead of hidden.
- The GCP A100 lane is still pending; the June 2026 GCP draft was L4, not A100.
- The local NVIDIA 6GB lane is preflight/dev only and cannot support public performance claims.
