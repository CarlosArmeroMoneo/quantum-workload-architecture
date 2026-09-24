# Public Release Audit

Status: public scope and validation checklist. The current reading path is the [project overview](../../PROJECT_OVERVIEW.md), [measured results](measured_results.md), and [review guide](how_to_review_this_project.md). Historical GPU measurements are not rerun by this audit.

## Accepted Evidence

- OVH RTX 5000 remains the canonical first real profiler-backed architecture slice.
- The canonical workload is `real_dense_ring6_batched`, using the implemented single-GPU Qiskit/OpenQASM2 cuTensorNet path.
- The accepted architecture nomination is `launch_overhead` from `real_profiler_analysis`. Its 21.86% setup share uses recorded phase time, not whole wall time or measured savings.
- The canonical NCU capture lacks occupancy, SM-utilization, and DRAM-utilization counters. Instrumented execution timings supply its phase breakdown.
- The separate session-runner experiment records a warm per-request wall-time improvement on three OVH workloads; startup is excluded from those medians.
- GHZ3 is a tiny portability/calibration case, not a throughput benchmark.

## Pending Or Future Work

- GCP A100 remains pending until a confirmed A100 host produces pinned artifacts that pass the offline acceptance gate.
- The GCP Batch renderer is dry-run only. It renders job JSON and does not call Cloud Batch.
- The TPU/JAX sister lane remains future-only. It is for shape-stable JAX/XLA workloads, not cuQuantum on TPU.
- QPU access is not implemented.
- CUDA-Q remains adapter-backed for normalization and structural planning only; this repository does not claim measured native CUDA-Q execution.
- H100, distributed GPU, and Hyperstack results are not established by the accepted evidence in this public package.

## Release And Naming

The project is Quantum Workload Atlas, the repository is `quantum-workload-architecture`, and the package/CLI is `aqs`. The latest project release is `v0.2-crossover-calibration`, published June 8, 2026. `v0.1-first-real-profiler-slice` packages the earlier accepted slice; `v0.5.0-evidence` is a historical raw-artifact tag, not a newer project release.

## Artifact Hygiene

Canonical small summaries are tracked in `evidence/first_real_profiler_slice`. Selected experiment records are also tracked under `artifacts/`; most rerun outputs remain ignored. Heavy profiler binaries are release assets or external artifacts. Frozen package checksums apply to the corresponding original package, not changing documentation on `main`.

Pinned evidence uses concrete paths. Cloud credentials, private host details, quota notes, and scratch artifacts must stay outside the tracked public tree. The rejected GCP draft captured NVIDIA L4 and is not A100 evidence.

Automatic adjacent-profile discovery now requires a matching, nonempty execution run ID. Explicitly supplied profiles with a conflicting run ID raise an analysis error. This prevents an unrelated adjacent capture from being attached to the reviewed execution. It is not a claim of a complete provenance or security audit; legacy directly supplied summaries without a run ID retain their existing API behavior.

## Presentation Review — September 24, 2026

The review started from public commit `7ac9dfd5dcc900e3e30966b1259149dbccc797c9`. It checked the public reading path, release records, selected source paths, tests, and the small stored artifacts supporting the showcased results. It did not rerun GPU captures, download and hash the heavyweight release archives, or audit every historical document and commit.

Changes clarify the release hierarchy, naming, metric denominators, real versus planned support, and warm versus cold timing. The capability snapshot has corrected document-relative links. Tests check local links on the edited reading path, recompute the result-card numbers from tracked JSON, exercise the documented CPU workflow, and cover profile-association errors. Historical measurements, release tags, and planner ranking rules are unchanged.

The canonical payload's `probe_fail`, sparse NCU counters, and substantial prediction errors remain visible. Public documents describe an engineering project, not a general fastest-backend advisor or a claim of quantum advantage.

## Validation Commands

```bash
python -m pytest tests/test_public_methodology_docs.py tests/test_public_presentation.py tests/test_arch_provenance.py -q
python -m pytest -m "not gpu and not profiler" -q
python -m ruff check src tests scripts
python -m mypy src/aqs
bash scripts/public_check.sh
```

CI results, not this checklist, determine whether a particular revision passes. The documentation checks cover the edited reading path and local file targets; they do not certify every external URL, Markdown anchor, or historical artifact.
