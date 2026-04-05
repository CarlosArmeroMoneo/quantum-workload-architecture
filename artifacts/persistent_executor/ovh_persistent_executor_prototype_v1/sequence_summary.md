# OVH Persistent Executor Sequence Summary

- Session lengths: `[1, 2, 4, 8]`
- Mixed session order: `['01_real_dense_ring6_amplitude.yaml', '06_star_graph_phase_amplitude_heldout_low.yaml', '08_parity_iqp_batched_heldout_medium.yaml', '01_real_dense_ring6_amplitude.yaml', '06_star_graph_phase_amplitude_heldout_low.yaml', '08_parity_iqp_batched_heldout_medium.yaml']`

| Session | Requests | Cold CLI ms | Warm CLI median ms | Warm Worker Execute median ms | RSS Delta MB | Plan Stable | Correctness Stable |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 01_real_dense_ring6_amplitude.len1 | 1 | 805.945 | 0.000 | 0.000 | 233.379 | True | True |
| 01_real_dense_ring6_amplitude.len2 | 2 | 718.896 | 657.978 | 102.888 | 248.133 | True | True |
| 01_real_dense_ring6_amplitude.len4 | 4 | 796.026 | 708.596 | 88.335 | 248.422 | True | True |
| 01_real_dense_ring6_amplitude.len8 | 8 | 790.557 | 674.395 | 86.684 | 248.555 | True | True |
| 06_star_graph_phase_amplitude_heldout_low.len1 | 1 | 845.631 | 0.000 | 0.000 | 233.293 | True | True |
| 06_star_graph_phase_amplitude_heldout_low.len2 | 2 | 760.550 | 695.266 | 131.431 | 248.156 | True | True |
| 06_star_graph_phase_amplitude_heldout_low.len4 | 4 | 797.873 | 556.533 | 68.872 | 248.309 | True | True |
| 06_star_graph_phase_amplitude_heldout_low.len8 | 8 | 775.960 | 656.461 | 87.928 | 248.457 | True | True |
| 08_parity_iqp_batched_heldout_medium.len1 | 1 | 856.508 | 0.000 | 0.000 | 233.156 | True | True |
| 08_parity_iqp_batched_heldout_medium.len2 | 2 | 819.255 | 592.278 | 65.138 | 247.965 | True | True |
| 08_parity_iqp_batched_heldout_medium.len4 | 4 | 826.059 | 686.676 | 83.056 | 248.184 | True | True |
| 08_parity_iqp_batched_heldout_medium.len8 | 8 | 816.559 | 642.916 | 76.199 | 248.875 | True | True |
| mixed.len6 | 6 | 804.694 | 658.619 | 89.397 | 248.305 | True | True |
