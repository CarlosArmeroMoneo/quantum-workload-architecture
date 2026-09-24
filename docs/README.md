# Documentation index

Start with the [project overview](../PROJECT_OVERVIEW.md), [measured results](reports/measured_results.md), and [review guide](reports/how_to_review_this_project.md). Older reports preserve their original experiments and decisions; a historical branch name or proposed next step is not a statement of current branch availability.

## Scope, evidence, and calibration

- [Public release audit](reports/public_release_audit.md), [historical capability audit](reports/current_state_truth_pass.md), and [canonical evidence index](reports/first_real_profiler_slice_index.md).
- [Evidence contract](architecture/evidence_contract.md), [profiler signal taxonomy](architecture/profiler_signal_taxonomy.md), and [kernel taxonomy report](reports/profiler_kernel_taxonomy_current_evidence.md).
- [Technical report v0.1](reports/quantum_workload_atlas_v0_1_report.md), [public evidence catalog](reports/public_evidence_catalog.md), and [catalog CSV](reports/public_evidence_catalog.csv).
- [Model calibration report](reports/model_calibration_current_evidence.md), [calibration table](reports/model_calibration_table.md), [dataset schema](architecture/calibration_dataset_schema.md), and [workload scale ladder](architecture/workload_scale_ladder.md).
- [v0.1 release notes](reports/v0_1_first_real_profiler_slice_release_notes.md), [v0.2 release notes](reports/v0_2_crossover_release_notes.md), [v0.2 report framework](reports/quantum_workload_atlas_v0_2_crossover_calibration.md), and [staged roadmap](reports/next_pr_roadmap.md).

## Measured OVH experiments

- [Evidence package index](reports/portfolio_index.md) and [demonstration runbook](runbooks/portfolio_demo.md).
- [Repeat-ROI foundation](reports/repeat_roi_foundation.md), [measured repeat-ROI results](reports/remote_repeat_roi_results_blocked.md), and [NCU/CUDA Graphs results](reports/remote_ncu_and_graphs_results_blocked.md).
- [CUDA-Q adapter and tiny-MNK results](reports/remote_cudaq_and_sidecar_results_blocked.md) and [tiny-MNK lab](../sidecars/tiny_mnk_lab/README.md). The sidecar is not a parity proxy for cuTensorNet's internal kernels.
- [Measured-validation follow-on](reports/ovh_measured_validation_follow_on.md), [baseline freeze](reports/ovh_v1_baseline.md), [top-three reconciliation](reports/ovh_top3_reconcile_note.md), and [merge-gate policy](reports/ovh_merge_gate_policy.md).
- [Calibration readout](reports/ovh_calibration_readout.md), [confidence validation](reports/ovh_confidence_validation_readout.md), [confidence defaulting](reports/ovh_confidence_defaulting_readout.md), and [time-to-first-result variance methodology](reports/ttfr_variance_methodology_v2.md).
- [Plan-reuse readout](reports/ovh_plan_reuse_prototype_readout.md), [persistent-executor plan](reports/ovh_persistent_executor_prototype_plan.md), [persistent-executor results](reports/ovh_persistent_executor_prototype_v1.md), and [Gate P policy](reports/ovh_gate_p_policy.md).
- [Session-runner plan](reports/ovh_session_runner_prototype_plan.md), [session-runner results](reports/ovh_session_runner_prototype_v1.md), [Gate S policy](reports/ovh_gate_s_policy.md), and [embedded-client results](reports/ovh_embedded_session_client_v1.md).

These experiments do not promote a planner retune or a new backend claim. CUDA Graph capture failed on the recorded default-stream path; no graph speedup is claimed. Existing-worker and autospawn request timings exclude different startup costs, so use each report's measurement definition.

## Reproduction and artifact handling

- [Canonical OVH rerun guide](runbooks/ovh_cu13_real_execution.md), [host session summary](runbooks/profiler_ovh_gra9_rtx5000_28_session.md), and [local-host limitations](known_limitations/profiler_host_blockers.md).
- [Persistent-executor runbook](runbooks/ovh_persistent_executor.md), [session-runner runbook](runbooks/ovh_session_runner.md), and [embedded-client runbook](runbooks/ovh_embedded_session_client.md).
- [Storage management](runbooks/storage_management.md), [run triage](runbooks/run_triage.md), and [post-run ingestion](runbooks/post_run_ingestion.md).

Small canonical summaries and selected experiment records are tracked under `evidence/` and `artifacts/`. Most local rerun outputs and all `release-assets/` remain ignored. Historical checksums identify their original packages; they are not a whole-repository integrity manifest for the evolving `main` branch. Private credentials belong outside Git.

## Planned or acceptance-gated work

- [GCP A100 status](reports/gcp_a100_portability_index.md) and [acceptance gate](runbooks/gcp_a100_acceptance_gate.md).
- [Local 6GB preflight](runbooks/local_6gb_preflight.md), [Hyperstack campaign plan](runbooks/hyperstack_crossover_campaign.md), and [accelerator-lab architecture](architecture/accelerator_lab_architecture.md).
- [Experiment-card template](experiments/experiment_card_template.md), [launch-overhead counterfactual](experiments/launch_overhead_counterfactual.md), and [counterfactual runbook](runbooks/launch_overhead_counterfactual_runbook.md).
- [Future TPU sister-workload design](architecture/tpu_sister_workload_lane.md).

These are plans, templates, or admission checks, not evidence of successful campaigns on the named devices.
