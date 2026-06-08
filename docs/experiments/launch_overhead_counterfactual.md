# Launch-Overhead Counterfactual Experiment Card

## Title

Test whether setup reuse reduces the OVH `real_dense_ring6_batched` `launch_overhead` nomination without changing correctness or hiding measured work.

## Source Nomination

- Workload slice: `real_dense_ring6_batched`.
- Host: OVH `ovh_gra9_rtx5000_28`, Quadro RTX 5000.
- Profiler: Nsight Compute profile summary reduced from a real `cuquantum_tensornet_gpu` execution.
- Architecture output: `evidence/first_real_profiler_slice/real_dense_ring6_batched.arch.json`.
- Bottleneck family: `launch_overhead`.
- Nomination source: `real_profiler_analysis`.

## Evidence Tier

Current evidence is Tier 3 architecture nomination evidence for the OVH canonical slice. This card defines a follow-up counterfactual experiment; it does not claim that the bottleneck has been solved.

## Observation

Real profiler-backed analysis nominated `launch_overhead`. The tracked architecture output reports setup/load/convert/postprocess overhead at about `21.86%`, making orchestration and setup a meaningful share of the profiled run.

## Hypothesis

Small exact-TN workloads may benefit from reducing orchestration/setup overhead through reuse, caching, persistent execution, or plan reuse. If the hypothesis is right, TTFR and setup share should improve while correctness and real profiler-backed evidence remain intact.

## Counterfactual Knobs

- `persistent_executor`: `off`, `on`
- `plan_bundle_reuse`: `off`, `on`
- `repeat_count_hint`: `1`, `8`, `32`, `128`
- `cache_workspace_gb`: `0`, `2`, `8`, `16`
- graph mode: `off`, `on` if supported
- prewarm mode: `none`, `light`, `full` if supported

This is not a broad sweep. The first pass should hold the workload, host, precision, planner budget, and selected-plan identity fixed unless a knob explicitly changes reuse behavior.

## Expected Measurements

- TTFR.
- `steady_iter_ms`.
- `setup_share_pct`.
- `profile_summary` phase times.
- correctness status.
- artifact manifest.
- nomination change after architecture analysis reruns.

## Success Criterion

- `setup_share_pct` is reduced.
- TTFR improves by at least `10%` against the matched baseline.
- Correctness is preserved.
- Profiler-backed evidence remains real, not synthetic.
- No new dominant bottleneck appears in the profile summary or architecture nomination.

## Stop Criterion

- TTFR improvement is less than `10%`.
- Improvement comes only from hiding setup outside the measured region.
- Correctness fails or output digest behavior changes unexpectedly.
- The profile summary is missing or synthetic.
- A profiler artifact is missing from the artifact manifest.

If any stop condition triggers, do not claim the bottleneck is resolved.

## Risks And Confounders

- Persistent workers can move import/setup work outside the measured request window.
- Warm caches can make the experiment measure cache state rather than architecture behavior.
- CUDA graph capture may fail or change stream behavior, so graph mode must stay optional.
- Tiny workloads can be dominated by profiler overhead or launch replay distortion.
- Plan reuse can change selected-plan identity if the baseline and counterfactual are not pinned.

## Required Artifacts

- Matched baseline and counterfactual execution payloads.
- Real `profile_summary` files for each accepted arm.
- Raw Nsight artifact references in a pinned artifact manifest.
- Correctness evaluation rows with `status=pass`.
- Architecture-analysis output showing whether the `launch_overhead` nomination changed.
- A short readout explaining any stopped or rejected arm.

## Acceptance Rule

Accept the counterfactual only if the matched run set preserves correctness, uses real profiler-backed summaries, records concrete artifact paths, reduces `setup_share_pct`, improves TTFR by at least `10%`, and does not introduce a new dominant bottleneck. Otherwise keep the result pending or rejected and leave the original `launch_overhead` nomination unchanged.

## v0.2 Bounded Manifest

The bounded v0.2 planning manifest is `configs/experiments/launch_overhead_counterfactual_v0_2.yaml`, with a paired-arm selection policy rather than a Cartesian sweep. The runbook is `docs/runbooks/launch_overhead_counterfactual_runbook.md`.
