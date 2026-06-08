# Accelerator Lab Architecture

Status: roadmap.

Quantum Workload Atlas is structured around an evidence ladder:

`static probe -> real execution -> profiler artifacts -> profile summary -> architecture nomination`

The current proven lane is the OVH single-GPU exact tensor-network path. Future accelerator-lab lanes should preserve the same evidence ladder before making public claims.

## Lanes

- GCP GPU sweeps: future Compute Engine or Batch orchestration for repeated GPU profiler captures.
- TPU sister workloads: future JAX/XLA workloads that mirror selected tensor-network pressure points without claiming cuTensorNet equivalence.
- QPU adapter surface: future optional integration layer for submitted quantum hardware jobs and returned evidence payloads.

## Claim Policy

- Do not describe Batch, TPU, or QPU lanes as implemented until executable code, runbooks, artifacts, and tests exist.
- Keep raw cloud identifiers and credentials out of git.
- Publish only pinned artifact manifests with concrete paths.
- Keep OVH as the canonical first profiler-backed exact-TN architecture slice until a later slice is explicitly promoted.
