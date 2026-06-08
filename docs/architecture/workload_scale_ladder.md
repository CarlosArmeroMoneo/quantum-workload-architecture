# Workload Scale Ladder

Status: v0.2 planning, no new execution.

The ladder keeps the next accelerator runs deliberate. It separates tiny sanity checks from workloads that can support calibration and architecture interpretation.

## Levels

| Level | Name | Manifest | Role | Local 6GB |
| --- | --- | --- | --- | --- |
| 0 | tiny sanity | `workloads/manifests/imported/real_ghz3_amplitude.yaml` | Import, manifest, execution, and portability sanity. | Allowed as preflight only. |
| 1 | small batched | `workloads/manifests/imported/real_dense_ring6_batched.yaml` | Compare with the accepted OVH canonical workload shape. | Memory permitting, preflight only. |
| 2 | medium structured | `workloads/manifests/generated/dense_universal_smoke.yaml` | Move toward contraction-work behavior. | Not recommended. |
| 3 | repeated structure | `workloads/manifests/validation/grid_2d_shallow_val.yaml` | Test repeat, reuse, and launch-overhead counterfactuals. | Not recommended. |

## Claim Boundaries

- GHZ3 is not a throughput benchmark.
- Local 6GB is a constrained preflight host only.
- Medium workloads are needed before making stronger performance conclusions.
- OVH RTX 5000 remains the accepted profiler-backed architecture slice.
- GCP A100 remains pending until the acceptance gate passes with pinned artifacts.

The machine-readable ladder is `configs/experiments/workload_scale_ladder_v0_2.yaml`.
