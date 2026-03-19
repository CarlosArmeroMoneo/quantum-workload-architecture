# OVH CUDA 13 Real Execution

## Purpose

Use this runbook to reproduce the canonical profiler-backed slice on the OVH Ubuntu 24.04 RTX 5000 host.

## Host Roles

- Local Windows + WSL2 + RTX 4050: development and negative-control profiling host.
- OVH Ubuntu 24.04 + Quadro RTX 5000: canonical public evidence host.

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

## Public Evidence Layout

- Curated summaries are tracked in `evidence/first_real_profiler_slice/`.
- Raw profiler binaries are distributed through the GitHub Release `v0.5.0-evidence`.
- The release mapping is frozen in `configs/profiling/first_real_profiler_slice_ovh_gra9_rtx5000_28.artifacts.json`.
