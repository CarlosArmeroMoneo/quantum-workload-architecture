# GCP Batch GPU Sweeps

Status: roadmap.

This is a future orchestration lane for running repeated GPU profiler captures through GCP Batch or equivalent Compute Engine automation.

## Intended Use

- Launch repeatable single-GPU jobs for validated workload manifests.
- Store execution payloads, profiler summaries, and raw profiler binaries in external artifact storage.
- Publish only curated summaries or pinned release manifests to git.

## Current Boundary

The repository now includes a render-only Batch template:

- Template: `configs/gcp/batch_job_templates/gpu_profile_job.template.json`
- Renderer: `scripts/render_gcp_batch_job.py`

Preview a job JSON without submitting anything:

```bash
python scripts/render_gcp_batch_job.py
```

Write a rendered job JSON for inspection:

```bash
python scripts/render_gcp_batch_job.py --out artifacts/gcp/rendered_gpu_profile_job.json
```

This is still an offline preparation lane. The renderer does not call GCP APIs, does not create a Batch job, and does not change the pending A100 evidence policy.
