# Tiny-MNK Sidecar Report: OVH Measured Pass

## Scope

- Sidecar branch: `stack/12-remote-cudaq-and-sidecar-results`
- Reference kernel family: `cutensor_internal_tiny_mnk`
- Reference shape: `M=32`, `N=256`, `K=75`
- Reference evidence: `evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.ncu.csv`
- Measured sidecar outputs:
  - `sidecars/tiny_mnk_lab/results/ncu/benchmark.csv`
  - `sidecars/tiny_mnk_lab/results/ncu/summary.json`
  - `sidecars/tiny_mnk_lab/results/ncu/tiny_mnk.ncu.csv`

## Build

- CUDA toolkit: `12.2.140` (`nvcc` from `nvidia-cuda-toolkit`)
- GPU: Quadro RTX 5000
- Driver: `580.95.05`
- Repo state: measured on `stack/12-remote-cudaq-and-sidecar-results` after the Stage 11 rebase, with helper-script fixes to make `profile_ncu.sh` import its own `.ncu-rep` and clean stale rerun outputs

## Benchmark Matrix

- Labels exercised: `tiny_mnk_reference`
- Shapes exercised: `M=32`, `N=256`, `K=75`
- Warmup / iters: `5 / 50`

## Results

- Matched reference shapes: `m32_n256_k75`
- Benchmark status: `50/50` iterations `ok`
- Fastest measured latency: `2652.800 ms`
- Median latency: `2697.165 ms`
- Slowest measured latency: `8714.420 ms`
- Peak GFLOP/s: `0.001853`
- Large outliers: `7` iterations at or above `5000 ms`
- Nsight Compute summary:
  - `55` profiled launches of `<unnamed>::tiny_mnk_gemm_kernel(const double2 *, const double2 *, double2 *, int, int, int)`
  - sidecar launch geometry: block `(16, 16, 1)`, grid `(16, 2, 1)`
  - median `sm__throughput.avg.pct_of_peak_sustained_elapsed=56.289`
  - median `gpu__dram_throughput.avg.pct_of_peak_sustained_elapsed=2.655`
  - median `gpu__compute_memory_throughput.avg.pct_of_peak_sustained_elapsed=4.801`
  - median `launch__waves_per_multiprocessor=0.17`
  - `launch__registers_per_thread=64`, `launch__shared_mem_per_block_allocated=0`

## Interpretation

- The sidecar reproduced the tracked tiny-MNK shape key, but it did not reproduce the internal cuTensorNet kernel signature. The measured sidecar kernel family was `tiny_mnk_sidecar_kernel`, not `cutensor_internal_tiny_mnk`.
- The launch geometry also differed materially from the reference path:
  - sidecar: block `(16, 16, 1)`, grid `(16, 2, 1)`
  - reference: block `(256, 1, 1)`, grid `(1, 1, 1)`
- The measured sidecar was far slower than the internal reference path and showed low DRAM throughput plus very low waves per multiprocessor, so this microbench should be treated as a shape-isolation tool rather than a faithful performance proxy for the cuTensorNet kernel.

## Attached Artifacts

- `benchmark.csv`
- `summary.json`
- `tiny_mnk.ncu.csv`
- `tiny_mnk.ncu-rep` was produced locally but intentionally kept out of git as a heavyweight profiler binary
