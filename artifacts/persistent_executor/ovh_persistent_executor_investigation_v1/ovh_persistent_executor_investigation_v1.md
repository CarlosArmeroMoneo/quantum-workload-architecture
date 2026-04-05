# OVH Persistent Executor Investigation v1

- Benchmark repeats per mode: `5`
- Workloads: `3`
- Interpretation: Persistent execution amortized enough bootstrap cost to beat one-shot bundle hits on the canonical low-repeat OVH workloads without materially harming the medium-repeat control. The next branch should stay performance-only and turn the worker into a tighter persistent-executor prototype.

### `01_real_dense_ring6_amplitude.yaml`

| Mode | CLI Wall ms | Session Total ms | Driver Total ms | Outer Overhead ms | Import Stack ms | Network Build ms | Worker Startup ms | Worker Dispatch ms | Worker Execute ms | Worker Reply ms | Inner Wall ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh | 2124.360 | 2124.360 | 1456.789 | 1407.992 | 0.009 | 6.242 | 0.000 | 0.000 | 0.000 | 0.000 | 49.545 |
| plan_json | 2155.523 | 2155.523 | 1406.663 | 1358.081 | 0.009 | 6.343 | 0.000 | 0.000 | 0.000 | 0.000 | 48.591 |
| bundle_hit | 2065.971 | 2065.971 | 1379.859 | 1037.108 | 892.559 | 110.887 | 0.000 | 0.000 | 0.000 | 0.000 | 333.618 |
| persistent_bundle_hit_cold | 773.025 | 1848.794 | 389.232 | 171.608 | 0.000 | 147.425 | 1086.793 | 0.283 | 220.245 | 0.003 | 217.624 |
| persistent_bundle_hit_warm | 644.897 | 1720.666 | 270.572 | 185.685 | 0.000 | 14.942 | 1086.793 | 0.301 | 80.535 | 0.003 | 77.844 |

- Seed selected plan: `plan_9681ead327789de4`
- Selection semantics preserved across all modes: `True`
- Accuracy parity across all modes: `True`
- One-shot bundle minus persistent warm CLI wall: `1421.073 ms`
- `--plan-json` minus one-shot bundle CLI wall: `-89.552 ms`
- Persistent warm recovered `None` of the one-shot bundle penalty

### `06_star_graph_phase_amplitude_heldout_low.yaml`

| Mode | CLI Wall ms | Session Total ms | Driver Total ms | Outer Overhead ms | Import Stack ms | Network Build ms | Worker Startup ms | Worker Dispatch ms | Worker Execute ms | Worker Reply ms | Inner Wall ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh | 2189.604 | 2189.604 | 1492.902 | 1441.501 | 0.008 | 6.232 | 0.000 | 0.000 | 0.000 | 0.000 | 51.401 |
| plan_json | 2101.302 | 2101.302 | 1433.770 | 1381.128 | 0.008 | 6.334 | 0.000 | 0.000 | 0.000 | 0.000 | 51.679 |
| bundle_hit | 2106.126 | 2106.126 | 1397.644 | 1096.480 | 932.414 | 106.295 | 0.000 | 0.000 | 0.000 | 0.000 | 298.254 |
| persistent_bundle_hit_cold | 771.102 | 1881.514 | 387.945 | 162.994 | 0.000 | 151.400 | 1097.707 | 0.290 | 223.948 | 0.003 | 221.118 |
| persistent_bundle_hit_warm | 638.334 | 1692.941 | 241.661 | 154.841 | 0.000 | 16.852 | 1097.707 | 0.285 | 89.402 | 0.003 | 86.820 |

- Seed selected plan: `plan_1e9bb43cfe444bbb`
- Selection semantics preserved across all modes: `True`
- Accuracy parity across all modes: `True`
- One-shot bundle minus persistent warm CLI wall: `1467.793 ms`
- `--plan-json` minus one-shot bundle CLI wall: `4.825 ms`
- Persistent warm recovered `304.23226` of the one-shot bundle penalty

### `08_parity_iqp_batched_heldout_medium.yaml`

| Mode | CLI Wall ms | Session Total ms | Driver Total ms | Outer Overhead ms | Import Stack ms | Network Build ms | Worker Startup ms | Worker Dispatch ms | Worker Execute ms | Worker Reply ms | Inner Wall ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh | 2183.688 | 2183.688 | 1466.134 | 1112.457 | 0.007 | 104.451 | 0.000 | 0.000 | 0.000 | 0.000 | 369.189 |
| plan_json | 2134.570 | 2134.570 | 1405.061 | 1103.146 | 0.006 | 105.585 | 0.000 | 0.000 | 0.000 | 0.000 | 295.249 |
| bundle_hit | 2021.989 | 2021.989 | 1342.561 | 1049.264 | 895.629 | 105.893 | 0.000 | 0.000 | 0.000 | 0.000 | 295.287 |
| persistent_bundle_hit_cold | 782.977 | 1850.570 | 388.558 | 173.986 | 0.000 | 143.774 | 1062.419 | 0.304 | 207.728 | 0.003 | 205.470 |
| persistent_bundle_hit_warm | 623.264 | 1675.177 | 251.157 | 177.769 | 0.000 | 17.255 | 1062.419 | 0.318 | 85.558 | 0.003 | 83.052 |

- Seed selected plan: `plan_7209297490c788dd`
- Selection semantics preserved across all modes: `True`
- Accuracy parity across all modes: `True`
- One-shot bundle minus persistent warm CLI wall: `1398.725 ms`
- `--plan-json` minus one-shot bundle CLI wall: `-112.580 ms`
- Persistent warm recovered `None` of the one-shot bundle penalty

