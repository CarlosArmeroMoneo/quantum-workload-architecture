# OVH CUDA 13 Real Execution

## Purpose

Use this runbook to reproduce the canonical profiler-backed slice and the measured follow-on OVH reports on the Ubuntu 25.04 RTX 5000 host.

## Host Roles

- Local Windows + WSL2 + RTX 4050: development and negative-control profiling host.
- OVH Ubuntu 25.04 + Quadro RTX 5000: canonical public evidence host.

## Connect And Prepare

Reconnect to your provisioned OVH host with your normal SSH workflow, then enter the repo:

```bash
cd ~/quantum-workload-architecture
tmux attach -t qwa || tmux new -s qwa
```

For first-time setup:

```bash
bash scripts/setup_ovh_cu13_env.sh ~/quantum-workload-architecture
```

The setup script creates `.venv_cu13`, installs the repo plus CUDA 13 dependencies, and writes `~/qwa_cuda_env_cu13.sh`.

## Activate The Canonical Shell

```bash
cd ~/quantum-workload-architecture
source .venv_cu13/bin/activate
source ~/qwa_cuda_env_cu13.sh
```

Expected profiler tools on this host:

- `nsys`: `/usr/bin/nsys`
- `QdstrmImporter`: `/usr/lib/nsight-systems/host-linux-x64/QdstrmImporter`
- `ncu`: `/usr/bin/ncu`
- `nsys` version: `NVIDIA Nsight Systems version 2023.2.3.1004-33186433v0`
- `ncu` version: `Version 2023.2.2.0 (build 33188574) (public-release)`

## Readiness Gate

```bash
python -m aqs doctor \
  --profiling \
  --outdir artifacts/readiness/ovh_gra9_rtx5000_28 \
  --out configs/systems/ovh_gra9_rtx5000_28.profiling_ready.json
```

Do not continue unless `profiling_ready=true`.

## Canonical Execution Sequence

Real unprofiled amplitude sanity run:

```bash
python -m aqs tnep execute \
  --manifest workloads/manifests/imported/real_ghz3_amplitude.yaml \
  --system-manifest configs/systems/ovh_gra9_rtx5000_28.yml \
  --plan-rank 1 \
  --objective ttfr \
  --probe-strategy cuquantum_if_available \
  --planner-budget balanced \
  --measurement-repeats 2 \
  --execution-intent require_real \
  --no-allow-distributed \
  --out artifacts/real_profile_runs/real_ghz3_amplitude.execute.cu13.json
```

Real amplitude `nsys` run:

```bash
python -m aqs profile nsys \
  --manifest workloads/manifests/imported/real_ghz3_amplitude.yaml \
  --system-manifest configs/systems/ovh_gra9_rtx5000_28.yml \
  --plan-rank 1 \
  --objective ttfr \
  --probe-strategy cuquantum_if_available \
  --planner-budget balanced \
  --measurement-repeats 2 \
  --execution-intent require_real \
  --no-allow-distributed \
  --outdir artifacts/real_profile_runs/amplitude_nsys_cu13_final
```

Real batched `ncu` run:

```bash
python -m aqs profile ncu \
  --manifest workloads/manifests/imported/real_dense_ring6_batched.yaml \
  --system-manifest configs/systems/ovh_gra9_rtx5000_28.yml \
  --plan-rank 1 \
  --objective ttfr \
  --probe-strategy cuquantum_if_available \
  --planner-budget balanced \
  --measurement-repeats 2 \
  --execution-intent require_real \
  --no-allow-distributed \
  --outdir artifacts/real_profile_runs/batched_ncu_cu13
```

Architecture handoff:

```bash
python -m aqs arch analyze-execution \
  --payload artifacts/real_profile_runs/batched_ncu_cu13/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.execution.json \
  --out artifacts/arch_real/real_dense_ring6_batched.arch.json
```

## Calibration-Only TTFR Replicates

Use calibration-only TTFR replicates only for uncertainty estimation on a small number of candidate pairs. This mode is opt-in, default-off, and should not replace the official deployment-style benchmark.

Key rules:

- Keep the official benchmark on the single-shot `require_real` slice.
- Use explicit `--plan-json` overrides so the probe measures frozen candidate plans rather than a fresh planner decision.
- Treat `--ttfr-repeats` as a diagnostic aid for uncertainty bands, not as a ranking retune mechanism by itself.
- The replicate path rebuilds a fresh network each time, but it does not simulate a fresh process launch for every sample.

Example:

```bash
python -m aqs tnep execute \
  --manifest workloads/manifests/imported/real_ghz3_amplitude.yaml \
  --system-manifest configs/systems/ovh_gra9_rtx5000_28.yml \
  --plan-json artifacts/measured_validation_runs/ovh_v1_calibration/plan_overrides/ghz3_oracle_balanced.json \
  --objective ttfr \
  --probe-strategy real_if_available \
  --planner-budget balanced \
  --measurement-repeats 2 \
  --ttfr-repeats 7 \
  --execution-intent require_real \
  --no-allow-distributed \
  --out artifacts/measured_validation_runs/ovh_v1_calibration/ttfr_replicates/ghz3_oracle_balanced.execute.json
```

Current tracked calibration summary outputs live in:

- `artifacts/measured_validation_runs/ovh_v1_calibration/ttfr_replicate_summary.md`
- `artifacts/measured_validation_runs/ovh_v1_calibration/ttfr_replicate_summary.json`

## Public Evidence Layout

- Curated summaries are tracked in `evidence/first_real_profiler_slice/`.
- Raw profiler binaries are distributed through the GitHub Release `v0.5.0-evidence`.
- The release mapping is frozen in `configs/profiling/first_real_profiler_slice_ovh_gra9_rtx5000_28.artifacts.json`.

## Measured Follow-On Package

- Repeat ROI results: `docs/reports/remote_repeat_roi_results_blocked.md`
- Diagnostic NCU and CUDA Graphs results: `docs/reports/remote_ncu_and_graphs_results_blocked.md`
- CUDA-Q adapter and tiny-MNK sidecar results: `docs/reports/remote_cudaq_and_sidecar_results_blocked.md`
- Portfolio package index: `docs/reports/portfolio_index.md`
