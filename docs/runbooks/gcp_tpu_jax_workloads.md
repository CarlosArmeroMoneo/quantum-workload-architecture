# GCP TPU JAX Workloads

Status: future-only runbook.

This runbook defines how a future TPU lane would be operated for JAX/XLA sister workloads. It does not provision TPU resources, import JAX, execute workloads, or create accepted evidence today. The lane is not cuQuantum on TPU.

## Future Setup

- Start from the roadmap system template `configs/systems/gcp_tpu_v6e.yml`.
- Use placeholder workload manifests under `workloads/tpu_sister_workloads/`.
- Install JAX/XLA only in a future TPU environment; this repository does not require JAX today.
- Keep the GPU/cuQuantum/Nsight lane separate from TPU/XLA artifacts.
- Record device identity, XLA backend, software versions, and shape signatures before collecting measurements.

## Placeholder Workloads

- `workloads/tpu_sister_workloads/jax_batched_contract.yaml`
- `workloads/tpu_sister_workloads/jax_compile_vs_execute.yaml`

These are design placeholders, not executable Atlas workload manifests.

## Expected Artifacts

Future accepted TPU evidence should include:

- TPU execution payload using a TPU-specific schema such as `qwa.tpu_execution.v1`.
- workload manifest snapshot.
- system manifest snapshot.
- XLA/HLO or equivalent compilation artifact if available.
- timing summary with `compile_time_s`, `first_execute_s`, and `steady_iter_ms`.
- shape metadata with `shape_signature`, `batch_size`, `xla_backend`, and `device_type`.
- memory estimate if available.
- cost summary if later available.
- pinned artifact manifest with concrete paths.

## Acceptance Criteria

- The run uses a real TPU device and records `device_type=TPU`.
- The execution backend is JAX/XLA, not cuQuantum.
- The payload reports compile, first-execute, and steady-iteration timings.
- The result is described as a sister-workload structural comparison only.
- Artifacts are concrete and pinned.
- The result does not claim QPU execution, TPU quantum simulation throughput, or backend equivalence with cuTensorNet.

## Limitations

- No TPU runtime is implemented in this repository.
- No TPU artifact is pinned or accepted today.
- No JAX dependency is required today.
- No cost or quota policy is implemented beyond storage lifecycle placeholders.
- TPU results would not replace the OVH RTX 5000 canonical GPU/cuQuantum profiler slice.

## Cost And Quota Caveat

TPU experiments can incur material cloud cost and quota delays. Future runs should start with one small placeholder workload, a fixed maximum wall time, and a cleanup step that deletes resources after completion. Do not run broad sweeps before a single TPU case produces reviewable artifacts.

## No Current Evidence Claim

This lane is future-only. It exists to define the evidence shape for future XLA/TPU sister workloads. It is not current TPU evidence, not cuQuantum on TPU, and not a QPU implementation.
