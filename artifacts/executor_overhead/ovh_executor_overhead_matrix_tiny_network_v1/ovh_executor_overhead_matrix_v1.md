# OVH Executor Overhead Matrix

- Prewarm mode under test: `tiny_network`
- Benchmark repeats per mode: `5`
- Workloads: `3`
- Interpretation: Benchmark-only prewarm mode 'tiny_network' did not recover most of the bundle-hit penalty across the canonical OVH workloads. The remaining cost points toward persistent executor/session overhead rather than a lightweight warmup fix.

### `01_real_dense_ring6_amplitude.yaml`

| Mode | CLI Wall ms | Driver Total ms | Outer Overhead ms | Dispatch ms | Real Execute ms | Post Exec ms | Pre-T-Start ms | Network Build ms | Inner Wall ms | TTFR ms | Prewarm ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh | 2092.557 | 1401.339 | 1352.906 | 0.367 | 48.741 | 1.489 | 0.367 | 6.166 | 48.741 | 46.751 | 0.000 |
| plan_json | 2078.418 | 1355.885 | 1306.145 | 0.282 | 48.542 | 1.478 | 0.282 | 6.126 | 48.542 | 46.566 | 0.000 |
| bundle_hit | 2139.032 | 1427.406 | 1125.429 | 953.507 | 307.698 | 1.609 | 953.507 | 106.552 | 307.698 | 305.024 | 0.000 |
| bundle_hit+tiny_network | 2186.774 | 1486.360 | 1437.613 | 1253.131 | 48.747 | 1.477 | 1253.131 | 6.018 | 48.747 | 46.771 | 314.977 |

- Seed selected plan: `plan_9681ead327789de4`
- Fresh selected plan IDs: `['plan_9681ead327789de4']`
- All override/bundle paths preserved the seed plan ID: `True`
- Accuracy parity across all modes: `True`
- Bundle-hit gap vs `--plan-json`: `60.614 ms`
- Recovery from explicit prewarm: `-47.743 ms`
- Prewarm recovered `-0.787655` of the bundle-hit gap

### `06_star_graph_phase_amplitude_heldout_low.yaml`

| Mode | CLI Wall ms | Driver Total ms | Outer Overhead ms | Dispatch ms | Real Execute ms | Post Exec ms | Pre-T-Start ms | Network Build ms | Inner Wall ms | TTFR ms | Prewarm ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh | 2280.737 | 1553.514 | 1501.606 | 0.404 | 57.947 | 1.637 | 0.404 | 6.418 | 57.947 | 55.532 | 0.000 |
| plan_json | 2093.245 | 1394.983 | 1344.565 | 0.290 | 51.593 | 1.502 | 0.290 | 6.097 | 51.593 | 49.602 | 0.000 |
| bundle_hit | 2128.992 | 1432.506 | 1135.029 | 961.306 | 300.115 | 1.501 | 961.306 | 105.927 | 300.115 | 297.516 | 0.000 |
| bundle_hit+tiny_network | 2219.080 | 1468.336 | 1416.317 | 1220.932 | 51.717 | 1.439 | 1220.932 | 6.046 | 51.717 | 49.834 | 268.804 |

- Seed selected plan: `plan_1e9bb43cfe444bbb`
- Fresh selected plan IDs: `['plan_1e9bb43cfe444bbb']`
- All override/bundle paths preserved the seed plan ID: `True`
- Accuracy parity across all modes: `True`
- Bundle-hit gap vs `--plan-json`: `35.747 ms`
- Recovery from explicit prewarm: `-90.088 ms`
- Prewarm recovered `-2.520143` of the bundle-hit gap

### `08_parity_iqp_batched_heldout_medium.yaml`

| Mode | CLI Wall ms | Driver Total ms | Outer Overhead ms | Dispatch ms | Real Execute ms | Post Exec ms | Pre-T-Start ms | Network Build ms | Inner Wall ms | TTFR ms | Prewarm ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh | 1961.994 | 1279.858 | 975.010 | 0.324 | 333.710 | 1.407 | 0.324 | 114.784 | 333.710 | 330.949 | 0.000 |
| plan_json | 2067.147 | 1380.008 | 1063.857 | 0.276 | 286.910 | 1.392 | 0.276 | 107.002 | 286.910 | 284.330 | 0.000 |
| bundle_hit | 2122.051 | 1453.390 | 1127.473 | 951.679 | 303.911 | 1.380 | 951.679 | 106.504 | 303.911 | 301.512 | 0.000 |
| bundle_hit+tiny_network | 2095.931 | 1382.065 | 1334.833 | 1217.364 | 46.469 | 1.382 | 1217.364 | 5.984 | 46.469 | 44.725 | 267.232 |

- Seed selected plan: `plan_7209297490c788dd`
- Fresh selected plan IDs: `['plan_7209297490c788dd']`
- All override/bundle paths preserved the seed plan ID: `True`
- Accuracy parity across all modes: `True`
- Bundle-hit gap vs `--plan-json`: `54.905 ms`
- Recovery from explicit prewarm: `26.121 ms`
- Prewarm recovered `0.475748` of the bundle-hit gap

