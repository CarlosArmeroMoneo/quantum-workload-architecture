# v0.1 First Real Profiler-Backed Slice

## Summary

This release packages Quantum Workload Atlas as a public evidence system around the first real profiler-backed exact-TN architecture slice.

## Public Anchor

- Canonical result: OVH RTX 5000 `real_dense_ring6_batched`.
- Evidence tier: Tier 3 architecture nomination.
- Backend: `cuquantum_tensornet_gpu`.
- Profiler: Nsight Compute reduced into a tracked profile summary.
- Nomination: `launch_overhead` from `real_profiler_analysis`.
- Setup share: about `21.86%` on the canonical batched run.

## Included Public Surfaces

- README front door and portfolio landing page.
- Evidence contract and profiler signal taxonomy.
- Public evidence catalog with prediction-error ratios.
- Model calibration report from accepted evidence only.
- Review guide and evidence-methodology documentation.
- Future GCP templates and acceptance gate without claiming A100 evidence.

## Boundaries

- GCP A100 evidence remains pending until a confirmed A100 host produces pinned artifacts.
- GHZ3 remains a tiny-workload portability/calibration case, not a throughput benchmark.
- CUDA-Q is adapter-backed for structural planning only.
- TPU work is roadmap-only.

## Validation

The release package should pass:

```bash
python -m pytest -m "not gpu and not profiler" -q
bash scripts/public_check.sh
```
