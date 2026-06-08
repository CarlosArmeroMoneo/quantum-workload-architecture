#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${QWA_STORAGE_ENV:-$REPO_ROOT/qwa_storage.env}"
LIFECYCLE_FILE="$REPO_ROOT/configs/gcp/lifecycle_balanced.json"
APPLY=0

usage() {
  cat <<'EOF'
Usage: scripts/setup_gcp_storage.sh [--apply] [--env PATH]

Creates or updates the configured Cloud Storage bucket. Dry-run is the default.
Required env vars: QWA_GCP_PROJECT, QWA_GCS_BUCKET, QWA_GCS_LOCATION.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
      ;;
    --env)
      ENV_FILE="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

strip_cr_var() {
  local name="$1"
  local value="${!name:-}"
  value="${value%$'\r'}"
  printf -v "$name" '%s' "$value"
}

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "$name is required; set it in qwa_storage.env or the environment" >&2
    exit 1
  fi
}

strip_cr_var QWA_GCP_PROJECT
strip_cr_var QWA_GCS_BUCKET
strip_cr_var QWA_GCS_LOCATION

require_var QWA_GCP_PROJECT
require_var QWA_GCS_BUCKET
require_var QWA_GCS_LOCATION

if [[ "$APPLY" -eq 1 ]] && ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud CLI is required for --apply" >&2
  exit 1
fi

bucket_name="${QWA_GCS_BUCKET#gs://}"
bucket_name="${bucket_name%/}"
bucket_url="gs://$bucket_name"

print_cmd() {
  printf 'DRY-RUN:'
  printf ' %q' "$@"
  printf '\n'
}

run_cmd() {
  if [[ "$APPLY" -eq 1 ]]; then
    "$@"
  else
    print_cmd "$@"
  fi
}

echo "==> Bucket: $bucket_url"
echo "==> Project: $QWA_GCP_PROJECT"
echo "==> Location: $QWA_GCS_LOCATION"

if [[ "$APPLY" -eq 1 ]]; then
  if gcloud --project "$QWA_GCP_PROJECT" storage buckets describe "$bucket_url" >/dev/null 2>&1; then
    echo "==> Updating existing bucket"
    run_cmd gcloud --project "$QWA_GCP_PROJECT" storage buckets update "$bucket_url" \
      --uniform-bucket-level-access \
      --public-access-prevention \
      --lifecycle-file="$LIFECYCLE_FILE"
  else
    echo "==> Creating bucket"
    run_cmd gcloud --project "$QWA_GCP_PROJECT" storage buckets create "$bucket_url" \
      --location="$QWA_GCS_LOCATION" \
      --default-storage-class=STANDARD \
      --uniform-bucket-level-access \
      --public-access-prevention \
      --lifecycle-file="$LIFECYCLE_FILE"
  fi
else
  run_cmd gcloud --project "$QWA_GCP_PROJECT" storage buckets describe "$bucket_url"
  run_cmd gcloud --project "$QWA_GCP_PROJECT" storage buckets create "$bucket_url" \
    --location="$QWA_GCS_LOCATION" \
    --default-storage-class=STANDARD \
    --uniform-bucket-level-access \
    --public-access-prevention \
    --lifecycle-file="$LIFECYCLE_FILE"
  run_cmd gcloud --project "$QWA_GCP_PROJECT" storage buckets update "$bucket_url" \
    --uniform-bucket-level-access \
    --public-access-prevention \
    --lifecycle-file="$LIFECYCLE_FILE"
fi

echo "==> Storage setup check complete"
