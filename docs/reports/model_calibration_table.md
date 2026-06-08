# Model Calibration Table

Generated from accepted tracked evidence plus pending acceptance-gated lanes. GCP A100 rows are not accepted evidence until pinned artifacts pass the acceptance gate.

| Case | Host | Workload | Tier | Pred TTFR s | Actual TTFR s | TTFR Ratio | Pred Iter ms | Actual Iter ms | Iter Ratio | Interpretation | Source |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| OVH dense ring6 batched | ovh_gra9_rtx5000_28 | wkl_3a3d42fe7b94a2ed | Tier 3 | 0.480977 | 1.04199 | 2.1664 | 6.64912 | 392.928 | 59.0948 | real_arch_nomination | `evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.execution.json` |
| OVH GHZ3 amplitude | ovh_gra9_rtx5000_28 | wkl_5361a0b920fc4e05 | Tier 3 | 0.497969 | 0.0231778 | 0.046545 | 4.99625 | 0.201421 | 0.040314 | tiny_workload_calibration | `evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.execution.json` |
| GCP A100 GHZ3 portability pending | gcp_a100_sxm4_40gb | workloads/manifests/imported/real_ghz3_amplitude.yaml | pending/unaccepted | pending | pending | pending | pending | pending | pending | pending_a100_portability_gate | `configs/profiling/gcp_a100_portability_slice.yaml` |
