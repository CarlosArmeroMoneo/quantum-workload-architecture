# Profiler Kernel Taxonomy: Current Evidence

This report summarizes accepted tracked profile summaries only. It does not add new profiling evidence and does not change the OVH RTX 5000 canonical result.

## Why Normalize Kernel Names

Raw Nsight kernel names are long, backend-specific, and unstable across library versions. Atlas maps them into workload-level families so architecture analysis can reason about contraction work, memory movement, initialization, framework overhead, sparse summaries, and profiler replay cautions without overfitting to one mangled symbol.

## Current Accepted Evidence

| Profile | Profiler | Kernels | Families | Signals |
| --- | --- | ---: | --- | --- |
| `evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.profile_summary.json` | ncu | 4 | `cutensor_tiny_mnk`=4 | `contraction_kernel_family_present`=true, `launch_bound_signal`=false, `low_utilization_tiny_workload`=true, `memory_bound_signal`=false, `profiler_replay_warning`=false, `sparse_profile_summary_warning`=false |
| `evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.profile_summary.json` | nsys | 0 | none | `contraction_kernel_family_present`=false, `launch_bound_signal`=true, `low_utilization_tiny_workload`=false, `memory_bound_signal`=false, `profiler_replay_warning`=false, `sparse_profile_summary_warning`=true |

## Interpretation

- The accepted OVH Nsight Compute batched profile contains `cutensor_tiny_mnk` contraction kernels, so the contraction kernel family is present.
- The accepted OVH Nsight Systems GHZ3 profile has no top-kernel rows in the reduced summary, so it carries a sparse-profile warning rather than a kernel-family claim.
- Tiny workloads and tiny-MNK kernels are not throughput benchmarks. They are useful for evidence mechanics, portability checks, and launch/setup analysis.
- `launch_bound_signal` is a prompt for a counterfactual experiment, not proof that launch overhead has been solved.
- `memory_bound_signal` should not be inferred unless memory-transfer families dominate the reduced summary.

## Limits

- NCU metrics in the current public profile are intentionally reduced and metrics-thin.
- Occupancy is unavailable in the accepted summaries, so utilization claims remain conservative.
- Future A100, H100, TPU, or CUDA-Q runtime claims require separate accepted evidence.
