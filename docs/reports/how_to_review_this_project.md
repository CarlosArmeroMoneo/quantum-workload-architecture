# How To Review This Project

Quantum Workload Atlas is best reviewed as an evidence system, not as a generic quantum demo.

## If You Have 3 Minutes

- Read `README.md`.
- Read `PROJECT_OVERVIEW.md`.
- Look for the main result: OVH RTX 5000, real `cuquantum_tensornet_gpu`, Nsight evidence, and a `launch_overhead` architecture nomination.

## If You Have 10 Minutes

- Read `docs/reports/first_real_profiler_slice_index.md`.
- Check `docs/architecture/evidence_contract.md` to see why the OVH batched case is the canonical Tier 3 result and why GCP A100 remains pending.
- Check `docs/architecture/profiler_signal_taxonomy.md` to see how profiler signals are grouped before architecture analysis.

## If You Have 30 Minutes

- Inspect `docs/runbooks/ovh_cu13_real_execution.md`.
- Inspect `docs/reports/model_calibration_current_evidence.md`.
- Inspect `docs/reports/model_calibration_table.md`.
- Inspect the tracked profiler summaries in `evidence/first_real_profiler_slice/`.

## Claim Boundaries

- OVH RTX 5000 remains the canonical first real profiler-backed architecture slice.
- GCP A100 remains pending until confirmed A100 artifacts are pinned.
- GHZ3 is useful for portability/calibration, not throughput benchmarking.
- CUDA-Q is adapter-backed structural planning only in this repo.
- TPU and QPU lanes are future-only.
