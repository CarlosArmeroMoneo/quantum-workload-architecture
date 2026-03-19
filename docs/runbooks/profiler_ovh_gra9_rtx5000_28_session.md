# OVH GRA9 RTX5000-28 Profiler Session

Session date: March 14, 2026

## Canonical Host

- Provider: OVH Public Cloud
- Region: GRA9
- Flavor: `rtx5000-28`
- OS: Ubuntu 24.04.3 LTS
- GPU: Quadro RTX 5000
- Driver: `580.126.09`
- Profiler tools: host-installed `nsys`, `QdstrmImporter`, and `ncu`

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
- Curated tracked evidence:
  - `evidence/first_real_profiler_slice/real_ghz3_amplitude.execute.cu13.json`
  - `evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.execution.json`
  - `evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.profile_summary.json`
  - `evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.execution.json`
  - `evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.profile_summary.json`
  - `evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.ncu.csv`
  - `evidence/first_real_profiler_slice/real_dense_ring6_batched.arch.json`
- Raw release asset:
  - `https://github.com/CarlosArmeroMoneo/quantum-workload-architecture/releases/tag/v0.5.0-evidence`

## First Real Nomination

- `nomination_source=real_profiler_analysis`
- `bottleneck_family=launch_overhead`
- `setup_share_pct~=21.86`

The canonical architecture handoff remained valid even when the imported metrics summary was sparse, because the final code can fall back to the adjacent profile summary JSON and to execution `phase_times`.

## References

- Rerun guide: `docs/runbooks/ovh_cu13_real_execution.md`
- Evidence index: `docs/reports/first_real_profiler_slice_index.md`
- Public artifact manifest: `configs/profiling/first_real_profiler_slice_ovh_gra9_rtx5000_28.artifacts.json`
