#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${QWA_STORAGE_ENV:-$REPO_ROOT/qwa_storage.env}"
APPLY=0

usage() {
  cat <<'EOF'
Usage: scripts/drive_sync_docs.sh [--apply] [--env PATH]

Copies human-facing project material into Google Drive for desktop. Dry-run is the default.
Required env var: QWA_DRIVE_ROOT.
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

strip_cr_var QWA_DRIVE_ROOT

if [[ -z "${QWA_DRIVE_ROOT:-}" ]]; then
  echo "QWA_DRIVE_ROOT is required; set it in qwa_storage.env or the environment" >&2
  exit 1
fi

drive_root="${QWA_DRIVE_ROOT%/}"
target="$drive_root/Quantum Workload Atlas"

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

copy_path() {
  local src="$1"
  local dest="$2"
  if [[ -e "$src" ]]; then
    run_cmd cp -R "$src" "$dest"
  fi
}

echo "==> Drive target: $target"
run_cmd mkdir -p "$target/docs" "$target/docs/reports" "$target/docs/runbooks" "$target/docs/architecture" "$target/docs/known_limitations"

copy_path "$REPO_ROOT/README.md" "$target/"
copy_path "$REPO_ROOT/SHA256SUMS.txt" "$target/"
copy_path "$REPO_ROOT/docs/reports/." "$target/docs/reports/"
copy_path "$REPO_ROOT/docs/runbooks/." "$target/docs/runbooks/"
copy_path "$REPO_ROOT/docs/architecture/." "$target/docs/architecture/"
copy_path "$REPO_ROOT/docs/known_limitations/." "$target/docs/known_limitations/"

echo "==> Drive copy plan complete"
