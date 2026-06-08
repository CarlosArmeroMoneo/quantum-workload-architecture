# Local 6GB NVIDIA Preflight Runbook

Status: local preflight only.

This lane is for cheap environment, manifest, and tiny-workload checks before spending cloud GPU time. It is not a canonical performance lane and cannot replace the OVH profiler-backed slice or satisfy the GCP A100 gate.

## Confirm Device Identity

Run:

```bash
nvidia-smi --query-gpu=name,memory.total,compute_cap --format=csv
```

Record the exact reported name, total memory, driver version, and compute capability in a host-specific local note if needed. Keep the public template named `local_nvidia_laptop_6gb` until the device identity is confirmed.

## Expected Uses

- Validate the local Python and CUDA/cuQuantum environment.
- Parse and validate system/workload manifests.
- Run tiny real execution only when the local stack supports it.
- Smoke-test profiler discovery and artifact parsers.
- Catch missing dependencies before using OVH, Hyperstack, or GCP budget.

## Not Expected

- Medium exact-TN profiling.
- Throughput conclusions.
- Canonical profiler-backed architecture results.
- A100 portability acceptance.
- Replacement of the accepted OVH RTX 5000 evidence.

## Local Probe

The optional probe is offline and has no cloud side effects:

```bash
bash scripts/local_gpu_probe.sh
```

The script checks `nvidia-smi`, lightweight Python imports, and the local `aqs doctor` command when available. Missing optional tools should be treated as preflight findings, not public evidence.

## Evidence Boundary

Local 6GB results may be Tier 0 or Tier 1 only unless manually reviewed and promoted under a separate evidence contract. They must not be used for public performance claims, A100 acceptance, or canonical architecture nomination.

Use `configs/systems/local_nvidia_laptop_6gb.template.yml` as a template. If a real local run is kept, create a local or scratch artifact outside the public evidence path unless it has been reviewed for claim safety.
