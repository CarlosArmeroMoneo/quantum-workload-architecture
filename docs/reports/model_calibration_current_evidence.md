# Model Calibration From Current Evidence

This report uses accepted tracked evidence only. It does not include the rejected local GCP L4 draft and does not claim a GCP A100 result.

The generated table lives in `docs/reports/model_calibration_table.md` and can be refreshed with:

```bash
python scripts/build_model_calibration_table.py
```

## Current Rows

| Run | Workload | Profiler | Predicted TTFR s | Actual TTFR s | TTFR ratio | Predicted iter ms | Actual iter ms | Iter ratio | Interpretation |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `run_219ba8a96d5d0d44` | GHZ3 amplitude | `nsys` | `0.497969` | `0.023177829` | `0.046545` | `4.996248` | `0.201421` | `0.040314` | tiny-workload overhead/cold-warm interpretation |
| `run_6e3b0bf4154a4a94` | dense ring6 batched | `ncu` | `0.480977` | `1.041988242` | `2.166399` | `6.649115` | `392.928316` | `59.094829` | canonical profiler-backed architecture nomination |

## Why Calibration Matters

The planner is useful only if its predictions remain honest against real runs. Atlas keeps prediction error visible so future changes can distinguish planner improvement from host overhead, profiler replay behavior, and tiny-workload artifacts.

## Current Predictors

- qubit count and source workload family
- contraction path cost
- largest intermediate
- workspace and cache workspace
- repeat count
- host and GPU target
- planner budget and reuse mode

## Measured Quantities

- TTFR
- steady iteration time
- GPU seconds
- peak workspace and memory
- phase timing from NVTX/runtime records
- profiler-derived kernel and phase signals

## Reading The Ratios

`ttfr_error_ratio = actual_ttfr / predicted_ttfr`

`iter_error_ratio = actual_iter_ms / predicted_iter_ms`

Ratios below `1.0` mean the model overpredicted time. Ratios above `1.0` mean the model underpredicted time.

## Interpretation

- GHZ3 amplitude is too small for throughput interpretation. It is still valuable because it exercises real `cuquantum_tensornet_gpu`, accuracy checks, and Nsight Systems reduction.
- Dense ring6 batched is the better public architecture slice. It exposes launch/setup overhead and a large steady-iteration prediction gap that should remain visible in future calibration work.
- The current evidence supports analysis and calibration discipline, not a planner retune.

## Error Modes

- Tiny-workload overhead: small jobs can be dominated by import, setup, launch, and postprocess phases.
- Profiler replay distortion: Nsight Compute replay can change timing enough that profile rows need interpretation.
- Environment startup/import overhead: Python and quantum framework startup can dominate very small cases.
- Host-specific launch overhead: the same workload shape can behave differently across local, OVH, and future GCP hosts.

## Proposed Next Calibration Features

- host overhead intercept
- profiler replay flag
- tiny-workload classifier
- uncertainty or abstention label when evidence is too narrow
- interpretation class tied to the evidence contract tier

## Next Calibration Work

- Keep prediction-error ratios in the warehouse mart and public evidence catalog.
- Add more accepted rows only after the A100 device identity gate passes.
- Separate portability validation from performance calibration in every report.
