# OVH Executor Overhead Matrix

- Prewarm mode under test: `import_context`
- Benchmark repeats per mode: `5`
- Workloads: `3`
- Interpretation: Benchmark-only prewarm mode 'import_context' did not recover most of the bundle-hit penalty across the canonical OVH workloads. The remaining cost points toward persistent executor/session overhead rather than a lightweight warmup fix.

### `01_real_dense_ring6_amplitude.yaml`

| Mode | CLI Wall ms | Driver Total ms | Outer Overhead ms | Dispatch ms | Real Execute ms | Post Exec ms | Pre-T-Start ms | Network Build ms | Inner Wall ms | TTFR ms | Prewarm ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh | 2087.321 | 1411.439 | 1362.687 | 0.376 | 48.752 | 1.548 | 0.376 | 6.159 | 48.752 | 46.625 | 0.000 |
| plan_json | 2080.162 | 1388.265 | 1340.313 | 0.286 | 48.229 | 1.484 | 0.286 | 6.148 | 48.229 | 46.252 | 0.000 |
| bundle_hit | 2149.166 | 1416.388 | 1123.510 | 945.419 | 307.214 | 1.559 | 945.419 | 105.670 | 307.214 | 304.684 | 0.000 |
| bundle_hit+import_context | 2098.731 | 1413.952 | 1262.231 | 1096.653 | 153.970 | 1.503 | 1096.653 | 106.819 | 153.970 | 151.105 | 148.133 |

- Seed selected plan: `plan_9681ead327789de4`
- Fresh selected plan IDs: `['plan_9681ead327789de4']`
- All override/bundle paths preserved the seed plan ID: `True`
- Accuracy parity across all modes: `True`
- Bundle-hit gap vs `--plan-json`: `69.004 ms`
- Recovery from explicit prewarm: `50.436 ms`
- Prewarm recovered `0.730906` of the bundle-hit gap

### `06_star_graph_phase_amplitude_heldout_low.yaml`

| Mode | CLI Wall ms | Driver Total ms | Outer Overhead ms | Dispatch ms | Real Execute ms | Post Exec ms | Pre-T-Start ms | Network Build ms | Inner Wall ms | TTFR ms | Prewarm ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh | 2111.095 | 1393.310 | 1343.153 | 0.384 | 51.459 | 1.515 | 0.384 | 6.644 | 51.459 | 49.583 | 0.000 |
| plan_json | 2117.132 | 1396.632 | 1345.036 | 0.306 | 51.597 | 1.495 | 0.306 | 6.376 | 51.597 | 49.636 | 0.000 |
| bundle_hit | 2085.147 | 1396.701 | 1099.802 | 917.495 | 299.720 | 1.568 | 917.495 | 105.562 | 299.720 | 297.005 | 0.000 |
| bundle_hit+import_context | 2051.305 | 1367.280 | 1213.139 | 1079.879 | 154.141 | 1.471 | 1079.879 | 104.248 | 154.141 | 151.538 | 144.881 |

- Seed selected plan: `plan_1e9bb43cfe444bbb`
- Fresh selected plan IDs: `['plan_1e9bb43cfe444bbb']`
- All override/bundle paths preserved the seed plan ID: `True`
- Accuracy parity across all modes: `True`
- Bundle-hit gap vs `--plan-json`: `-31.985 ms`
- Recovery from explicit prewarm: `33.842 ms`
- Prewarm recovered `None` of the bundle-hit gap

### `08_parity_iqp_batched_heldout_medium.yaml`

| Mode | CLI Wall ms | Driver Total ms | Outer Overhead ms | Dispatch ms | Real Execute ms | Post Exec ms | Pre-T-Start ms | Network Build ms | Inner Wall ms | TTFR ms | Prewarm ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh | 2103.880 | 1382.504 | 1095.169 | 0.318 | 287.631 | 1.358 | 0.318 | 105.184 | 287.631 | 285.163 | 0.000 |
| plan_json | 2083.130 | 1353.470 | 1027.979 | 0.293 | 288.392 | 1.376 | 0.293 | 104.359 | 288.392 | 285.913 | 0.000 |
| bundle_hit | 2136.452 | 1446.081 | 1156.285 | 991.730 | 292.374 | 1.390 | 991.730 | 105.839 | 292.374 | 289.901 | 0.000 |
| bundle_hit+import_context | 2056.197 | 1361.344 | 1210.456 | 1102.515 | 151.818 | 1.385 | 1102.515 | 106.359 | 151.818 | 149.268 | 143.514 |

- Seed selected plan: `plan_7209297490c788dd`
- Fresh selected plan IDs: `['plan_7209297490c788dd']`
- All override/bundle paths preserved the seed plan ID: `True`
- Accuracy parity across all modes: `True`
- Bundle-hit gap vs `--plan-json`: `53.322 ms`
- Recovery from explicit prewarm: `80.255 ms`
- Prewarm recovered `1.505109` of the bundle-hit gap

