# Launch-Overhead Counterfactual

## Observation

The canonical OVH `real_dense_ring6_batched` slice produced a Tier 3 `launch_overhead` nomination from real profiler-backed analysis. The tracked architecture output reports setup/load/convert/postprocess overhead at about `21.86%`.

## Hypothesis

For small exact-TN workloads, orchestration and setup can dominate enough that caching, persistent workers, plan reuse, or graph capture may improve TTFR without changing correctness.

## Counterfactual Knobs

- `persistent_executor`: `false`, `true`
- `plan_bundle_reuse`: `false`, `true`
- `repeat_count_hint`: `1`, `8`, `32`, `128`
- CUDA graph mode: `off`, `on` only when capture is supported
- cache workspace: `0`, `2`, `8` GB

## Expected Evidence

- lower TTFR
- lower setup share
- stable correctness and output digest behavior
- profile summary shows a changed phase mix
- selected plan identity is stable unless the experiment explicitly changes planning

## Stop Condition

If TTFR improves by less than `10%`, correctness changes, or overhead simply moves into another phase, do not claim the bottleneck is resolved.
