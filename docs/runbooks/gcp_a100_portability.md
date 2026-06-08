# GCP A100 Portability Runbook

Status: future lane.

Use this runbook only after provisioning a confirmed A100 40GB host. The lane is a portability/profiler validation, not a throughput benchmark.

## Required Host

- Provider: GCP Compute Engine.
- Machine family: A2 standard.
- Machine type: `a2-highgpu-1g`.
- Accelerator: `nvidia-tesla-a100`.
- Expected NCU display name: `NVIDIA A100-SXM4-40GB`.
- Expected compute capability: `8.0`.

Do not use `g2-standard-*` or `nvidia-l4` for this lane.

The future-host template is `configs/systems/gcp_a100_sxm4_40gb.yml`. It is not evidence by itself.

## Validation Commands

```bash
nvidia-smi
python -m aqs doctor --profiling --outdir artifacts/readiness/gcp_a100_sxm4_40gb
python -m aqs profile ncu \
  --manifest workloads/manifests/imported/real_ghz3_amplitude.yaml \
  --system-manifest configs/systems/gcp_a100_sxm4_40gb.yml \
  --measurement-repeats 1 \
  --execution-intent require_real \
  --planner-budget balanced \
  --plan-rank 1 \
  --no-allow-distributed \
  --outdir artifacts/profiles/gcp_a100_sxm4_40gb/ncu
```

## Success Conditions

- The payload succeeds with real `cuQuantum` execution.
- Accuracy checks pass.
- NCU captures cuTensorNet contraction kernels.
- The profile summary marks the tiny GHZ workload as overhead dominated.
- The result is documented as portability validation and does not replace the OVH canonical slice.
