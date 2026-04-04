# Current State Truth Pass

This report freezes the public scope of the repository as of April 4, 2026.

The rule for this document is simple: schema breadth is allowed to be wider than executable support, but README claims must follow executable support and measured evidence rather than the full ontology.

## Capability Matrix

| Area | Manifest/schema allows | Actually implemented | Real measured evidence exists | Proof file | Claim allowed in README |
| --- | --- | --- | --- | --- | --- |
| Manifest ontology | `qiskit`, `cirq`, `stim`, `cudaq`, `normalized_ir`; broad semantic targets including `samples` and `detectors` | Broad schema only; executable implementation is narrower | N/A | This report | Talk about ontology breadth only as vocabulary |
| Normalize + features | All workload manifests | `qiskit` OpenQASM2 imports, adapter-backed `cudaq` manifests, and family-backed `normalized_ir` manifests | Yes | [`docs/reports/first_real_profiler_slice_index.md`](docs/reports/first_real_profiler_slice_index.md) | Claim deterministic normalization for implemented source paths only, and call CUDA-Q adapter-backed |
| Structural probe + planner | Any benchmark/workload combination | `qiskit`, adapter-backed `cudaq`, or supported `normalized_ir` families with `state`, `amplitude`, `batched_amplitudes`, `expectation` | Yes | [`docs/reports/first_real_profiler_slice_index.md`](docs/reports/first_real_profiler_slice_index.md) | Claim exact-TN planning for the implemented subset only, and keep CUDA-Q marked adapter-backed |
| Real cuTensorNet execution | Any manifest can declare real intent | Single-GPU `qiskit` workloads for `amplitude` and `batched_amplitudes` only | Yes | [`evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.execution.json`](../../evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.execution.json) | Claim real measured execution only for this single-GPU Qiskit/OpenQASM2 path |
| Profiler reduction | Profiler metadata can be attached to runs | Nsight Systems reduction is mature; Nsight Compute reduction exists but remains metrics-thin | Yes | [`evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.profile_summary.json`](../../evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.profile_summary.json) | Claim real profiler-backed summaries and call out NCU limits |
| Architecture nominations | Any profiled run can be analyzed | Profiler-backed nominations for launch/setup, memory bandwidth, reuse, planner ROI, capacity, and communication | Yes | [`docs/reports/first_real_profiler_slice_index.md`](docs/reports/first_real_profiler_slice_index.md) | Claim measured nomination reasoning, not exhaustive diagnosis |

## Implemented Validation Modes

`python -m aqs manifest validate` now has three modes:

- `schema`: structural YAML validation only.
- `implemented`: rejects workload combinations that the repo does not implement end to end today.
- `real`: rejects workload combinations that the real single-GPU cuTensorNet executor does not support.

That means examples such as `source_format='cirq'`, `source_format='stim'`, or unsupported semantic targets can remain in the ontology without being misrepresented as executable, while `source_format='cudaq'` is now handled only through the adapter-backed path described below.

## Explicit Limits

- `cirq` and `stim` remain schema vocabulary only in the current branch.
- `cudaq` is adapter-backed for normalization and structural planning, but it does not yet have separate measured CUDA-Q execution evidence.
- `samples`, `detectors`, and `syndrome_summary` remain schema vocabulary only for the execution path.
- Family-backed `normalized_ir` execution is currently limited to `dense_universal`, `qaoa_graph`, `trotter_1d`, and `grid_2d_shallow`.
- Real measured execution is currently limited to the single-GPU Qiskit/OpenQASM2 path for `amplitude` and `batched_amplitudes`.
- Nsight Compute summaries are real, but the reduction path is still thinner than the Nsight Systems path and should be described that way.

## Evidence That Supports Public Claims

- Canonical evidence index: [`docs/reports/first_real_profiler_slice_index.md`](docs/reports/first_real_profiler_slice_index.md)
- Canonical `nsys` execution payload: [`evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.execution.json`](../../evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.execution.json)
- Canonical `ncu` profile summary: [`evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.profile_summary.json`](../../evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.profile_summary.json)
- Measured repeat-ROI report: [`docs/reports/remote_repeat_roi_results_blocked.md`](docs/reports/remote_repeat_roi_results_blocked.md)
- Measured NCU and CUDA Graphs report: [`docs/reports/remote_ncu_and_graphs_results_blocked.md`](docs/reports/remote_ncu_and_graphs_results_blocked.md)
- Measured CUDA-Q adapter and sidecar report: [`docs/reports/remote_cudaq_and_sidecar_results_blocked.md`](docs/reports/remote_cudaq_and_sidecar_results_blocked.md)

## README Claim Policy

The README may claim:

- reproducible manifest to planning to execution flow for the implemented subset,
- real profiler-backed evidence on the canonical OVH host,
- measured nomination reasoning grounded in tracked summaries and release assets.

The README must not claim:

- end-to-end Cirq, Stim, or CUDA-Q support,
- direct real execution for semantic targets outside `amplitude` and `batched_amplitudes`,
- multi-GPU or distributed measured results,
- deeper NCU architectural coverage than the current reduction actually exports.
