#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${QWA_STORAGE_ENV:-$REPO_ROOT/qwa_storage.env}"
APPLY=0

usage() {
  cat <<'EOF'
Usage: scripts/gcp_sync_artifacts.sh [--apply] [--env PATH]

Syncs curated machine artifacts to Cloud Storage. Dry-run is the default.
Required env vars: QWA_GCP_PROJECT, QWA_GCS_BUCKET.
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

require_var QWA_GCP_PROJECT
require_var QWA_GCS_BUCKET

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

copy_file() {
  local src="$1"
  local dest_prefix="$2"
  local rel="${src#"$REPO_ROOT"/}"
  local dest="$bucket_url/$dest_prefix/$rel"
  run_cmd gcloud --project "$QWA_GCP_PROJECT" storage cp "$src" "$dest"
}

sync_dir_if_exists() {
  local src="$1"
  local dest_prefix="$2"
  if [[ -d "$src" ]]; then
    run_cmd gcloud --project "$QWA_GCP_PROJECT" storage rsync "$src" "$bucket_url/$dest_prefix" --recursive
  fi
}

classify_prefix() {
  local rel="$1"
  case "$rel" in
    evidence/*.execution.json|evidence/*.execute.*.json|evidence/*/*.execution.json|evidence/*/*.execute.*.json)
      printf '%s\n' "execution-payloads"
      ;;
    evidence/*.profile_summary.json|evidence/*.ncu.csv|evidence/*/*.profile_summary.json|evidence/*/*.ncu.csv|artifacts/profiles/*)
      printf '%s\n' "profile-summaries"
      ;;
    evidence/*.arch.json|evidence/*/*.arch.json)
      printf '%s\n' "architecture-outputs"
      ;;
    configs/profiling/*.artifacts.json|docs/reports/*_index.md|docs/reports/portfolio_release_manifest.json|SHA256SUMS.txt)
      printf '%s\n' "release-manifests"
      ;;
    artifacts/campaigns/*|artifacts/measured_validation_runs/*|artifacts/session_runner/*|artifacts/persistent_executor/*|artifacts/embedded_session/*)
      printf '%s\n' "batch-logs"
      ;;
    *)
      printf '%s\n' ""
      ;;
  esac
}

echo "==> Bucket: $bucket_url"
echo "==> Project: $QWA_GCP_PROJECT"

sync_dir_if_exists "$REPO_ROOT/release-assets" "profiler-artifacts/canonical/release-assets"

while IFS= read -r -d '' rel; do
  prefix="$(classify_prefix "$rel")"
  if [[ -n "$prefix" ]]; then
    copy_file "$REPO_ROOT/$rel" "$prefix"
  fi
done < <(git -C "$REPO_ROOT" ls-files -z \
  artifacts \
  configs/profiling \
  docs/reports \
  evidence \
  SHA256SUMS.txt)

echo "==> Artifact sync plan complete"
