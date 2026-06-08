# Quantum Workload Atlas Portfolio

Quantum Workload Atlas is a profiler-backed evidence system for quantum tensor-network workloads on accelerators. It connects workload structure, exact-TN planning, real cuQuantum execution, Nsight evidence, model calibration, and architecture-facing recommendations.

## Pinned Project

**v0.1 First Real Profiler-Backed Slice** is the release reference for this project.

- Release: [v0.1-first-real-profiler-slice](https://github.com/CarlosArmeroMoneo/quantum-workload-architecture/releases/tag/v0.1-first-real-profiler-slice)
- Commit/tag purpose: freeze the first public evidence package around the OVH Tier 3 profiler-backed exact-TN slice.
- Claim boundary: GCP A100 remains pending until confirmed A100 artifacts are pinned.

## Main Result

The canonical public result is the OVH RTX 5000 profiler-backed slice:

```text
real_dense_ring6_batched -> cuquantum_tensornet_gpu -> Nsight Compute summary -> launch_overhead nomination
```

Evidence starts here:

- How to review this project: [docs/reports/how_to_review_this_project.md](docs/reports/how_to_review_this_project.md)
- Public evidence index: [docs/reports/first_real_profiler_slice_index.md](docs/reports/first_real_profiler_slice_index.md)
- Evidence contract: [docs/architecture/evidence_contract.md](docs/architecture/evidence_contract.md)
- Profiler signal taxonomy: [docs/architecture/profiler_signal_taxonomy.md](docs/architecture/profiler_signal_taxonomy.md)
- Evidence catalog: [docs/reports/public_evidence_catalog.md](docs/reports/public_evidence_catalog.md)
- Technical report: [docs/reports/quantum_workload_atlas_v0_1_report.md](docs/reports/quantum_workload_atlas_v0_1_report.md)
- Calibration report: [docs/reports/model_calibration_current_evidence.md](docs/reports/model_calibration_current_evidence.md)
- Calibration table: [docs/reports/model_calibration_table.md](docs/reports/model_calibration_table.md)
- Launch-overhead counterfactual: [docs/experiments/launch_overhead_counterfactual.md](docs/experiments/launch_overhead_counterfactual.md)
- v0.1 release notes: [docs/reports/v0_1_first_real_profiler_slice_release_notes.md](docs/reports/v0_1_first_real_profiler_slice_release_notes.md)
- Next PR roadmap: [docs/reports/next_pr_roadmap.md](docs/reports/next_pr_roadmap.md)

## What To Notice

- Real `cuquantum_tensornet_gpu` execution is tracked with accuracy checks.
- Nsight Systems/Compute artifacts are reduced into structured summaries.
- The architecture nomination uses `real_profiler_analysis`, not synthetic scoring.
- Prediction-error ratios are visible instead of hidden.
- The GCP A100 lane is still pending; the June 2026 GCP draft was L4, not A100.

## Evidence Methodology

- Technical report: [docs/reports/technical_report.md](docs/reports/technical_report.md)
- Profiler signal taxonomy: [docs/architecture/profiler_signal_taxonomy.md](docs/architecture/profiler_signal_taxonomy.md)
- Evidence contract: [docs/architecture/evidence_contract.md](docs/architecture/evidence_contract.md)
- Evidence index: [docs/reports/first_real_profiler_slice_index.md](docs/reports/first_real_profiler_slice_index.md)
- Review guide: [docs/reports/how_to_review_this_project.md](docs/reports/how_to_review_this_project.md)
