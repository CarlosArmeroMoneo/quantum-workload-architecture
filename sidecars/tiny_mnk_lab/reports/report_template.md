# Tiny-MNK Sidecar Report

## Scope

- Sidecar branch: `stack/09-tiny-mnk-sidecar-foundation`
- Reference kernel family: `cutensor_internal_tiny_mnk`
- Reference shape: `M=32`, `N=256`, `K=75`
- Reference evidence: `evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.ncu.csv`

## Build

- CUDA toolkit:
- GPU:
- Driver:
- Commit:

## Benchmark Matrix

- Labels exercised:
- Shapes exercised:
- Warmup / iters:

## Results

- Matched reference shapes:
- Fastest median latency:
- Peak GFLOP/s:
- Nsight notes:

## Interpretation

- Does the sidecar reproduce the tiny-MNK launch pattern seen in the cuTensorNet evidence?
- Do the profile exports suggest launch-bound behavior, memory-bound behavior, or both?
- What changed relative to the reference kernel signatures tracked under `config/observed_tiny_mnk_kernels.json`?

## Attached Artifacts

- `benchmark.csv`
- `summary.json`
- `tiny_mnk.ncu-rep` / `tiny_mnk.ncu.csv`
- `tiny_mnk.nsys-rep`
