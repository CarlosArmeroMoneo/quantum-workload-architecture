#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:-$HOME/quantum-workload-architecture}"
VENV_DIR="$REPO_DIR/.venv_cu13"
ENV_FILE="$HOME/qwa_cuda_env_cu13.sh"

echo "==> Repo dir: $REPO_DIR"
if [[ ! -d "$REPO_DIR" ]]; then
  echo "Repo directory does not exist: $REPO_DIR" >&2
  exit 1
fi

cd "$REPO_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> Creating virtual environment"
  python3 -m venv "$VENV_DIR"
else
  echo "==> Reusing existing virtual environment at $VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "==> Upgrading packaging tools"
python -m pip install --upgrade pip setuptools wheel

echo "==> Installing repo in editable mode"
python -m pip install -e .[db]

echo "==> Installing CUDA 13 / profiling runtime packages"
python -m pip install cupy-cuda13x
python -m pip install nvidia-cublas nvidia-curand nvidia-nvjitlink nvidia-cuda-runtime
python -m pip install nvidia-cusolver nvidia-cusparse
python -m pip install --no-cache-dir cuquantum-cu13 cuquantum-python-cu13
python -m pip install qiskit

echo "==> Writing CUDA environment helper"
python - <<'PY'
from pathlib import Path
import os
import stat
import sys

venv_root = Path(sys.prefix)
site_packages = sorted(venv_root.glob("lib/python*/site-packages"))
candidates = [
    "nvidia/cuda_runtime",
    "nvidia/cuda_nvrtc",
    "nvidia/curand",
    "nvidia/nvjitlink",
    "nvidia/cublas",
    "nvidia/cusparse",
    "nvidia/cusolver",
    "nvidia/cufft",
]
cuda_path = None
lib_dirs = []

for sp in site_packages:
    for rel in candidates:
        base = sp / rel
        libdir = base / "lib"
        if rel == "nvidia/cuda_runtime" and base.exists():
            cuda_path = base
        if libdir.exists():
            lib_dirs.append(str(libdir))

if cuda_path is None:
    for sp in site_packages:
        legacy = sp / "nvidia" / "cu13"
        if legacy.exists():
            cuda_path = legacy
            legacy_lib = legacy / "lib"
            if legacy_lib.exists():
                lib_dirs.insert(0, str(legacy_lib))
            break

if cuda_path is None:
    raise SystemExit("could not locate CUDA runtime files inside the virtual environment")

deduped_lib_dirs = []
seen = set()
for entry in lib_dirs:
    if entry in seen:
        continue
    seen.add(entry)
    deduped_lib_dirs.append(entry)

env_file = Path.home() / "qwa_cuda_env_cu13.sh"
lines = [
    "#!/usr/bin/env bash",
    f'export CUDA_PATH="{cuda_path}"',
    f'export LD_LIBRARY_PATH="{":".join(deduped_lib_dirs)}:${{LD_LIBRARY_PATH:-}}"',
]
env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
env_file.chmod(env_file.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

print(f"Wrote {env_file}")
print(f"CUDA_PATH={cuda_path}")
for entry in deduped_lib_dirs:
    print(f"LD_LIBRARY_PATH+= {entry}")
PY

echo "==> Activating CUDA environment helper"
source "$ENV_FILE"

echo "==> Quick import checks"
python - <<'PY'
import cupy
print("cupy:", cupy.__version__)
x = cupy.arange(8)
print("cupy smoke:", x)

import qiskit
print("qiskit:", getattr(qiskit, "__version__", "unknown"))

import cuquantum
print("cuquantum:", getattr(cuquantum, "__version__", "unknown"))

import cuquantum.tensornet as cutn
print("cuquantum.tensornet import: OK")
PY

echo "==> Done"
echo
echo "Next time you reconnect, run:"
echo "  cd $REPO_DIR"
echo "  source .venv_cu13/bin/activate"
echo "  source ~/qwa_cuda_env_cu13.sh"
