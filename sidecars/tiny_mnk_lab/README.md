# Tiny-MNK Lab

This sidecar isolates the tiny-MNK contraction shape already visible in the tracked Nsight Compute evidence for `real_dense_ring6_batched`. As of April 4, 2026, the OVH host has produced measured benchmark and Nsight Compute outputs for this lab.

Current reference kernel:

- Family: `cutensor_internal_tiny_mnk`
- Shape: `M=32`, `N=256`, `K=75`
- Evidence source: [`evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.ncu.csv`](../../evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.ncu.csv)

Contents:

- `CMakeLists.txt`: builds the standalone CUDA microbench `tiny_mnk_bench`
- `src/tiny_mnk_bench.cu`: simple complex GEMM-style benchmark for tiny `M x N x K` shapes
- `config/observed_tiny_mnk_kernels.json`: tracked reference kernel catalog extracted from repo evidence
- `schema/tiny_mnk_result.schema.json`: expected JSON shape for exported sidecar summaries
- `scripts/extract_reference_kernel.py`: extracts tracked tiny-MNK kernel signatures from Nsight Compute CSV output
- `scripts/export_results.py`: aggregates benchmark CSV output and optional Nsight Compute CSV into a summary JSON
- `scripts/profile_ncu.sh`: Linux helper for Nsight Compute collection
- `scripts/profile_nsys.sh`: Linux helper for Nsight Systems collection
- `reports/report_template.md`: final measured OVH sidecar report

Measured OVH outputs:

- `results/ncu/benchmark.csv`
- `results/ncu/summary.json`
- `results/ncu/tiny_mnk.ncu.csv`
- `reports/report_template.md`

Suggested workflow:

1. `cmake -S sidecars/tiny_mnk_lab -B sidecars/tiny_mnk_lab/build`
2. `cmake --build sidecars/tiny_mnk_lab/build --config Release`
3. `bash sidecars/tiny_mnk_lab/scripts/profile_ncu.sh`
4. Inspect `sidecars/tiny_mnk_lab/results/ncu/summary.json` and `sidecars/tiny_mnk_lab/reports/report_template.md`

Measured interpretation:

- The standalone benchmark reproduced the tracked shape key `m32_n256_k75`.
- The measured standalone kernel family and launch geometry were materially different from the internal cuTensorNet kernel family.
- Treat this lab as a shape-isolation tool, not a parity proxy for the production cuTensorNet path.
