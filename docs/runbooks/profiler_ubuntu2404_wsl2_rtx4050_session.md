# Profiler Session Note: ubuntu2404_wsl2_rtx4050

This host is intentionally kept as a negative-control profiling environment.

## Summary

- Platform: Ubuntu 24.04 on WSL2 with an RTX 4050 Laptop GPU.
- Profiler source: container-bundled `nsys`, `QdstrmImporter`, and `ncu`.
- Outcome: useful for local debugging and failure classification, not for the canonical profiler-backed slice.

## Why It Is Not Canonical

- `QdstrmImporter` was blocked by a missing `libdw.so.1` dependency in the frozen container workflow.
- Nsight Compute remained blocked by host GPU counter policy before a reliable filtered capture could be proven.
- The canonical public evidence therefore comes from the OVH Ubuntu 25.04 RTX 5000 host, not from this WSL2 environment.

## Public-Facing Use

- Keep this record only as a reproducibility note for local debugging.
- Use generic mounts such as `/path/to/repo:/workspace` when adapting the container workflow.
- Do not treat this host as evidence for the public profiler-backed result.
