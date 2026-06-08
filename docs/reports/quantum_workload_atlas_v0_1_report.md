# Quantum Workload Atlas v0.1 Report

## Problem Statement

Quantum tensor-network workloads do not map cleanly to one backend, one accelerator, or one optimization path. A small exact-TN amplitude request can be dominated by setup and launch overhead, while a larger batched contraction can shift toward planner, memory, or reuse behavior.

Quantum Workload Atlas is built as an evidence system for that ambiguity: normalize the workload, probe feasible exact-TN execution, plan candidate accelerator paths, execute real workloads when possible, reduce profiler artifacts, and turn the measured signal into architecture-facing recommendations.

## System Design

The current evidence ladder is:

```text
workload manifest -> normalize/features -> exact-TN probe -> plan -> real execution -> profiler report -> profile summary -> architecture nomination
```

The proven execution slice is single-GPU exact tensor-network execution through `cuquantum_tensornet_gpu` on the canonical OVH RTX 5000 host. The repo keeps heavy raw profiler binaries out of git and tracks curated execution, profile, and architecture summaries under `evidence/first_real_profiler_slice/`.

## Evidence Model

Atlas separates evidence classes instead of treating every benchmark row as equivalent:

- Synthetic or structural analysis: useful for planning and smoke tests, not public performance evidence.
- Real execution: a workload executed through a real backend with accuracy checks.
- Real profiler-backed execution: real execution plus Nsight reduction and architecture nomination.
- Portability validation: real execution on another host that checks toolchain/device behavior, not a throughput claim.

The current public result is profiler-backed. The GCP A100 lane is pending until a confirmed A100 40GB host produces pinned artifacts.

## Canonical OVH Result

The canonical public slice is OVH `ovh_gra9_rtx5000_28`: Ubuntu 24.04.3 LTS, Quadro RTX 5000, driver `580.126.09`, and host-installed Nsight tooling.

The headline architecture result is:

```text
real_dense_ring6_batched -> cuquantum_tensornet_gpu -> Nsight Compute summary -> launch_overhead nomination
```

The tracked architecture output reports `nomination_source=real_profiler_analysis` and `bottleneck_family=launch_overhead`. The nomination is grounded in measured phase timing: load/convert/postprocess setup contributes about `21.86%` of the canonical batched run.

The companion GHZ3 amplitude `nsys` slice is useful because it shows how tiny workloads can become dominated by one-time overhead and cold-vs-warm effects. It should not be sold as throughput evidence.

## Pending GCP A100 Lane

The A100 lane remains a future portability/profiler validation path. The accepted bar is documented in `configs/profiling/gcp_a100_portability_slice.yaml` and `docs/reports/gcp_a100_portability_index.md`.

A June 2026 local GCP draft used an L4-backed host. That draft is explicitly rejected as A100 evidence and must stay outside the public result set.

## Model Calibration

Current accepted evidence shows useful calibration gaps:

- GHZ3 amplitude is a tiny-workload case where measured times are far below planner predictions; it is useful for portability and overhead interpretation, not broad performance calibration.
- Dense ring6 batched is the canonical profiler-backed result, and the measured steady iteration is much slower than the initial model prediction. That gap is exactly why the repo should expose prediction-error tables instead of only claiming successful execution.

The next no-GPU analysis step is to keep those ratios visible in the public evidence catalog and warehouse marts.

## Limitations

- The accepted public GPU evidence is still a narrow OVH slice.
- GCP A100 has no approved pinned artifacts yet.
- Nsight Compute reduction is metrics-thin for the current tracked NCU file, although kernel capture is non-empty.
- CUDA-Q is adapter-backed for structural planning only; the repo does not claim native CUDA-Q runtime execution.
- TPU work is a sister-workload roadmap, not cuQuantum-on-TPU.

## Next Experiments

- Confirm A100 40GB identity, then run the pending GHZ3 portability/profiler lane.
- Add a medium exact-TN workload after the portability check, not before.
- Run Batch-managed sweeps only after the single-case GCP capture passes.
- Extend profiler taxonomy from raw kernel names into stable kernel-family evidence.
- Keep model-calibration summaries in docs and warehouse views so prediction gaps stay visible.
