# GCP Batch GPU Sweeps

Status: future dry-run orchestration only.

This is a future orchestration lane for running repeated GPU profiler captures through GCP Batch or equivalent Compute Engine automation. The current repository only renders job JSON for inspection; it does not call GCP APIs, submit Batch jobs, run GPUs, or create accepted evidence.

## Intended Use

- Render repeatable single-node GPU profiler jobs for validated workload manifests.
- Store execution payloads, profiler summaries, and raw profiler binaries in external artifact storage.
- Publish only curated summaries or pinned release manifests to git.
- Run the GCP A100 acceptance gate after any future capture before making an A100 evidence claim.

## Current Boundary

The repository now includes a render-only Batch template:

- Template: `configs/gcp/batch_job_templates/gpu_profile_job.template.json`
- Renderer: `scripts/render_gcp_batch_job.py`

Preview a job JSON without submitting anything:

```bash
python scripts/render_gcp_batch_job.py \
  --template configs/gcp/batch_job_templates/gpu_profile_job.template.json \
  --workload workloads/manifests/imported/real_dense_ring6_batched.yaml \
  --system configs/systems/gcp_a100_sxm4_40gb.yml \
  --profiler ncu \
  --output-prefix gs://BUCKET/qwa/runs/example \
  --job-name qwa-a100-batched-ncu
```

Write a rendered job JSON for inspection:

```bash
python scripts/render_gcp_batch_job.py \
  --template configs/gcp/batch_job_templates/gpu_profile_job.template.json \
  --workload workloads/manifests/imported/real_dense_ring6_batched.yaml \
  --system configs/systems/gcp_a100_sxm4_40gb.yml \
  --profiler ncu \
  --output-prefix gs://BUCKET/qwa/runs/example \
  --job-name qwa-a100-batched-ncu \
  --out artifacts/gcp/rendered_gpu_profile_job.json
```

The rendered spec contains dry-run labels and environment variables, including `QWA_DRY_RUN=true`. It is a review artifact, not proof that a job ran.

## Before Any Batch Sweep

- A single-node validation case must pass first.
- For the A100 lane, candidate artifacts must pass `scripts/validate_gcp_a100_acceptance.py`.
- The workload list must stay curated; no broad workload sweep is part of the current accepted evidence.
- The local render should be reviewed for concrete workload/system paths and a concrete GCS output prefix.

## Budget Stop Rules

- Keep the workload count small and curated.
- Set a maximum wall time with `--max-run-duration`.
- Delete or stop resources after a submitted future run completes.
- Do not start broad sweeps before the single-case lane is accepted.
- Stop if profiler summaries are missing, synthetic, or fail the relevant acceptance gate.

## Artifact Sync Requirements

- Store execution payloads, profile summaries, raw profiler artifacts, and architecture outputs under the configured GCS prefix.
- Keep raw heavyweight artifacts out of git.
- Promote only reduced summaries or pinned release manifests after review.
- Run the acceptance gate after future A100 runs and before updating public evidence indexes.
