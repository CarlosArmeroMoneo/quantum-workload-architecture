# OVH Persistent Executor Prototype v1

- Gate: `Gate P`
- Benchmark repeats per mode: `5`
- Sequence lengths: `[1, 2, 4, 8]`
- Mixed session order: `['01_real_dense_ring6_amplitude.yaml', '06_star_graph_phase_amplitude_heldout_low.yaml', '08_parity_iqp_batched_heldout_medium.yaml', '01_real_dense_ring6_amplitude.yaml', '06_star_graph_phase_amplitude_heldout_low.yaml', '08_parity_iqp_batched_heldout_medium.yaml']`
- Interpretation: Gate P passed: persistent warm bundle requests remained materially faster than one-shot bundle hits across the OVH trio, cold session totals still beat one-shot totals, and the worker kept strict plan-id/correctness parity.

## `01_real_dense_ring6_amplitude.yaml`

| Mode | CLI Wall ms | Session Total ms | Worker Startup ms | Worker Execute ms | Dispatch+Reply ms | Import Stack ms | Network Build ms | Inner Wall ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh | 2220.715 | 2220.715 | 0.000 | 0.000 | 0.000 | 0.009 | 6.466 | 49.232 |
| plan_json | 2214.297 | 2214.297 | 0.000 | 0.000 | 0.000 | 0.009 | 6.459 | 48.995 |
| one_shot_bundle | 2145.002 | 2145.002 | 0.000 | 0.000 | 0.000 | 927.512 | 113.074 | 365.141 |
| persistent_cold_bundle | 826.626 | 1870.452 | 1075.633 | 233.065 | 0.335 | 0.000 | 156.274 | 230.318 |
| persistent_warm_bundle | 660.002 | 660.002 | 1075.633 | 92.863 | 0.328 | 0.000 | 18.697 | 90.119 |

- Seed selected plan: `plan_9681ead327789de4`
- Selected plan id stable: `True`
- Correctness stable: `True`
- Warm gain vs one-shot bundle: `1485.000 ms`
- Cold session total gain vs one-shot bundle: `274.549 ms`
- Gate P checks: `{'warm_gain_gt_1s': True, 'persistent_cold_beats_one_shot': True, 'warm_worker_execute_lt_120ms': True, 'dispatch_reply_lt_5ms': True, 'import_real_stack_near_zero': True, 'selected_plan_id_stable': True, 'correctness_stable': True}`

## `06_star_graph_phase_amplitude_heldout_low.yaml`

| Mode | CLI Wall ms | Session Total ms | Worker Startup ms | Worker Execute ms | Dispatch+Reply ms | Import Stack ms | Network Build ms | Inner Wall ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh | 2300.363 | 2300.363 | 0.000 | 0.000 | 0.000 | 0.009 | 6.402 | 51.399 |
| plan_json | 2135.559 | 2135.559 | 0.000 | 0.000 | 0.000 | 0.010 | 6.321 | 51.958 |
| one_shot_bundle | 2116.880 | 2116.880 | 0.000 | 0.000 | 0.000 | 966.517 | 111.861 | 313.627 |
| persistent_cold_bundle | 803.967 | 1925.846 | 1118.442 | 236.546 | 0.349 | 0.000 | 156.090 | 233.562 |
| persistent_warm_bundle | 641.879 | 641.879 | 1118.442 | 90.304 | 0.299 | 0.000 | 17.152 | 87.620 |

- Seed selected plan: `plan_1e9bb43cfe444bbb`
- Selected plan id stable: `True`
- Correctness stable: `True`
- Warm gain vs one-shot bundle: `1475.001 ms`
- Cold session total gain vs one-shot bundle: `191.034 ms`
- Gate P checks: `{'warm_gain_gt_1s': True, 'persistent_cold_beats_one_shot': True, 'warm_worker_execute_lt_120ms': True, 'dispatch_reply_lt_5ms': True, 'import_real_stack_near_zero': True, 'selected_plan_id_stable': True, 'correctness_stable': True}`

## `08_parity_iqp_batched_heldout_medium.yaml`

| Mode | CLI Wall ms | Session Total ms | Worker Startup ms | Worker Execute ms | Dispatch+Reply ms | Import Stack ms | Network Build ms | Inner Wall ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh | 2128.207 | 2128.207 | 0.000 | 0.000 | 0.000 | 0.007 | 114.247 | 355.173 |
| plan_json | 2141.262 | 2141.262 | 0.000 | 0.000 | 0.000 | 0.007 | 123.130 | 385.346 |
| one_shot_bundle | 2075.396 | 2075.396 | 0.000 | 0.000 | 0.000 | 960.163 | 113.970 | 309.112 |
| persistent_cold_bundle | 817.009 | 1916.145 | 1065.767 | 221.897 | 0.330 | 0.000 | 149.378 | 219.110 |
| persistent_warm_bundle | 594.481 | 594.481 | 1065.767 | 77.937 | 0.243 | 0.000 | 15.238 | 75.532 |

- Seed selected plan: `plan_7209297490c788dd`
- Selected plan id stable: `True`
- Correctness stable: `True`
- Warm gain vs one-shot bundle: `1480.914 ms`
- Cold session total gain vs one-shot bundle: `159.250 ms`
- Gate P checks: `{'warm_gain_gt_1s': True, 'persistent_cold_beats_one_shot': True, 'warm_worker_execute_lt_120ms': True, 'dispatch_reply_lt_5ms': True, 'import_real_stack_near_zero': True, 'selected_plan_id_stable': True, 'correctness_stable': True}`

