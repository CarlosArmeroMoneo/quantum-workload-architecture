# Quantum Workload Atlas — project overview

Quantum Workload Atlas (QWA) is a Python toolkit for studying the execution cost of quantum tensor-network workloads. The repository is named `quantum-workload-architecture`; its package and command-line interface are named `aqs`.

The engineering question is practical: **is a workload spending time on useful contraction work, on finding a plan, or on preparing and invoking the execution?** The project records enough context to inspect that distinction rather than reporting an unexplained timing number.

## Engineering scope

The pipeline validates workload and system manifests, normalizes supported inputs, probes tensor-network structure, proposes plans, runs the implemented single-GPU cuTensorNet path, checks numerical output, and combines execution timings with reduced Nsight evidence. Reports retain unsupported cases, failed probes, prediction errors, and negative experiments.

The project builds the workflow, measurement, analysis, and reusable execution-session layers around existing numerical libraries. It does not implement cuTensorNet itself, a new quantum algorithm, or accelerator hardware.

## What has been measured

**Canonical profiler-backed slice.** On OVH Quadro RTX 5000, `real_dense_ring6_batched` has load/conversion/postprocessing equal to 21.86% of its recorded phase time. The associated analysis nominates `launch_overhead`. This is a hypothesis supported by measured phases and a real profile, not a measured speedup or an exhaustive hardware diagnosis.

**Warm session experiment.** On three workloads on the OVH host, the recorded same-workload medians fall from 653–672 ms through the persistent CLI to 51–56 ms through an existing-worker session. This comparison concerns warm request wall time. It excludes cold worker startup and does not establish faster GPU kernels. The summary records unchanged plan selection, no correctness drift, and no fallback.

The [measured results](docs/reports/measured_results.md) provide exact values, denominators, source files, and limitations. Those two experiments must not be presented as one controlled before/after experiment.

## Current release and limits

The latest project release is [v0.2-crossover-calibration](https://github.com/CarlosArmeroMoneo/quantum-workload-architecture/releases/tag/v0.2-crossover-calibration), published June 8, 2026. It adds calibration and preflight tools while retaining the earlier accepted OVH evidence. The historical `v0.5.0-evidence` tag identifies a raw-artifact package, not a newer project release.

Real GPU execution is limited to single-GPU Qiskit/OpenQASM2 amplitude and batched-amplitude workloads. CUDA-Q is adapter-backed structural planning only. GCP A100 remains pending acceptance; local NVIDIA 6GB is preflight/dev only. H100, distributed GPU, Hyperstack, TPU/JAX, and QPU results are not established by this public package. The planner is not presented as a generally validated fastest-backend selector.

## Review and reproduce

Start with the [review guide](docs/reports/how_to_review_this_project.md), the [CPU quickstart](README.md#cpu-quickstart), and the [documentation index](docs/README.md). The CPU path checks workflow behavior, not historical GPU performance.

<details>
<summary>Supporting methodology</summary>

- [Public release audit](docs/reports/public_release_audit.md) and [canonical evidence index](docs/reports/first_real_profiler_slice_index.md).
- [Evidence contract](docs/architecture/evidence_contract.md), [profiler signal taxonomy](docs/architecture/profiler_signal_taxonomy.md), and [kernel taxonomy report](docs/reports/profiler_kernel_taxonomy_current_evidence.md).
- [Model calibration table](docs/reports/model_calibration_table.md).
- [Experiment card template](docs/experiments/experiment_card_template.md) and [launch-overhead counterfactual](docs/experiments/launch_overhead_counterfactual.md).
- [v0.1 release notes](docs/reports/v0_1_first_real_profiler_slice_release_notes.md), [v0.2 release notes](docs/reports/v0_2_crossover_release_notes.md), and [staged roadmap](docs/reports/next_pr_roadmap.md).

</details>
