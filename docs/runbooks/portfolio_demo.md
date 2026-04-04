# Portfolio Demo Runbook

This is the canonical local demo path for the measured portfolio package frozen on April 4, 2026. It validates the implemented workflow, re-renders the package asset, and inspects the curated OVH measurements without re-running the full remote campaigns.

## 1. Activate the Canonical Shell

```bash
source .venv_cu13/bin/activate
source ~/qwa_cuda_env_cu13.sh
```

## 2. Validate the Foundations

```bash
python -m aqs manifest validate --mode implemented \
  workloads/manifests/generated/dense_universal_smoke.yaml \
  workloads/manifests/imported/cudaq_ghz3_amplitude.yaml \
  configs/campaigns/cpu_dry_run_v1.yaml
```

## 3. Run the CPU Campaign Demo

```bash
python -m aqs campaign run \
  --manifest configs/campaigns/cpu_dry_run_v1.yaml \
  --outdir artifacts/campaigns/cpu_dry_run_v1
```

## 4. Render the Portfolio Asset

```bash
python scripts/render_report_assets.py
```

## 5. Inspect the Curated Measured Summaries

```bash
python - <<'PY'
import json
from pathlib import Path

paths = {
    "repeat_roi": "artifacts/campaigns/repeat_roi_v1/summary.json",
    "graphs": "artifacts/campaigns/cuda_graphs_ablation_v1/summary.json",
    "cudaq": "artifacts/cudaq_adapter_compare/summary.json",
    "sidecar": "sidecars/tiny_mnk_lab/results/ncu/summary.json",
}
for label, path in paths.items():
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    print(f"== {label} ==")
    if label == "repeat_roi":
        print(payload["cell_count"], payload["run_count"], payload["status_counts"])
    elif label == "graphs":
        print(payload["cell_count"], payload["run_count"], payload["status_counts"])
    elif label == "cudaq":
        print(payload["host_profile"]["gpu_model"], len(payload["results"]))
    else:
        print(payload["benchmark"]["run_count"], payload["profile"]["shape_keys"])
PY
```

## 6. Know the Boundary

- Branches `stack/10` through `stack/12` are now backed by measured OVH host outputs and curated artifacts.
- The repeat-ROI pass was mostly negative, so the measured package keeps the existing planner defaults rather than lowering thresholds to `{2, 2}`.
- CUDA Graph capture failed on the default (legacy) stream in every measured attempt, so no graph speedup claim is made.
- CUDA-Q evidence is adapter-backed structural comparison plus matched Qiskit real-execution controls, not native CUDA-Q runtime execution.
- The tiny-MNK sidecar is measured, but it is not a parity proxy for the internal cuTensorNet tiny-MNK kernel family.
