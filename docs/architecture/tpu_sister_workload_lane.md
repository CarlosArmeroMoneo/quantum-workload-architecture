# TPU Sister Workload Lane

Status: roadmap.

The TPU lane is a future JAX/XLA sister-workload lane. It is not an implementation in the current repository.

## Intent

- Build JAX workloads that resemble selected tensor-shape and contraction-pressure patterns.
- Capture XLA compilation and execution evidence.
- Compare bottleneck families at the architecture level without claiming direct cuTensorNet parity.

## Non-Claims

- No TPU runtime is implemented today.
- No TPU evidence is pinned today.
- TPU results must not be presented as quantum tensor-network throughput unless a future implementation proves that path directly.
