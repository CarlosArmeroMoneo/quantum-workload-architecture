# Portfolio Demo Runbook

This is the canonical local demo path for the current portfolio package. It proves the implemented workflow without claiming the remote measured-result branches.

## 1. Validate the Foundations

```bash
python -m aqs manifest validate --mode implemented \
  workloads/manifests/generated/dense_universal_smoke.yaml \
  workloads/manifests/imported/cudaq_ghz3_amplitude.yaml \
  configs/campaigns/cpu_dry_run_v1.yaml
```

## 2. Run the CPU Campaign Demo

```bash
python -m aqs campaign run \
  --manifest configs/campaigns/cpu_dry_run_v1.yaml \
  --outdir artifacts/campaigns/cpu_dry_run_v1
```

## 3. Render the Portfolio Asset

```bash
python scripts/render_report_assets.py
```

## 4. Inspect the Sidecar Reference Catalog

```bash
python sidecars/tiny_mnk_lab/scripts/extract_reference_kernel.py \
  --input evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.ncu.csv \
  --profile-summary evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.profile_summary.json \
  --output sidecars/tiny_mnk_lab/config/observed_tiny_mnk_kernels.json
```

## 5. Know the Boundary

- Branches `stack/10` through `stack/12` are blocked until a Linux CUDA host is available.
- This demo does not claim measured repeat-ROI, diagnostic NCU, CUDA-Q runtime, or sidecar benchmark results.
