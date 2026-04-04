# Repeat ROI Foundation

This stage adds the local scaffolding for repeated-contraction ROI analysis without claiming measured GPU evidence yet.

- `configs/campaigns/repeat_roi_v1.yaml` remains the remote CUDA-host manifest.
- `configs/campaigns/repeat_roi_cpu_dry_run_v1.yaml` is the local dry-run proof that the matrix expansion, aggregation, and reporting logic work on this machine.
- `configs/planner/repeat_roi_policy.v1.yaml` is the first planner policy hook file. It is a dry-run starting point, not a measured recommendation.

What this stage does:

- Expands the small imported-QASM corpus with a GHZ4 source and paired amplitude/batched manifests.
- Adds repeat-ROI metrics to campaign summaries and reports.
- Produces break-even and amortization signals from campaign outputs so later remote branches can swap in measured evidence without redesigning the report schema.

What this stage does not claim:

- No GPU-backed repeat ROI numbers are claimed from local dry runs.
- No planner threshold in this branch should be treated as measured truth.
- The measured follow-on report now lives in [`docs/reports/remote_repeat_roi_results_blocked.md`](remote_repeat_roi_results_blocked.md), where the OVH host pass rejects lowering the planner thresholds to `{2, 2}`.
