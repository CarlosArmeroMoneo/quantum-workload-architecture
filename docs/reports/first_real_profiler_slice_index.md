# First Real Profiler Slice Index

This document is the public technical appendix for the first fully real profiler-backed exact-TN slice.

## Canonical Records In Git

- Host manifest: `configs/systems/ovh_gra9_rtx5000_28.yml`
- Readiness proof: `configs/systems/ovh_gra9_rtx5000_28.profiling_ready.json`
- Slice manifest: `configs/profiling/first_real_profiler_slice.yaml`
- Public artifact manifest: `configs/profiling/first_real_profiler_slice_ovh_gra9_rtx5000_28.artifacts.json`
- Canonical rerun guide: `docs/runbooks/ovh_cu13_real_execution.md`
- Canonical session summary: `docs/runbooks/profiler_ovh_gra9_rtx5000_28_session.md`

## Curated Tracked Evidence

- Unprofiled real amplitude execute:
  - `evidence/first_real_profiler_slice/real_ghz3_amplitude.execute.cu13.json`
- Real amplitude `nsys` summaries:
  - `evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.execution.json`
  - `evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.profile_summary.json`
  - `evidence/first_real_profiler_slice/real_ghz3_amplitude.arch.json`
- Real batched `ncu` summaries:
  - `evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.execution.json`
  - `evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.profile_summary.json`
  - `evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.ncu.csv`
  - `evidence/first_real_profiler_slice/real_dense_ring6_batched.arch.json`

## Raw Release Assets

- Release tag: `v0.5.0-evidence`
- Archive asset: `first-real-profiler-slice-evidence.zip`
- Checksum asset: `SHA256SUMS.txt`
- Release URL:
  - `https://github.com/CarlosArmeroMoneo/quantum-workload-architecture/releases/tag/v0.5.0-evidence`

The release archive contains the heavyweight profiler binaries that are intentionally excluded from git:

- amplitude `nsys` `.nsys-rep`, `.qdstrm`, `.sqlite`, attempt JSON, and stats CSVs
- batched `ncu` `.ncu-rep` and attempt JSON

## Result Summary

- Nomination source: `real_profiler_analysis`
- Bottleneck family: `launch_overhead`
- Setup share: approximately `21.86%`
- Profiler-kernel taxonomy report: `docs/reports/profiler_kernel_taxonomy_current_evidence.md`
- Counterfactual experiment card: `docs/experiments/launch_overhead_counterfactual.md`
- Reusable experiment-card template: `docs/experiments/experiment_card_template.md`

This result is grounded in the OVH CUDA 13 host execution path. The negative-control WSL2 host remains useful for debugging and failure classification, but it is not the evidence source for the public result above.
