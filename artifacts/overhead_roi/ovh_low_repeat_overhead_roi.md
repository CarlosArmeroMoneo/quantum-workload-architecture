# OVH Low-Repeat Overhead ROI

- Workloads: `3`
- Interpretation: Fresh-vs-frozen call-wall savings are large enough to justify a performance branch focused on plan reuse, cache, or amortization before any ranking change. The current frozen-plan path does not deliver a stable inner-TTFR improvement by itself, so the best-supported target is outer orchestration overhead rather than ranking.

### `01_real_dense_ring6_amplitude.yaml`

- Selected template: `quick_turnaround`
- Fresh call wall: `1965.046 ms`
- Frozen call wall: `565.287 ms`
- Fresh minus frozen call wall: `1399.759 ms`
- Fresh outer orchestration: `1905.008 ms`
- Frozen outer orchestration: `503.836 ms`
- Fresh TTFR median: `46.723 ms`
- Frozen TTFR median: `47.326 ms`
- Fresh minus frozen TTFR: `-0.604 ms`
- Fresh planner/setup/first-contract medians: `39.402 / 4.075 / 0.582 ms`
- Frozen planner/setup/first-contract medians: `39.863 / 4.058 / 0.598 ms`
- Warm medians fresh/frozen: `0.313 / 0.293 ms`
- Planning+setup share of TTFR delta: `None`
- First-contract share of TTFR delta: `None`

### `06_star_graph_phase_amplitude_heldout_low.yaml`

- Selected template: `quick_turnaround`
- Fresh call wall: `704.015 ms`
- Frozen call wall: `577.313 ms`
- Fresh minus frozen call wall: `126.702 ms`
- Fresh outer orchestration: `629.313 ms`
- Frozen outer orchestration: `513.642 ms`
- Fresh TTFR median: `61.516 ms`
- Frozen TTFR median: `50.198 ms`
- Fresh minus frozen TTFR: `11.317 ms`
- Fresh planner/setup/first-contract medians: `50.504 / 4.238 / 0.581 ms`
- Frozen planner/setup/first-contract medians: `42.899 / 4.151 / 0.581 ms`
- Warm medians fresh/frozen: `0.296 / 0.296 ms`
- Planning+setup share of TTFR delta: `0.679701`
- First-contract share of TTFR delta: `1.9e-05`

### `08_parity_iqp_batched_heldout_medium.yaml`

- Selected template: `quick_turnaround`
- Fresh call wall: `537.979 ms`
- Frozen call wall: `517.479 ms`
- Fresh minus frozen call wall: `20.500 ms`
- Fresh outer orchestration: `461.285 ms`
- Frozen outer orchestration: `444.050 ms`
- Fresh TTFR median: `44.804 ms`
- Frozen TTFR median: `44.746 ms`
- Fresh minus frozen TTFR: `0.058 ms`
- Fresh planner/setup/first-contract medians: `37.781 / 4.001 / 0.539 ms`
- Frozen planner/setup/first-contract medians: `37.860 / 3.959 / 0.535 ms`
- Warm medians fresh/frozen: `0.276 / 0.266 ms`
- Planning+setup share of TTFR delta: `-0.634257`
- First-contract share of TTFR delta: `0.067982`

