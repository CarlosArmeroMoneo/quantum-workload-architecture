# GCP A100 Portability Index

Status: pending real A100 capture.

This index reserves the public reporting surface for the GCP A100 portability lane. It does not currently approve an A100 result.

## Current State

- No pinned A100 artifact manifest is approved in this repository.
- The intended workload is `workloads/manifests/imported/real_ghz3_amplitude.yaml`.
- The intended purpose is portability and profiler validation, not throughput benchmarking.
- OVH `ovh_gra9_rtx5000_28` remains the canonical first profiler-backed architecture slice.

## Rejected Draft

A June 2026 local GCP draft used `artifacts/profiles/gcp_gpu_node/real_ghz3_amplitude.ncu.ae7ab0f3bc426431.*`. Its Nsight Compute CSV reports `NVIDIA L4` and compute capability `8.9`, so it is not A100 evidence and must not be described as a GCP A100 result.

## Acceptance Bar

Before this lane can move from pending to approved:

- `nvidia-smi` must report an A100 40GB device.
- The NCU CSV must report `device__attribute_display_name=NVIDIA A100-SXM4-40GB` and CC `8.0`.
- The execution payload must show `execution_source=cuquantum_tensornet_gpu`.
- Accuracy checks must pass.
- The profile summary must preserve the tiny-workload overhead-dominated caveat.
- Artifact references must use concrete digest-stem paths and a pinned public artifact manifest.

See `configs/profiling/gcp_a100_portability_slice.yaml` for the machine-readable acceptance criteria.

The executable offline gate is `scripts/validate_gcp_a100_acceptance.py`, configured by `configs/profiling/gcp_a100_acceptance_gate.yaml`. It must pass before any pinned GCP A100 artifact set is listed here as accepted evidence.
