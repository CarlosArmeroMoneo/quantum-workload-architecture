# OVH Plan Reuse Prototype

- Workloads: `3`
- Interpretation: Explicit reusable plan bundles are safe and auditable, and they reduce end-to-end CLI wall time on the two low-repeat amplitude workloads by removing fresh planning/probe/orchestration work while keeping the selected plan fixed. The benefit is not universal: the medium-repeat control was slightly negative because cold real-executor initialization shifted into the reused execute phase. This is a performance result, not a calibration or ranking result.
- Ranking changed: `no`

### `01_real_dense_ring6_amplitude.yaml`

- Selected template: `quick_turnaround`
- Bundle hit rate: `3/3` reused runs
- CLI wall fresh/reused median: `2094.026 / 1955.080 ms`
- CLI wall delta: `138.946 ms` (`6.64%`)
- Driver total fresh/reused median: `1352.496 / 1284.915 ms`
- Driver total delta: `67.581 ms` (`5.00%`)
- Outer-overhead fresh/reused median: `1302.783 / 989.200 ms`
- Probe fresh/reused median: `1160.611 / 0.000 ms`
- Candidate generation fresh/reused median: `0.258 / 0.000 ms`
- Execute-bundle fresh/reused median: `52.686 / 1186.419 ms`
- Inner wall fresh/reused median: `50.575 / 295.715 ms`
- TTFR fresh/reused median: `48.562 / 293.078 ms`
- Safety check: `same_selected_plan_id=True`, `all_reuse_hits=True`

### `06_star_graph_phase_amplitude_heldout_low.yaml`

- Selected template: `quick_turnaround`
- Bundle hit rate: `3/3` reused runs
- CLI wall fresh/reused median: `2065.271 / 2018.693 ms`
- CLI wall delta: `46.577 ms` (`2.26%`)
- Driver total fresh/reused median: `1359.373 / 1306.673 ms`
- Driver total delta: `52.700 ms` (`3.88%`)
- Outer-overhead fresh/reused median: `1303.995 / 1013.884 ms`
- Probe fresh/reused median: `1107.936 / 0.000 ms`
- Candidate generation fresh/reused median: `0.261 / 0.000 ms`
- Execute-bundle fresh/reused median: `54.080 / 1209.755 ms`
- Inner wall fresh/reused median: `52.139 / 305.288 ms`
- TTFR fresh/reused median: `50.191 / 302.496 ms`
- Safety check: `same_selected_plan_id=True`, `all_reuse_hits=True`

### `08_parity_iqp_batched_heldout_medium.yaml`

- Selected template: `quick_turnaround`
- Bundle hit rate: `3/3` reused runs
- CLI wall fresh/reused median: `2146.894 / 2153.985 ms`
- CLI wall delta: `-7.092 ms` (`-0.33%`)
- Driver total fresh/reused median: `1400.710 / 1427.894 ms`
- Driver total delta: `-27.185 ms` (`-1.94%`)
- Outer-overhead fresh/reused median: `1055.274 / 1120.123 ms`
- Probe fresh/reused median: `869.853 / 0.000 ms`
- Candidate generation fresh/reused median: `0.243 / 0.000 ms`
- Execute-bundle fresh/reused median: `297.196 / 1244.767 ms`
- Inner wall fresh/reused median: `295.338 / 303.513 ms`
- TTFR fresh/reused median: `292.757 / 300.958 ms`
- Safety check: `same_selected_plan_id=True`, `all_reuse_hits=True`
