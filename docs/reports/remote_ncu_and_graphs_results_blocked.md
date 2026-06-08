# Remote NCU Diagnostics and CUDA Graphs Results: OVH Measured Pass

- Date: `2026-04-04` UTC
- Live host: OVH `ovh_gra9_rtx5000_28` with Quadro RTX 5000, driver `580.126.09`, Ubuntu `24.04.3 LTS`, and green profiling readiness in `configs/systems/ovh_gra9_rtx5000_28.profiling_ready.json`
- Diagnostic command: `python -m aqs profile ncu --manifest workloads/manifests/imported/real_dense_ring6_batched.yaml --system-manifest configs/systems/ovh_gra9_rtx5000_28.yml --profile-mode diagnostic --graph-mode off`
- CUDA Graphs manifest: `configs/campaigns/cuda_graphs_ablation_v1.yaml`

## Diagnostic NCU Pass

- Real execution source: `cuquantum_tensornet_gpu`
- Run status: `success`
- Curated artifacts kept on this branch:
  - `artifacts/profiles/ncu/real_dense_ring6_batched.ncu.32f6e24969d9e164.profile_summary.json`
  - `artifacts/profiles/ncu/real_dense_ring6_batched.ncu.32f6e24969d9e164.ncu.csv`
- Heavy local-only artifacts intentionally not committed:
  - `artifacts/profiles/ncu/real_dense_ring6_batched.ncu.32f6e24969d9e164.ncu-rep`
  - `artifacts/profiles/ncu/real_dense_ring6_batched.ncu.32f6e24969d9e164.attempt.json`
  - `artifacts/profiles/ncu/real_dense_ring6_batched.ncu.32f6e24969d9e164.execution.json`
- Measured runtime for the profiled `graph_mode=off` pass:
  - TTFR: `70.823 s`
  - warm-contract phase total: `229.194 s`
  - wall: `367.738 s`
- Reduced profile summary highlights:
  - `125` kernels captured with `report_written=true`, `kernel_seen=true`, and `metrics_collected=true`
  - top kernels were cuTensor `tiny_mnk` contraction kernels
  - `launch_proxy_pct=100.0`, `occupancy_pct=4.606569`, `sm_util_pct=0.698625`
  - `reuse_signal=unlikely`
- Measured interpretation: this diagnostic slice was usable and real, but it remained strongly launch-bound on tiny-MNK contraction kernels rather than showing evidence of high SM saturation.

## CUDA Graphs A/B Campaign

- Cell count: `12`
- Run count: `36`
- Status counts: `12` `success`, `24` `runtime_error`
- Successes were limited to `graph_mode=off`:
  - `real_ghz3_amplitude.yaml`, repeat hint `8`: `6/6` success across the `off` cell, mean wall `30.643 ms`, mean steady iter `0.173 ms`
  - `real_ghz3_amplitude.yaml`, repeat hint `32`: `6/6` success across the `off` cell, mean wall `15.408 ms`, mean steady iter `0.136 ms`
  - `real_dense_ring6_batched.yaml`, repeat hint `8`: `6/6` success across the `off` cell, mean wall `48.372 ms`, mean steady iter `0.287 ms`
  - `real_dense_ring6_batched.yaml`, repeat hint `32`: `6/6` success across the `off` cell, mean wall `53.332 ms`, mean steady iter `0.265 ms`
- All `warm_only` and `steady_state` replicates failed with the same measured runtime error:
  - reason code: `graph_capture_failed`
  - reason: `CUDA Graph capture failed: cannot capture on the default (legacy) stream`
- Curated branch artifacts:
  - `artifacts/campaigns/cuda_graphs_ablation_v1/summary.json`
  - `artifacts/campaigns/cuda_graphs_ablation_v1/results.csv`
  - `artifacts/campaigns/cuda_graphs_ablation_v1/report.md`
  - `artifacts/campaigns/cuda_graphs_ablation_v1/plots/status_counts.svg`
  - `artifacts/campaigns/cuda_graphs_ablation_v1/plots/ttfr_by_cell.svg`
  - `artifacts/campaigns/cuda_graphs_ablation_v1/plots/repeat_roi_break_even.svg`

## Verdict

- Publish the Nsight Compute slice as a real measured diagnostic pass.
- Do not claim CUDA Graph speedups on this host. The current execution path failed every attempted graph capture before a successful replay could be measured.
- Measured recommendation for this stack branch: keep `graph_mode=off`.

## Notes

- The checked-in `configs/systems/ovh_gra9_rtx5000_28.yml` still carries older static host metadata. The live run above was verified against the refreshed readiness artifact and the actual host inventory, and the manifest refresh should follow in the packaging pass.
- Negative results were preserved as first-class evidence rather than hidden behind the successful `off` baselines.
