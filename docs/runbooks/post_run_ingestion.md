# Post-Run Ingestion Runbook

Status: offline workflow for future accelerator artifacts.

Use this workflow after a Hyperstack or GCP run has produced local artifacts. The scripts do not call cloud APIs and do not assume artifacts exist.

## Required Inputs

- System manifest.
- Workload manifest.
- Execution payload.
- Reduced profile summary.
- Optional architecture output.
- Optional artifact manifest or artifact directory.

## Ingest One Run

```bash
python scripts/ingest_accelerator_run.py \
  --system-manifest configs/systems/hyperstack_a100.template.yml \
  --workload-manifest workloads/manifests/imported/real_dense_ring6_batched.yaml \
  --execution-payload artifacts/example/run.execution.json \
  --profile-summary artifacts/example/run.profile_summary.json \
  --output artifacts/example/normalized_record.json
```

The output status is:

- `accepted` when real execution, correctness, host identity, and profile evidence pass.
- `pending` when artifacts are incomplete or sparse.
- `rejected` when the wrong host/device, missing real execution, or missing correctness makes interpretation unsafe.

## Build A Report

```bash
python scripts/build_crossover_report.py \
  --calibration-table-json artifacts/example/calibration_records.json \
  --out docs/reports/crossover_calibration_generated.md
```

Review the generated report before moving any artifact into a public evidence path.
