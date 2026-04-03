# Remote NCU Diagnostics and CUDA Graphs Results: Blocked Locally

The diagnostic Nsight Compute pass and the CUDA Graphs A/B pass depend on the same Linux CUDA host class as the measured campaign branches. This workstation only carries the foundation code and manifests.

## Blocker

- No local Linux CUDA host with the validated Nsight toolchain
- No local ability to confirm whether CUDA Graph capture is supported, useful, or a negative result for the canonical workloads

## Remote Execution Checklist

1. Confirm profiler readiness with `python -m aqs doctor --profiling`
2. Run diagnostic NCU on the representative measured workload:
   `python -m aqs profile ncu --manifest workloads/manifests/imported/real_dense_ring6_batched.yaml --system-manifest configs/systems/ovh_gra9_rtx5000_28.yml --profile-mode diagnostic --graph-mode off`
3. Run the CUDA Graphs ablation campaign:
   `python -m aqs campaign run --manifest configs/campaigns/cuda_graphs_ablation_v1.yaml --outdir artifacts/campaigns/cuda_graphs_ablation_v1`
4. Re-render campaign outputs with `python -m aqs campaign summarize --manifest configs/campaigns/cuda_graphs_ablation_v1.yaml --outdir artifacts/campaigns/cuda_graphs_ablation_v1`
5. Record explicit negative-result reporting if graph capture is unsupported or degrades performance

## Expected Outputs

- Enriched `profile_summary.json` for the diagnostic NCU slice
- `artifacts/campaigns/cuda_graphs_ablation_v1/summary.json`
- `artifacts/campaigns/cuda_graphs_ablation_v1/results.csv`
- `artifacts/campaigns/cuda_graphs_ablation_v1/report.md`
- Curated notes stating whether `off`, `warm_only`, or `steady_state` was the best practical setting

## Merge Condition

This branch remains blocked until the measured diagnostic NCU summary and the CUDA Graphs ablation report are both published, including an explicit statement if the best outcome is "leave graph_mode=off".
