# Storage Management Runbook

Status: template.

This repo uses three storage tiers:

- Git stores source, configs, tests, docs, curated evidence summaries, and manifest references.
- GCP Cloud Storage stores machine artifacts: profiler outputs, execution payloads, batch logs, profile summaries, architecture outputs, and future GPU/TPU evidence.
- Google Drive My Drive stores human-facing material: reports, notes, screenshots, exported docs, and lightweight demo folders.

Do not store credentials, project IDs, bucket names, Drive paths, or raw profiler binaries in Drive docs or git.

## Local Config

Copy the template and fill it locally:

```bash
cp qwa_storage.env.example qwa_storage.env
```

Required variables:

- `QWA_GCP_PROJECT`: local GCP project ID.
- `QWA_GCS_BUCKET`: bucket name or `gs://` bucket URL.
- `QWA_GCS_LOCATION`: bucket location, chosen to match the active compute region.
- `QWA_DRIVE_ROOT`: local Google Drive for desktop root path.

`qwa_storage.env` is ignored by git.

## GCP Bucket Setup

Preview the bucket setup:

```bash
bash scripts/setup_gcp_storage.sh
```

Apply the setup:

```bash
bash scripts/setup_gcp_storage.sh --apply
```

The setup uses `gcloud storage`, uniform bucket-level access, public access prevention, and `configs/gcp/lifecycle_balanced.json`.

The balanced lifecycle policy keeps canonical profiler artifacts indefinitely while moving them to colder classes over time. Scratch profiler artifacts expire after 30 days. Batch and TPU run folders move to Nearline after 30 days and expire after 180 days unless promoted to canonical evidence.

## Artifact Upload

Preview artifact upload commands:

```bash
bash scripts/gcp_sync_artifacts.sh
```

Upload curated machine artifacts:

```bash
bash scripts/gcp_sync_artifacts.sh --apply
```

The sync script uploads tracked curated outputs to the prefixes defined in `configs/gcp/bucket_layout.yaml`. If local `release-assets/` exists, it is synced to the canonical profiler-artifact prefix.

## Drive Copy

Preview the human-facing Drive copy:

```bash
bash scripts/drive_sync_docs.sh
```

Copy docs into My Drive:

```bash
bash scripts/drive_sync_docs.sh --apply
```

Use Google Drive for desktop paths that Bash can resolve. On Windows, Git Bash paths are usually more reliable than raw backslash paths.

## Restore And Audit

List canonical profiler artifacts:

```bash
gcloud storage ls "$QWA_GCS_BUCKET/profiler-artifacts/canonical/" --recursive
```

Restore a curated prefix locally:

```bash
gcloud storage rsync "$QWA_GCS_BUCKET/profile-summaries/" restored/profile-summaries --recursive
```

Audit the repo-side storage policy:

```bash
bash -n scripts/setup_gcp_storage.sh scripts/gcp_sync_artifacts.sh scripts/drive_sync_docs.sh
python -m pytest tests/test_system_manifests.py -m "not gpu and not profiler" -q
bash scripts/public_check.sh
```

Reference docs:

- Cloud Storage classes: https://docs.cloud.google.com/storage/docs/storage-classes
- Object lifecycle management: https://docs.cloud.google.com/storage/docs/lifecycle
- Bucket locations: https://docs.cloud.google.com/storage/docs/bucket-locations
- `gcloud storage rsync`: https://docs.cloud.google.com/sdk/gcloud/reference/storage/rsync
- Drive for desktop: https://support.google.com/drive/answer/13401938
