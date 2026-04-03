# Portfolio Index

![Portfolio stack status](assets/portfolio_status.svg)

This index packages the stacked-branch rollout as it exists in this workspace on April 3, 2026.

## Completed Foundations

- `stack/00-truth-capability-matrix`: [`docs/reports/current_state_truth_pass.md`](current_state_truth_pass.md)
- `stack/04-campaign-runner-and-reporting`: CPU-safe campaign runner via [`configs/campaigns/cpu_dry_run_v1.yaml`](../../configs/campaigns/cpu_dry_run_v1.yaml)
- `stack/05-repeat-roi-foundation`: [`docs/reports/repeat_roi_foundation.md`](repeat_roi_foundation.md)
- `stack/07-cuda-graphs-foundation`: graph-mode plumbing and [`configs/campaigns/cuda_graphs_ablation_v1.yaml`](../../configs/campaigns/cuda_graphs_ablation_v1.yaml)
- `stack/08-cudaq-adapter`: adapter-backed CUDA-Q manifests under [`workloads/manifests/imported`](../../workloads/manifests/imported)
- `stack/09-tiny-mnk-sidecar-foundation`: [`sidecars/tiny_mnk_lab/README.md`](../../sidecars/tiny_mnk_lab/README.md)

## Blocked Remote Result Branches

- `stack/10-remote-repeat-roi-results`: [`docs/reports/remote_repeat_roi_results_blocked.md`](remote_repeat_roi_results_blocked.md)
- `stack/11-remote-ncu-and-graphs-results`: [`docs/reports/remote_ncu_and_graphs_results_blocked.md`](remote_ncu_and_graphs_results_blocked.md)
- `stack/12-remote-cudaq-and-sidecar-results`: [`docs/reports/remote_cudaq_and_sidecar_results_blocked.md`](remote_cudaq_and_sidecar_results_blocked.md)

## Release Package

- Curated manifest: [`docs/reports/portfolio_release_manifest.json`](portfolio_release_manifest.json)
- Checksums: [`SHA256SUMS.txt`](../../SHA256SUMS.txt)
- Demo runbook: [`docs/runbooks/portfolio_demo.md`](../runbooks/portfolio_demo.md)

## Notes

- The stack is intentionally truthful about the blocker boundary: branches `10` through `12` are not measured-result claims on this machine.
- The packaging branch freezes the current curated report set and records what is complete versus what still requires a Linux CUDA host.
