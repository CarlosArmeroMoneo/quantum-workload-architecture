# Remote Repeat ROI Results: Blocked Locally

This branch exists to keep the stack honest. The `repeat_roi_v1` measured-results pass is not executable on the current workstation because it requires a Linux CUDA host with the real quantum/profiler stack installed.

## Blocker

- Current host: Windows workspace, no confirmed Linux CUDA runtime for campaign execution
- Required host class: single-GPU Linux CUDA node with `cupy`, `cuquantum`, `qiskit`, `ncu`, `nsys`, and `duckdb`
- Required campaign: [`configs/campaigns/repeat_roi_v1.yaml`](../../configs/campaigns/repeat_roi_v1.yaml)

## Remote Execution Checklist

1. Validate the host with `python -m aqs doctor --profiling --outdir artifacts/profiling_readiness`
2. Validate the campaign with `python -m aqs campaign validate --manifest configs/campaigns/repeat_roi_v1.yaml`
3. Run the measured campaign with `python -m aqs campaign run --manifest configs/campaigns/repeat_roi_v1.yaml --outdir artifacts/campaigns/repeat_roi_v1`
4. Re-render summaries with `python -m aqs campaign summarize --manifest configs/campaigns/repeat_roi_v1.yaml --outdir artifacts/campaigns/repeat_roi_v1`
5. Capture representative profiler subsets for the recommended cells from `summary.json`
6. Publish curated `summary.json`, `results.csv`, `report.md`, and selected profiler-derived evidence

## Expected Outputs

- `artifacts/campaigns/repeat_roi_v1/summary.json`
- `artifacts/campaigns/repeat_roi_v1/results.csv`
- `artifacts/campaigns/repeat_roi_v1/report.md`
- Curated profiler follow-up artifacts for representative cells
- Planner policy updates derived from measured ROI instead of the current dry-run structural model

## Merge Condition

Do not merge this branch as "complete results" until the remote host run has produced the outputs above and the report explicitly states whether the dry-run policy suggestions held up under measured execution.
