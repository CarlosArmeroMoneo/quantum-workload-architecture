# How To Review This Project

Quantum Workload Atlas is a measurement and execution-workflow project. Start with a result, then follow its source files; the full documentation catalog is optional.

## If You Have 3 Minutes

Read the [project overview](../../PROJECT_OVERVIEW.md) and the [measured results](measured_results.md). There are two distinct examples: a profiler-backed overhead nomination and a warm session-invocation improvement. Check what each number measures before interpreting it as a speedup.

## If You Have 10 Minutes

Open the [canonical execution payload](../../evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.execution.json), [profile summary](../../evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.profile_summary.json), and [architecture output](../../evidence/first_real_profiler_slice/real_dense_ring6_batched.arch.json). Confirm that their run and profile IDs match. Recalculate the setup share from the recorded phases; do not use whole wall time as the denominator.

Next inspect the [session summary](../../artifacts/session_runner/ovh_session_runner_prototype_v1/summary.json). Compare `same_workload_medians`, check `fallback_count` and the drift checks, and distinguish warm requests from worker startup. Read the [evidence contract](../architecture/evidence_contract.md) and [profiler signal taxonomy](../architecture/profiler_signal_taxonomy.md) for the terminology.

## If You Have 30 Minutes

Run the [CPU quickstart](../../README.md#cpu-quickstart). Its output is a plan JSON, not a GPU timing result. Run the non-GPU tests and inspect the [CI workflow](../../.github/workflows/cpu-smoke.yml) to see which dependency combinations are checked.

Read the [OVH rerun guide](../runbooks/ovh_cu13_real_execution.md) before attempting a GPU reproduction. Inspect the [calibration table](model_calibration_table.md), [calibration report](model_calibration_current_evidence.md), and the recorded `probe_fail` in the canonical payload. The [documentation index](../README.md) links the remaining experiments.

## Claim Boundaries

OVH RTX 5000 remains the canonical first real profiler-backed architecture slice. GCP A100 remains pending until confirmed A100 artifacts are pinned and accepted. GHZ3 is a tiny portability/calibration case, not a throughput benchmark. CUDA-Q is adapter-backed structural planning only. Local NVIDIA 6GB is preflight/dev only; H100, distributed GPU, TPU, and QPU results are not established by this public package.

A successful CPU check establishes workflow behavior. A matching historical artifact establishes a recorded observation. Neither alone establishes a generally optimal backend, a kernel speedup, or quantum advantage.
