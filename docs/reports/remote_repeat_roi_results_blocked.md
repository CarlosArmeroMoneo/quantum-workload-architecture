# Remote Repeat ROI Results: OVH Measured Pass

- Date: `2026-04-04` UTC
- Host: OVH `ovh_gra9_rtx5000_28` with Quadro RTX 5000, driver `580.95.05`, CUDA 13 Python stack, and green profiling readiness in `configs/systems/ovh_gra9_rtx5000_28.profiling_ready.json`
- Manifest: `configs/campaigns/repeat_roi_v1.yaml`

## Campaign Outcome

- Cell count: `360`
- Run count: `1080`
- Status: `1080/1080` successful runs
- Execution source: `cuquantum_tensornet_gpu`
- Graph mode: `off` for the full repeat-ROI campaign
- Curated branch artifacts:
  - `artifacts/campaigns/repeat_roi_v1/summary.json`
  - `artifacts/campaigns/repeat_roi_v1/results.csv`
  - `artifacts/campaigns/repeat_roi_v1/report.md`

## Measured ROI Findings

- `repeat_roi.findings` contains `360` evaluated cells: `90` baseline, `44` positive, `20` neutral, and `206` negative.
- Among the `270` optimized cells, only `16.3%` were positive while `76.3%` were negative.
- Cache reuse without autotune was mixed rather than broadly beneficial: `21` positive, `19` neutral, `50` negative. The mean wall delta versus the no-opt baseline was `-0.014 ms`, with a median of `+0.037 ms`.
- Autotune was net harmful in both measured modes:
  - `autotune=true`, `reuse_cache=false`: `11` positive, `1` neutral, `78` negative; mean wall delta `+3.801 ms`, median `+4.482 ms`
  - `autotune=true`, `reuse_cache=true`: `12` positive, `78` negative; mean wall delta `+3.992 ms`, median `+4.540 ms`
- The best wins clustered on the smallest `real_ghz3_amplitude.yaml` cases plus a few `real_qaoa_ring4_batched.yaml` and `real_grid_shape6_amplitude.yaml` cache-reuse cases.
- The worst measured regression was `cell_1cb2e43f43d9a4b8` on `real_dense_ring6_amplitude.yaml` (`quick`, repeat `32`, autotune plus cache) at `+22.752 ms` versus the no-opt baseline.

## Policy Verdict

- The dry-run suggestion to lower both planner thresholds from `{disable_autotune_below_repeat: 6, disable_reuse_cache_below_repeat: 8}` to `{2, 2}` did not hold up under measured execution on this host.
- Measured evidence supports keeping autotune conservative. It was net negative in every repeat bucket tested.
- Reuse-cache did not show a clean global threshold. It helped selected workloads, but the measured pass does not justify a blanket lower threshold of `2`.
- The dry-run structural model was materially conservative on absolute timing here, so those dry-run policy suggestions should not be promoted without measured confirmation.
- Branch conclusion: reject the suggested `{2, 2}` override and keep the existing planner defaults unchanged.

## Notes

- This branch did not add dedicated profiler follow-up subsets beyond the readiness smoke. The generated `profile_candidate_nsys` and `profile_candidate_ncu` flags in `results.csv` and `report.md` were preserved for targeted follow-up in `stack/11`.
- Negative results are part of the measured record and were kept intact rather than filtered out.
