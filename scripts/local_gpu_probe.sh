#!/usr/bin/env bash
set -euo pipefail

echo "==> Local NVIDIA identity"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,compute_cap --format=csv || nvidia-smi
else
  echo "nvidia-smi not found on PATH"
fi

PYTHON_CMD=""
if [[ -x ".venv/bin/python" ]]; then
  PYTHON_CMD=".venv/bin/python"
elif [[ -x ".venv/Scripts/python.exe" ]]; then
  PYTHON_CMD=".venv/Scripts/python.exe"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="python3"
fi

if [[ -z "$PYTHON_CMD" ]]; then
  echo "python not found on PATH"
  exit 0
fi

echo "==> Python import preflight"
"$PYTHON_CMD" - <<'PY'
import importlib.util

for name in ["aqs", "numpy", "yaml", "qiskit", "cupy", "cuquantum"]:
    status = "present" if importlib.util.find_spec(name) else "missing"
    print(f"{name}: {status}")
PY

echo "==> aqs doctor"
if "$PYTHON_CMD" -m aqs doctor --help >/dev/null 2>&1; then
  "$PYTHON_CMD" -m aqs doctor || true
else
  echo "aqs doctor is not available in this environment"
fi
