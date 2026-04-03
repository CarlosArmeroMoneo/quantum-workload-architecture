# Remote CUDA-Q and Tiny-MNK Sidecar Results: Blocked Locally

The CUDA-Q comparison pass and the tiny-MNK sidecar measurement pass both require a Linux CUDA host that is not available in this workspace.

## Blocker

- CUDA-Q runtime is not installed on the current machine
- The sidecar lab under [`sidecars/tiny_mnk_lab`](../../sidecars/tiny_mnk_lab/README.md) is scaffolded but not measured locally
- The canonical profiler evidence for the tiny-MNK kernel is tracked, but no standalone sidecar benchmark results have been captured yet

## Remote Execution Checklist

1. Install CUDA-Q on the Linux CUDA host alongside the existing `cupy`, `cuquantum`, and `qiskit` environment
2. Validate the adapter-backed manifests:
   `python -m aqs manifest validate --mode implemented workloads/manifests/imported/cudaq_ghz3_amplitude.yaml workloads/manifests/imported/cudaq_dense_ring6_batched.yaml`
3. Run the CUDA-Q structural planning path and compare against the Qiskit fixtures
4. Build the sidecar:
   `cmake -S sidecars/tiny_mnk_lab -B sidecars/tiny_mnk_lab/build && cmake --build sidecars/tiny_mnk_lab/build --config Release`
5. Profile the sidecar with `bash sidecars/tiny_mnk_lab/scripts/profile_ncu.sh`
6. Fill in `sidecars/tiny_mnk_lab/reports/report_template.md` from the emitted sidecar `summary.json`

## Expected Outputs

- CUDA-Q comparison notes and curated normalization/probe evidence
- Sidecar `benchmark.csv`
- Sidecar `summary.json`
- Sidecar profiler exports (`.ncu-rep`, `.ncu.csv`, optional `.nsys-rep`)
- Final report populated from `sidecars/tiny_mnk_lab/reports/report_template.md`

## Merge Condition

This branch remains blocked until both the CUDA-Q comparison evidence and the tiny-MNK sidecar results are captured on a Linux CUDA host and added as curated summaries rather than placeholders.
