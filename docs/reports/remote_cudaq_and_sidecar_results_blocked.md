# Remote CUDA-Q and Tiny-MNK Sidecar Results: OVH Measured Pass

- Date: `2026-04-04` UTC
- Live host: OVH `ovh_gra9_rtx5000_28` with Quadro RTX 5000, driver `580.95.05`, Ubuntu `25.04`, green profiling readiness, and a working CUDA build toolchain after installing `cmake` plus `nvidia-cuda-toolkit`

## CUDA-Q Comparison

- `cudaq` Python package import succeeded on this host at version `0.14.0`
- Manifest validation succeeded for both adapter-backed manifests:
  - `workloads/manifests/imported/cudaq_ghz3_amplitude.yaml`
  - `workloads/manifests/imported/cudaq_dense_ring6_batched.yaml`
- Curated branch artifacts:
  - `artifacts/cudaq_adapter_compare/summary.json`
  - `artifacts/cudaq_adapter_compare/report.md`
- Adapter-backed structural comparison results:
  - `ghz3_amplitude`: normalized IR comparable keys matched the Qiskit fixture, the interaction graph matched excluding source kind, and the structural-real probe matched on `largest_intermediate=4.0` and `optimizer_cost=100.0`
  - `dense_ring6_batched`: normalized IR comparable keys matched the Qiskit fixture, the interaction graph matched excluding source kind, and the structural-real probe matched on `largest_intermediate=16.0` and `optimizer_cost=940.0`
- Real execution truth boundary:
  - both CUDA-Q manifests returned `runtime_error` with `reason_code=unsupported_source_format`
  - measured reason: `real cuTensorNet execution currently supports source_format='qiskit' only`
  - matching Qiskit manifests executed successfully via `cuquantum_tensornet_gpu`
- Measured Qiskit comparison runs on the same host:
  - `qiskit_qasm2_ghz3.yaml`: TTFR `0.044028 s`, wall `0.045965 s`, steady iter `0.237200 ms`
  - `real_dense_ring6_batched.yaml`: TTFR `0.066752 s`, wall `0.068773 s`, steady iter `0.284760 ms`
- Branch conclusion for CUDA-Q: the package is installed and the adapter-backed normalization plus probe path is real, but this repo still does not have separate measured native CUDA-Q runtime execution evidence on this host.

## Tiny-MNK Sidecar

- Build and profile commands completed on this host after repairing the helper script:
  - `cmake -S sidecars/tiny_mnk_lab -B sidecars/tiny_mnk_lab/build`
  - `cmake --build sidecars/tiny_mnk_lab/build --config Release`
  - `bash sidecars/tiny_mnk_lab/scripts/profile_ncu.sh`
- Branch code fixes required for a truthful repeatable sidecar flow:
  - `profile_ncu.sh` now removes stale prior outputs and imports the generated `.ncu-rep` into `tiny_mnk.ncu.csv` before exporting the summary
  - the sidecar exporter now records the standalone `tiny_mnk_gemm_kernel` family when the benchmark shape is known, instead of dropping the measured NCU rows
- Curated branch artifacts:
  - `sidecars/tiny_mnk_lab/results/ncu/benchmark.csv`
  - `sidecars/tiny_mnk_lab/results/ncu/summary.json`
  - `sidecars/tiny_mnk_lab/results/ncu/tiny_mnk.ncu.csv`
  - `sidecars/tiny_mnk_lab/reports/report_template.md`
- Heavy local-only sidecar artifact intentionally not committed:
  - `sidecars/tiny_mnk_lab/results/ncu/tiny_mnk.ncu-rep`
- Measured sidecar benchmark results for the tracked reference shape `m32_n256_k75`:
  - `50/50` benchmark iterations reported `ok`
  - median latency `2697.165 ms`
  - minimum latency `2652.800 ms`
  - maximum latency `8714.420 ms`
  - peak throughput `0.001853 GFLOP/s`
  - `7` iterations were `>= 5000 ms`
- Measured sidecar NCU profile results:
  - `55` profiled launches of `<unnamed>::tiny_mnk_gemm_kernel(const double2 *, const double2 *, double2 *, int, int, int)`
  - sidecar launch shape: block `(16, 16, 1)`, grid `(16, 2, 1)`
  - reference cuTensorNet launch shape: block `(256, 1, 1)`, grid `(1, 1, 1)`
  - median `sm__throughput.avg.pct_of_peak_sustained_elapsed=56.289`
  - median `gpu__dram_throughput.avg.pct_of_peak_sustained_elapsed=2.655`
  - median `gpu__compute_memory_throughput.avg.pct_of_peak_sustained_elapsed=4.801`
  - median `launch__waves_per_multiprocessor=0.17`
  - `launch__registers_per_thread=64`, `launch__shared_mem_per_block_allocated=0`
- Branch conclusion for the sidecar: it reproduced the tracked tiny-MNK shape key and emitted real profiler-backed outputs, but it did not reproduce the internal cuTensorNet kernel signature or launch configuration. The measured standalone kernel was materially different and far slower than the internal reference path.

## Verdict

- Publish CUDA-Q as a truthful partial result: adapter-backed structural comparison is measured, but native CUDA-Q runtime execution is still unsupported in this repo.
- Publish the tiny-MNK sidecar as a real measured pass, including the helper-script fixes required to make the NCU export path repeatable.
- Do not claim CUDA-Q runtime execution evidence or sidecar parity with the internal cuTensorNet kernel family.
