# Quantum Workload Architecture

Quantum Workload Architecture is a Python toolkit for deciding which exact tensor-network plan to run for a quantum workload on a real machine, and for showing what actually bottlenecks that run.

The repo takes workloads from normalized manifests through planning, real `cuTensorNet` execution, profiler reduction, and architecture analysis, with the supporting artifacts either tracked in git or linked from a pinned release.

## What It Shows

- A workload can be normalized, probed, planned, and executed through one reproducible CLI flow.
- The architecture recommendations come from measured Nsight data, not synthetic scoring alone.
- Small summaries stay in git, while large profiler artifacts are published through a pinned release.

## Result Snapshot

| Signal | Value | Evidence |
| --- | --- | --- |
| Canonical host | OVH Ubuntu 24.04, Quadro RTX 5000, host-installed `nsys` / `QdstrmImporter` / `ncu` | [OVH session summary](docs/runbooks/profiler_ovh_gra9_rtx5000_28_session.md) |
| Evidence source | Real `cuTensorNet` execution with profiler-backed artifact reduction | [Evidence index](docs/reports/first_real_profiler_slice_index.md) |
| First architecture nomination | `nomination_source=real_profiler_analysis` | [Public evidence index](docs/reports/first_real_profiler_slice_index.md) |
| Bottleneck family | `launch_overhead` | [Public evidence index](docs/reports/first_real_profiler_slice_index.md) |
| Setup share | `21.86%` on the canonical batched run | [Public evidence index](docs/reports/first_real_profiler_slice_index.md) |
| Reproducibility path | Canonical rerun guide and pinned release assets | [OVH rerun guide](docs/runbooks/ovh_cu13_real_execution.md), [release `v0.5.0-evidence`](https://github.com/CarlosArmeroMoneo/quantum-workload-architecture/releases/tag/v0.5.0-evidence) |

![Canonical profiler-backed architecture snapshot](docs/reports/assets/first_real_profiler_slice_canonical.svg)

Frozen March 14, 2026 snapshot for the canonical `real_dense_ring6_batched` run. The left panel is normalized from `execution_run.failure_detail_json.phase_times` in the [public evidence index](docs/reports/first_real_profiler_slice_index.md), using the tracked [batched execution payload](evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.execution.json); the right panel shows the matching primary nomination from the tracked [batched architecture output](evidence/first_real_profiler_slice/real_dense_ring6_batched.arch.json).

## Capability Matrix

This table is the compact truth pass for public claims. The longer audit lives in [docs/reports/current_state_truth_pass.md](docs/reports/current_state_truth_pass.md).

| Area | Manifest/schema allows | Actually implemented | Real measured evidence exists | Proof file | Claim allowed in README |
| --- | --- | --- | --- | --- | --- |
| Manifest ontology | `qiskit`, `cirq`, `stim`, `cudaq`, `normalized_ir`; broad semantic targets | Broad schema only; executable implementation is narrower | N/A | [Truth pass report](docs/reports/current_state_truth_pass.md) | Describe breadth as schema vocabulary, not working backend support |
| Normalize + features | All workload manifests | `qiskit` OpenQASM2 imports and family-backed `normalized_ir` manifests | Yes | [Profiler slice index](docs/reports/first_real_profiler_slice_index.md) | Claim deterministic normalization for implemented source paths only |
| Structural probe + planner | Any benchmark/workload combination | `qiskit` or supported `normalized_ir` families with `state`, `amplitude`, `batched_amplitudes`, `expectation` | Yes | [Profiler slice index](docs/reports/first_real_profiler_slice_index.md) | Claim exact-TN planning for the implemented subset only |
| Real cuTensorNet execution | Any manifest can declare real intent | Single-GPU `qiskit` workloads for `amplitude` and `batched_amplitudes` only | Yes | [Tracked `nsys` execution payload](evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.execution.json) | Claim real measured execution only for the single-GPU Qiskit/OpenQASM2 path |
| Profiler reduction | Profiler metadata can be attached to runs | Nsight Systems reduction is mature; Nsight Compute reduction exists but remains metrics-thin | Yes | [Tracked `ncu` profile summary](evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.profile_summary.json) | Claim real profiler-backed summaries and note NCU depth limits explicitly |
| Architecture nominations | Any profiled run can be analyzed | Profiler-backed nominations for launch/setup, memory bandwidth, reuse, planner ROI, capacity, and communication | Yes | [Profiler slice index](docs/reports/first_real_profiler_slice_index.md) | Claim measured nomination reasoning, not exhaustive diagnosis |

## 60-Second CPU Quickstart

The CPU path is meant to prove the end-to-end workflow without requiring Qiskit, CUDA, or Nsight.

```bash
python -m pip install -e .[dev,db]
python scripts/init_db.py --db benchmarks/warehouse/aqs.duckdb --schema benchmarks/warehouse/schema.sql

python -m aqs manifest validate \
  --mode implemented \
  workloads/manifests/generated/dense_universal_smoke.yaml \
  configs/systems/cpu_probe.yml

python -m aqs tnep probe \
  --manifest workloads/manifests/generated/dense_universal_smoke.yaml \
  --probe-strategy structural_real

python -m aqs tnep plan \
  --manifest workloads/manifests/generated/dense_universal_smoke.yaml \
  --system-manifest configs/systems/cpu_probe.yml \
  --probe-strategy structural_real \
  --out artifacts/plans/dense_universal_smoke.plan.json
```

This quickstart is a local smoke path. The headline public result comes from the canonical OVH CUDA 13 host, where real `cuTensorNet` execution and Nsight artifacts are captured and reduced into the evidence linked above. For imported QASM workflows or real GPU execution, install the `quantum` extra and use the runbooks below.

## Evidence Chain

```mermaid
flowchart LR
    A[Workload Manifest] --> B[Normalize + Features]
    B --> C[Exact-TN Probe]
    C --> D[Real cuTensorNet Execution]
    D --> E[Nsight Systems / Nsight Compute]
    E --> F[Architecture Nomination]
```

Public repo policy:

- Small curated summaries stay in [`evidence/first_real_profiler_slice`](evidence/first_real_profiler_slice).
- Heavy profiler binaries are published through the GitHub Release `v0.5.0-evidence`.
- Private host credentials are never stored in this repository.

## Technical Appendix

- Capability truth pass: [`docs/reports/current_state_truth_pass.md`](docs/reports/current_state_truth_pass.md)
- Public evidence index: [`docs/reports/first_real_profiler_slice_index.md`](docs/reports/first_real_profiler_slice_index.md)
- Repeat ROI foundation: [`docs/reports/repeat_roi_foundation.md`](docs/reports/repeat_roi_foundation.md)
- Canonical OVH rerun guide: [`docs/runbooks/ovh_cu13_real_execution.md`](docs/runbooks/ovh_cu13_real_execution.md)
- Canonical OVH session summary: [`docs/runbooks/profiler_ovh_gra9_rtx5000_28_session.md`](docs/runbooks/profiler_ovh_gra9_rtx5000_28_session.md)
- Generic profiler-host runbook: [`docs/runbooks/profiler_linux_host.md`](docs/runbooks/profiler_linux_host.md)
- Known local-host blockers: [`docs/known_limitations/profiler_host_blockers.md`](docs/known_limitations/profiler_host_blockers.md)

## Repository Notes

- The public project name is **Quantum Workload Architecture**; the stable Python package and CLI remain `aqs` for compatibility.
- Nsight Compute profiling now supports `python -m aqs profile ncu --profile-mode basic|diagnostic|deep`, backed by `configs/profiling/ncu_metric_sets.yaml`.
- Most of `artifacts/` and all of `release-assets/` are intentionally ignored so local reruns do not pollute the public tree. Small tracked truth-pass fixtures under `artifacts/truth_pass/` are the current exception.
- `ovh.conf.example` documents the expected OVH client shape. Real credentials must live outside git.
