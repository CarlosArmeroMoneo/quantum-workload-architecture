# Quantum Workload Atlas v0.2 Crossover Calibration

Status: report skeleton. Not all experiments have been run.

## 1. Abstract

This report will calibrate when exact tensor-network workloads move from launch/setup dominated behavior to contraction-work dominated behavior. The current accepted evidence remains the OVH RTX 5000 profiler-backed slice.

## 2. Research Question

When do exact tensor-network quantum workloads move from launch/setup dominated to contraction-work dominated, and can Atlas predict that transition from workload/profiler evidence?

## 3. Evidence Tiers

Evidence tiers follow `docs/architecture/evidence_contract.md`. Local 6GB evidence is preflight only. GCP A100 remains pending until the acceptance gate passes.

## 4. Current Accepted OVH Result

The accepted current architecture nomination is `launch_overhead` from `real_profiler_analysis` on OVH `real_dense_ring6_batched`.

## 5. GCP A100 Pending Lane

The A100 lane is pending until a confirmed A100 host produces pinned execution, profile, accuracy, and artifact-manifest evidence that passes the offline acceptance gate.

## 6. Calibration Dataset Schema

The row schema is defined in `docs/architecture/calibration_dataset_schema.md`.

## 7. Crossover Classifier

The first classifier is a transparent heuristic implemented in `src/aqs/calibration.py`. It is not a final ML model.

## 8. Planned Workloads

The planned ladder is `configs/experiments/workload_scale_ladder_v0_2.yaml`. GHZ3 remains a sanity case, not a throughput benchmark.

## 9. Planned Hyperstack/GCP Campaigns

Hyperstack is prepared as a tightly capped mini-campaign. GCP A100 remains acceptance-gated and should not run until quota and artifact requirements are ready.

## 10. Expected Results

Expected results are classification rows and profiler-backed interpretation, not broad benchmark rankings.

## 11. Limitations

The current accepted dataset is narrow. Local laptop GPU results cannot support canonical public performance claims. TPU and QPU lanes remain future-only.

## 12. Next Experiments

- Run local 6GB preflight only for tiny sanity checks.
- Use the triage planner before spending cloud budget.
- Run the Hyperstack mini-campaign only within stop rules.
- Ingest future artifacts through the offline post-run workflow.
