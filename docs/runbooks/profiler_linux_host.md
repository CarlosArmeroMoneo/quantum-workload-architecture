# Profiler-Capable Linux Host Runbook

## Purpose

Bring up one controlled Linux profiling node and close the first real profiler-backed exact-TN slice end to end.

Frozen slice definition:
- `configs/profiling/first_real_profiler_slice.yaml`
- Canonical host manifest: `configs/systems/ovh_gra9_rtx5000_28.yml`
- Canonical rerun guide: `docs/runbooks/ovh_cu13_real_execution.md`

## Freeze The Host

1. Copy `configs/systems/linux_profiler_node.template.yml` to a host-specific manifest in `configs/systems/`.
2. Fill in:
   - OS and kernel
   - NVIDIA driver version
   - GPU model and memory
   - container runtime version, if containers are used at all
   - canonical tool source for `nsys`, `QdstrmImporter`, and `ncu`
   - resolved executable paths for `nsys`, `QdstrmImporter`, and `ncu`
   - whether GPU performance counters are enabled
   - the actual launch user and capabilities used for profiling
   - the tracked readiness artifact path and session log path
3. Keep the profiler tool source fixed for the host you are freezing.
   - For the canonical OVH slice, all three tools are host-installed Ubuntu packages.
   - Do not mix container-bundled and host-installed profiler binaries within one blessed slice.
4. Record an image ref only if a container image is part of the execution path.
5. Validate the manifest before profiling:

```bash
python -m aqs manifest validate configs/systems/<host>.yml
```

## Gate On Readiness

Initialize the warehouse first if `benchmarks/warehouse/<host>.duckdb` does not already exist:

```bash
python -m aqs init-db --db benchmarks/warehouse/<host>.duckdb
```

Run this first and do not continue until it is green:

```bash
python -m aqs doctor \
  --profiling \
  --outdir artifacts/readiness/<host> \
  --out configs/systems/<host>.profiling_ready.json \
  --db benchmarks/warehouse/<host>.duckdb
```

Required result:
- `profiling_ready=true`
- `nsys.readiness_class=ready`
- `ncu.readiness_class=ready`
- do not continue on "tool present"; readiness must be green

## Smoke The Profilers

These runs are outside the quantum pipeline.

```bash
python -m aqs profile smoke --tool nsys --outdir artifacts/readiness/<host>/nsys
python -m aqs profile smoke --tool ncu --outdir artifacts/readiness/<host>/ncu
```

Required result:
- one usable `.nsys-rep`
- one usable `.ncu-rep`
- one persisted profiler-attempt record for each
- one non-empty parsed summary for each

Usable artifact definition for this milestone:
- Nsight Systems:
  - `.nsys-rep` exists
  - SQLite export or stats-backed summary succeeds
  - parsed summary is non-empty
- Nsight Compute:
  - `.ncu-rep` exists
  - at least one kernel is captured
  - parsed metrics summary is non-empty

## Profile One Tiny Amplitude Run

Use the frozen amplitude target:
- `workloads/manifests/imported/real_ghz3_amplitude.yaml`
- `precision=complex128`
- `planner_budget=balanced`
- `plan_rank=1`
- `measurement_repeats=2`
- `execution_intent=require_real`
- `allow_distributed=false`

If the host is not the canonical OVH node:
- use a host-specific successor slice file under `configs/profiling/`
- do not inherit old H100-only expectations for workspace or plan shape

```bash
python -m aqs profile nsys \
  --manifest workloads/manifests/imported/real_ghz3_amplitude.yaml \
  --system-manifest configs/systems/<host>.yml \
  --measurement-repeats 2 \
  --execution-intent require_real \
  --planner-budget balanced \
  --plan-rank 1 \
  --no-allow-distributed \
  --outdir artifacts/profiles/<host>/nsys \
  --db benchmarks/warehouse/<host>.duckdb
```

Required result:
- `execution_source=cuquantum_tensornet_gpu`
- usable `.nsys-rep`
- SQLite/stats exports succeed
- NVTX ranges are visible for the exact-TN phases
- a real `profile_summary` row is written

## Profile One Tiny Batched-Amplitude Run

Use the frozen batched target:
- `workloads/manifests/imported/real_dense_ring6_batched.yaml`
- `precision=complex128`
- `planner_budget=balanced`
- `plan_rank=1`
- `measurement_repeats=2`
- `execution_intent=require_real`
- `allow_distributed=false`

```bash
python -m aqs profile ncu \
  --manifest workloads/manifests/imported/real_dense_ring6_batched.yaml \
  --system-manifest configs/systems/<host>.yml \
  --measurement-repeats 2 \
  --execution-intent require_real \
  --planner-budget balanced \
  --plan-rank 1 \
  --no-allow-distributed \
  --outdir artifacts/profiles/<host>/ncu \
  --db benchmarks/warehouse/<host>.duckdb
```

Required result:
- usable `.ncu-rep`
- at least one kernel is captured
- parsed metrics summary is non-empty
- a real `profile_summary` row is written

## Re-run Architecture Analysis

Run:

```bash
python -m aqs arch analyze-execution --payload artifacts/profiles/<host>/ncu/<payload>.json
```

Minimal success condition:
- at least one nomination has `nomination_source=real_profiler_analysis`

Only after this should you widen the slice.

Historical note:
- the WSL2 RTX 4050 host remains a negative-control and debugging record
- the container-bundled H100 draft is no longer the canonical first profiler-backed slice in this repo
