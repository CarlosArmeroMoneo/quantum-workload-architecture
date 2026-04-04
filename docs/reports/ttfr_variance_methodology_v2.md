# TTFR Variance Methodology v2

This document defines the next-step upgrade path for close-call TTFR disputes on the OVH host. It does not replace the current lightweight targeted replicate flow; it adds a stronger interleaved mode for future retune decisions.

## Current v1 Method

The existing targeted replicate tool runs one candidate, then the other candidate, and compares their TTFR medians from separate sequential batches.

Strengths:

- lightweight
- easy to run against frozen plan overrides
- useful as a veto tool when a single-shot winner flips or stays inside the observed variance band

Limits:

- the candidates do not run interleaved
- drift can accumulate between the left batch and right batch
- the uncertainty band is based on individual spread rather than paired deltas

## v2 Upgrade

The new methodology adds an interleaved pair mode:

- `A B A B A B ...`

instead of:

- `A A A ...` then `B B B ...`

The interleaved mode is designed for close-call retune disputes where the claimed win is small and low-repeat TTFR noise matters.

## Required Outputs

When `pair_mode=interleaved`, the pair summary must include:

- `pair_mode`
- `per_block_deltas_s`
- `delta_mean_s`
- `delta_median_s`
- `delta_stdev_s`
- `delta_confidence_interval`
- `conclusion`

The delta definition is:

- `right_minus_left_ttfr_s`

Positive deltas mean the left template is faster for that block.

## Conclusion Categories

- `winner_stable`: the interleaved delta-based interval stays on one side of zero and the median winner matches the single-shot baseline
- `inconclusive_vs_variance`: the interleaved delta-based interval crosses zero
- `winner_flipped_vs_single_shot`: the interleaved delta-based interval clears zero, but the median winner flips relative to the stored single-shot baseline

## Usage Rule

- Keep `pair_mode=sequential` as the default lightweight path.
- Use `pair_mode=interleaved` when a future planner retune claim depends on a small TTFR edge.
- Do not use sequential-only evidence to certify a close-call retune when the observed gap is still comparable to variance.

## Current Status

- Implemented: the targeted pair runner now supports `--pair-mode sequential|interleaved`
- Default: `sequential`
- Intended use today: upgrade path for future close-call retune disputes
- Certification status today: defined and runnable, but not yet the basis for any approved planner retune
