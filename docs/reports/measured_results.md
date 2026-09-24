# Measured results and their limits

These are two separate experiments on the OVH Quadro RTX 5000 host. The first establishes a traceable profiling result; the second measures a warm execution-session change. They are not a single controlled before/after experiment and do not establish cross-device performance.

## 1. Canonical profiler-backed slice

The recorded run is `run_6e3b0bf4154a4a94`, workload `real_dense_ring6_batched`, captured March 14, 2026. The executor is `cuquantum_tensornet_gpu`, using `complex128` and one GPU.

| Recorded value | Result |
| --- | ---: |
| Load + conversion + postprocessing | 0.366781632 s |
| Sum of the six recorded phases | 1.677920655 s |
| Setup share of recorded phase time | `21.86%` |
| Whole execution wall time | 2.231213113 s |
| Maximum absolute batched-amplitude error | 3.227937720230791e-17 |
| Accuracy threshold | 1e-12 |

The percentage is calculated as:

```text
100 * (load_circuit + convert_to_einsum + postprocess)
    / sum(execution_run.failure_detail_json.phase_times.values())
```

Planning is included in the denominator, not the numerator. Whole-process wall time is a different denominator. The headline is neither a 21.86% wall-time reduction nor a measurement of kernel-launch latency alone.

The nomination `launch_overhead` comes from the rule-based analysis. The execution payload supplies the instrumented phase timings; the adjacent Nsight Compute summary identifies the real profile. Its own `nvtx_phase_times_json` is empty, and occupancy, SM utilization, and DRAM utilization are null. Those missing counters must not be inferred from the nomination label.

### Evidence and unresolved measurements

- [Execution payload](../../evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.execution.json): timings, accuracy, execution status, selected plan, and the run's embedded system manifest.
- [Profile summary](../../evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.profile_summary.json): profile `prof_ee9e809cca0bb5f2` and matching run ID.
- [Architecture output](../../evidence/first_real_profiler_slice/real_dense_ring6_batched.arch.json): matching run/profile IDs, nomination, and calculation.
- [Canonical evidence index](first_real_profiler_slice_index.md): raw release assets and rerun references.

The payload records `probe_fail` even though the later real execution and accuracy check succeed. It is not evidence that every upstream stage succeeded. Predicted time to first result is 0.480977 s versus 1.041988242 s observed; predicted steady iteration is 6.649115 ms versus 392.928316 ms observed. The corresponding observed/predicted ratios are `2.1664` and `59.0948`. These are measurements from the profiled run, which may include profiler distortion, not unprofiled throughput comparisons or proof of a calibrated cost model.

Use the embedded system manifest when interpreting this frozen capture. A later host configuration can differ; host names are not GPU-memory specifications. The recorded GPU model is Quadro RTX 5000, and `gpu_mem_gb` is 15.0 in this payload. The `28` in the host identifier is not a claim of 28 GB of GPU memory.

## 2. Warm session execution

The session-runner experiment compares a persistent warm CLI with a session that uses an existing worker. It retains the selected plan and execution semantics while reducing invocation overhead.

| Workload | Persistent warm CLI median (ms) | Existing-worker session median (ms) |
| --- | ---: | ---: |
| Dense ring6 amplitude | 659.080 | 52.429 |
| Star-graph phase amplitude | 672.209 | 56.204 |
| Parity IQP batched amplitudes | 653.156 | 51.414 |

The [machine-readable summary](../../artifacts/session_runner/ovh_session_runner_prototype_v1/summary.json) records 765 request rows across the benchmark package, zero fallbacks, unchanged ranking, and passing correctness/selected-plan drift checks. This is not 765 independent measurements per table row. The [per-request CSV](../../artifacts/session_runner/ovh_session_runner_prototype_v1/per_request.csv) and [experiment report](ovh_session_runner_prototype_v1.md) provide the broader record.

The comparison excludes cold worker startup. The report records approximately 1.137 s of one-time startup for the autospawn path. Warm per-request medians therefore must not be advertised as end-to-end cold-start latency. The experiment demonstrates a local request-path improvement on three cases, not a general cuTensorNet kernel speedup, a statistically characterized cross-system benchmark, or a planner-ranking improvement.

## Negative results worth retaining

The [CUDA Graphs experiment](remote_ncu_and_graphs_results_blocked.md) reports a capture failure rather than a graph speedup. The [calibration table](model_calibration_table.md) exposes prediction errors. The [CUDA-Q and sidecar report](remote_cudaq_and_sidecar_results_blocked.md) distinguishes adapter-backed planning and a separate shape-isolation lab from native CUDA-Q execution or cuTensorNet-kernel equivalence.

Those limits are part of the result, not exceptions to remove from the presentation.
