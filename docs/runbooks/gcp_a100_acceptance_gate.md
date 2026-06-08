# GCP A100 Acceptance Gate

Status: required before any public A100 result.

The GCP A100 lane is a portability and calibration lane first. It must not be described as an A100 performance result until a larger, acceptance-gated workload justifies that claim.

## Required Evidence

- Device identity verified as `NVIDIA A100-SXM4-40GB`.
- Compute capability verified as `8.0`.
- System manifest is `configs/systems/gcp_a100_sxm4_40gb.yml` or a frozen host-specific derivative.
- Execution payload reports `execution_source=cuquantum_tensornet_gpu`.
- Accuracy evaluation passes.
- Nsight Systems or Nsight Compute artifact is generated.
- Reduced `profile_summary` is non-empty.
- Artifact manifest uses concrete pinned paths.
- Interpretation class is assigned.
- Tiny-workload warning is preserved for GHZ3.

## Rejection Conditions

- Device is L4, T4, H100, or any non-A100 GPU.
- Profiler summary is empty.
- Accuracy fails or is missing.
- Artifact references are local scratch paths only.
- Report wording claims throughput from GHZ3.

## First Accepted Claim

The first accepted GCP A100 GHZ3 result should be Tier 2 portability/calibration evidence only. It does not replace the OVH Tier 3 canonical architecture slice.
