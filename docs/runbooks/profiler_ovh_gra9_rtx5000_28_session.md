# OVH GRA9 RTX5000-28 Profiler Session

Session refresh date: April 4, 2026

Canonical first-slice evidence date: March 14, 2026

## Live Host Inventory

- Provider: OVH Public Cloud
- Region: GRA9
- Flavor: `rtx5000-28`
- OS: Ubuntu 24.04.3 LTS
- Kernel: `6.14.0-34-generic`
- GPU: Quadro RTX 5000
- Driver: `580.126.09`
- Profiler tools: host-installed `nsys`, `QdstrmImporter`, and `ncu`
- Tool versions:
  - `nsys`: `NVIDIA Nsight Systems version 2023.2.3.1004-33186433v0`
  - `QdstrmImporter`: `NVIDIA Nsight Systems 2023.2.3.1004-33186433v0`
  - `ncu`: `Version 2023.2.2.0 (build 33188574) (public-release)`
- Container runtime on `PATH`: none detected during the April 4 refresh

## Canonical Environment

- Python environment: `.venv_cu13`
- CUDA wheel helper: `~/qwa_cuda_env_cu13.sh`
- Tool paths:
  - `nsys`: `/usr/bin/nsys`
  - `QdstrmImporter`: `/usr/lib/nsight-systems/host-linux-x64/QdstrmImporter`
  - `ncu`: `/usr/bin/ncu`

## Recorded Outputs

- Readiness proof:
  - `configs/systems/ovh_gra9_rtx5000_28.profiling_ready.json`
- Canonical first-slice curated evidence:
  - `evidence/first_real_profiler_slice/real_ghz3_amplitude.execute.cu13.json`
  - `evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.execution.json`
  - `evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.profile_summary.json`
  - `evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.execution.json`
  - `evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.profile_summary.json`
  - `evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.ncu.csv`
  - `evidence/first_real_profiler_slice/real_dense_ring6_batched.arch.json`
- Stage 10 repeat ROI measured outputs:
  - `artifacts/campaigns/repeat_roi_v1/summary.json`
  - `artifacts/campaigns/repeat_roi_v1/results.csv`
  - `artifacts/campaigns/repeat_roi_v1/report.md`
- Stage 11 diagnostic NCU and CUDA Graph outputs:
  - `artifacts/profiles/ncu/real_dense_ring6_batched.ncu.32f6e24969d9e164.profile_summary.json`
  - `artifacts/profiles/ncu/real_dense_ring6_batched.ncu.32f6e24969d9e164.ncu.csv`
  - `artifacts/campaigns/cuda_graphs_ablation_v1/summary.json`
  - `artifacts/campaigns/cuda_graphs_ablation_v1/results.csv`
  - `artifacts/campaigns/cuda_graphs_ablation_v1/report.md`
- Stage 12 CUDA-Q adapter and tiny-MNK sidecar outputs:
  - `artifacts/cudaq_adapter_compare/summary.json`
  - `artifacts/cudaq_adapter_compare/report.md`
  - `sidecars/tiny_mnk_lab/results/ncu/benchmark.csv`
  - `sidecars/tiny_mnk_lab/results/ncu/summary.json`
  - `sidecars/tiny_mnk_lab/results/ncu/tiny_mnk.ncu.csv`
  - `sidecars/tiny_mnk_lab/reports/report_template.md`
- Raw release asset:
  - `https://github.com/CarlosArmeroMoneo/quantum-workload-architecture/releases/tag/v0.5.0-evidence`

## First Real Nomination

- `nomination_source=real_profiler_analysis`
- `bottleneck_family=launch_overhead`
- `setup_share_pct~=21.86`

The canonical architecture handoff remained valid even when the imported metrics summary was sparse, because the final code can fall back to the adjacent profile summary JSON and to execution `phase_times`.

## Measured Follow-On Notes

- The repeat-ROI campaign was mostly negative, so the packaging refresh keeps the existing planner defaults.
- The CUDA Graph A/B pass failed every attempted graph capture on the default (legacy) stream and does not claim a speedup.
- CUDA-Q remains adapter-backed only for structural comparison; native CUDA-Q runtime execution is still unsupported in this repo.
- The tiny-MNK sidecar now has measured outputs, but the measured launch geometry differs materially from the internal cuTensorNet tiny-MNK kernels.

## References

- Rerun guide: `docs/runbooks/ovh_cu13_real_execution.md`
- Evidence index: `docs/reports/first_real_profiler_slice_index.md`
- Public artifact manifest: `configs/profiling/first_real_profiler_slice_ovh_gra9_rtx5000_28.artifacts.json`
