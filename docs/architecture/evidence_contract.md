# Evidence Contract

This contract defines what public Atlas claims mean. Every result should state an evidence tier and avoid implying stronger evidence than the artifacts support.

## Evidence Tiers

| Tier | Name | Minimum Evidence | Allowed Claim |
| --- | --- | --- | --- |
| Tier 0 | structural/synthetic | Workload manifest, normalization, probe, dry-run, or synthetic analysis only | Planning feasibility, schema coverage, or expected execution path |
| Tier 1 | real execution | Real backend execution succeeded, timing payload exists, and correctness checks pass | Real execution on the stated host/backend |
| Tier 2 | real profiler-backed | Tier 1 plus Nsight artifact capture and reduced profile summary | Profiler-backed execution and workload signal interpretation |
| Tier 3 | architecture nomination | Tier 2 plus bottleneck nomination from measured profile/runtime evidence | Architecture-facing bottleneck hypothesis and next experiment |

## Current Public Classification

- OVH `real_dense_ring6_batched`: Tier 3. It has real `cuquantum_tensornet_gpu` execution, a tracked Nsight Compute summary, and a `launch_overhead` nomination from `real_profiler_analysis`.
- OVH GHZ3 amplitude: Tier 3 for evidence mechanics, but tiny-workload caveats must stay attached. It is not a throughput benchmark.
- GCP A100 GHZ3 lane: pending. Once a confirmed A100 40GB host passes the acceptance gate, the intended claim is Tier 2 portability/calibration, not throughput.
- WSL2 RTX4050 host: negative-control and dev-host readiness evidence. It should not be used as the public architecture result.
- Rejected local GCP draft: no A100 tier. Its device was L4, so it cannot support A100 claims.

## Required Public Wording

- State the host, backend, profiler, and tier.
- Distinguish portability validation from performance calibration.
- Keep tiny-workload warnings visible.
- Do not claim CUDA-Q runtime evidence; current CUDA-Q support is adapter-backed structural planning only.
- Do not claim TPU evidence; current TPU work is a sister-workload roadmap.
