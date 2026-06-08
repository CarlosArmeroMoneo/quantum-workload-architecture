# Profiler Signal Taxonomy

Atlas reduces profiler artifacts into workload-level signals instead of leaving them as raw profiler dumps.

## Kernel Families

- `cutensor_contraction`: cuTensor/cuTensorNet contraction kernels.
- `cutensor_tiny_mnk`: tiny-MNK cuTensor contraction kernels.
- `reduction`: reduction or aggregation kernels.
- `initialization`: array initialization and arange-style kernels.
- `memory_transfer`: memcpy, memset, and related transfer kernels.
- `framework_overhead`: CuPy, framework, pointwise, or dispatch helper kernels.
- `unknown`: kernels that should stay visible until classified.

## Profiler Signals

- `launch_bound_signal`: profiler evidence suggests setup, launch, framework, or sparse-summary overhead should be tested with a counterfactual.
- `memory_bound_signal`: memory-transfer families dominate the reduced kernel summary.
- `low_utilization_tiny_workload`: occupancy is low or the profile is dominated by tiny-MNK kernels.
- `contraction_kernel_family_present`: a cuTensor/cuTensorNet contraction family appears in the reduced summary.
- `profiler_replay_warning`: profiler replay metadata suggests the capture may have distorted timing.
- `sparse_profile_summary_warning`: the reduced profile has no top-kernel rows, so kernel-family inference should stay limited.

## Phase Families

- `load_circuit`: workload source loading and frontend import.
- `convert_to_einsum`: conversion into the contraction representation.
- `contract_path`: path search and planning inside the execution path.
- `contract_first`: first contraction execution.
- `contract_warm`: repeated/warm contraction execution.
- `postprocess`: output formatting, validation, and cleanup work.

## Bottleneck Families

- `launch_overhead`: setup, load, conversion, launch, or orchestration overhead dominates the useful contraction work.
- `planner_roi`: path search or autotune time is large enough that planner budget and reuse should be tested.
- `cache_reuse`: cold-vs-warm timing suggests reuse, persistent workers, or caching may change TTFR.
- `memory_workspace_pressure`: workspace or peak memory pressure appears to constrain the execution mode.
- `low_utilization_tiny_workload`: kernels are real but too small to occupy the accelerator well.
- `profiler_replay_distortion`: profiler replay or capture mode may change observed timing enough to require caution.

## Usage Rule

Architecture nominations should reference reduced families and phases where possible. Raw kernel names remain useful evidence, but public claims should be made at the workload-signal level.
