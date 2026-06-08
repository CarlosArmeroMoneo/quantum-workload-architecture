# TPU Sister Workload Lane

Status: future-only design.

The TPU lane is a future JAX/XLA sister-workload lane. It is not implemented evidence in the current repository, and it is not cuQuantum on TPU. The current accepted evidence remains the GPU/cuQuantum lane, with OVH RTX 5000 as the canonical first real profiler-backed architecture slice.

## Intent

- Define JAX/XLA workloads that resemble selected tensor-shape, batching, and compile-vs-execute pressure points.
- Capture XLA compilation and execution evidence only after a future TPU environment exists.
- Compare workload structure and architecture signals conceptually, not as backend-equivalent cuTensorNet results.
- Keep TPU evidence separate from GPU Nsight/cuQuantum evidence.

## Lane Separation

- GPU lane: Qiskit/OpenQASM2 exact-TN workloads, real cuQuantum execution where implemented, Nsight Systems/Compute artifacts, and architecture nominations.
- TPU lane: future JAX/XLA sister workloads with shape-stable tensor operations and XLA timing artifacts.
- QPU lane: not implemented; QPU access remains future-only and outside this TPU design.

The TPU lane must never be described as cuQuantum running on TPU. A future TPU result can support structural comparison only after its own execution payload, metrics, artifacts, and acceptance notes are pinned.

## Placeholder Workload Families

- JAX batched tensor contraction.
- JAX compile-vs-execute repeated-shape benchmark.
- Optional future JAX local Hamiltonian or trotter-like step.

Current placeholder manifests:

- `workloads/tpu_sister_workloads/jax_batched_contract.yaml`
- `workloads/tpu_sister_workloads/jax_compile_vs_execute.yaml`

## Suggested TPU Metrics

- `compile_time_s`
- `first_execute_s`
- `steady_iter_ms`
- `shape_signature`
- `batch_size`
- `xla_backend`
- `device_type`
- `memory_estimate_gb` if available
- `cost_usd` if later available

## TPU Execution Payload Schema

Future TPU execution payloads should use a separate schema such as `qwa.tpu_execution.v1`:

```yaml
api_version: qwa.tpu_execution.v1
status: success
lane: tpu_sister_workload
workload_id: tpu_jax_batched_contract
system_name: gcp_tpu_v6e
execution_backend: jax_xla
device_type: TPU
xla_backend: tpu
shape_signature: batch=...,lhs=...,rhs=...
batch_size: 0
metrics:
  compile_time_s: null
  first_execute_s: null
  steady_iter_ms: null
  memory_estimate_gb: null
artifacts:
  execution_payload: null
  xla_hlo: null
  profiler_trace: null
claim_boundary:
  future_only: true
  not_cuquantum_on_tpu: true
  not_qpu_execution: true
```

The payload should not reuse GPU `execution_source=cuquantum_tensornet_gpu`, Nsight profile fields, or A100 acceptance classes.

## Acceptance Boundary

Before any TPU result becomes accepted evidence:

- A real TPU device identity and XLA backend must be recorded.
- Compile time, first execution, and steady iteration metrics must be present.
- Artifacts must use concrete pinned paths.
- The result must state that comparisons are conceptual/workload-structural, not backend-equivalent.
- The public docs must still state that TPU work is future-only until those artifacts exist.

## Non-Claims

- No TPU runtime is implemented today.
- No JAX dependency is required by this repository today.
- No TPU evidence is pinned today.
- No cuQuantum-on-TPU path exists.
- No QPU provider adapter or QPU execution evidence is implemented.
- TPU results must not be presented as quantum tensor-network throughput unless a future implementation proves that path directly.
