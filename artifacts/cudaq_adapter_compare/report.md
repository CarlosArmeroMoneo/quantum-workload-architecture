# CUDA-Q Adapter Comparison Summary

- Generated: `2026-04-04T12:49:10.931574+00:00`
- Host: `Quadro RTX 5000`, driver `580.95.05`, OS `Ubuntu 25.04`
- CUDA-Q package version: `0.14.0`
- Truth boundary: the `cudaq` package is installed, but this repo still routes `source_format: cudaq` through an adapter-backed normalization/probe path and does not expose native real CUDA-Q execution.

## ghz3_amplitude

- IR comparable keys match: `True`
- Interaction graph match excluding kind: `True`
- Probe largest intermediate match: `True`
- Probe optimizer cost match: `True`
- CUDA-Q manifest real execute status: `runtime_error` (unsupported_source_format: real cuTensorNet execution currently supports source_format='qiskit' only)
- Qiskit manifest real execute status: `success` via `cuquantum_tensornet_gpu`
- Qiskit measured runtime: TTFR `0.044028 s`, wall `0.045965 s`, steady iter `0.237200 ms`

## dense_ring6_batched

- IR comparable keys match: `True`
- Interaction graph match excluding kind: `True`
- Probe largest intermediate match: `True`
- Probe optimizer cost match: `True`
- CUDA-Q manifest real execute status: `runtime_error` (unsupported_source_format: real cuTensorNet execution currently supports source_format='qiskit' only)
- Qiskit manifest real execute status: `success` via `cuquantum_tensornet_gpu`
- Qiskit measured runtime: TTFR `0.066752 s`, wall `0.068773 s`, steady iter `0.284760 ms`
