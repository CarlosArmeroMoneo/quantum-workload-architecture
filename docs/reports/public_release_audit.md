# Public Release Audit

Status: current public-readiness audit for the no-GPU methodology package.

This audit checks whether the repository reads as a standalone technical evidence system. The public surface should emphasize measured artifacts, claim boundaries, reproducible validation, and future gates. It should not use vague promotional language or imply evidence that is not pinned.

## Accepted Evidence

- OVH RTX 5000 remains the canonical first real profiler-backed architecture slice.
- The canonical workload is `real_dense_ring6_batched`.
- The accepted execution path is real `cuquantum_tensornet_gpu` for the implemented single-GPU Qiskit/OpenQASM2 exact-TN path.
- The accepted profiler evidence is reduced from Nsight Systems and Nsight Compute summaries.
- The accepted architecture nomination is `launch_overhead` from `real_profiler_analysis`.
- GHZ3 evidence is portability/calibration support only. It is not a throughput benchmark.

## Pending Or Future Work

- GCP A100 remains pending until a confirmed A100 host produces pinned artifacts that pass the offline acceptance gate.
- The GCP Batch renderer is dry-run only. It renders job JSON and does not call Cloud Batch.
- The TPU/JAX sister lane remains future-only. It is for shape-stable JAX/XLA workloads, not cuQuantum on TPU.
- QPU access is not implemented.
- CUDA-Q remains adapter-backed for normalization and structural planning only; this repository does not claim measured native CUDA-Q execution.

## Artifact Hygiene

- Canonical small summaries are tracked in `evidence/first_real_profiler_slice`.
- Heavy profiler binaries remain release assets or externally synchronized artifacts; the public repo keeps summaries and references.
- Pinned artifact paths must be concrete. Wildcard artifact paths are acceptable only in search commands or glob inputs, not as pinned evidence.
- Cloud credentials, private host details, local quota notes, and scratch artifacts must stay outside the tracked public tree.
- The ignored local GCP draft that captured `NVIDIA L4` is not A100 evidence.

## Public-Language Check

- The top-level framing is technical: workload manifests, exact-TN planning, cuTensorNet execution, Nsight reduction, evidence tiers, calibration, and architecture nominations.
- Reader-facing docs avoid broad hype and generic promotional phrasing.
- Private positioning notes stay outside the tracked public tree.
- Vendor names are used only for technical context: device models, accelerator families, toolchains, profiler tools, and cloud resources.

## What Changed Since v0.1

- Added an offline GCP A100 acceptance gate for candidate artifact sets.
- Added a profiler kernel taxonomy report that normalizes raw Nsight kernel names into workload-level families.
- Added experiment-card templates and a launch-overhead counterfactual card.
- Added dry-run GCP Batch job rendering without credentials or cloud side effects.
- Added a future-only TPU/JAX sister-workload lane.
- Added this audit to keep public claims aligned with accepted evidence.

## Validation Commands

```bash
python -m pytest tests/test_public_methodology_docs.py -q
python -m pytest -m "not gpu and not profiler" -q
python -m mypy src/aqs
bash scripts/public_check.sh
```

## Audit Result

Pass criteria:

- OVH remains the canonical accepted profiler-backed architecture slice.
- GCP A100 remains acceptance-gated and pending.
- TPU, QPU, and native CUDA-Q execution remain future or unsupported where appropriate.
- No pinned artifact path uses unresolved wildcard evidence.
- Public docs read as a technical project record, not a promotional pitch.
