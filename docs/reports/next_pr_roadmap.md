# Next PR Roadmap

This roadmap keeps post-v0.1 work small and evidence-gated. Release tags should stay fixed except for explicit public-hygiene corrections.

| PR | Title | Goal | Expected Files | Dependency | No-GPU Safe |
| --- | --- | --- | --- | --- | --- |
| PR 1 | Post-v0.1 cleanup and public-release hardening | Make the released evidence package easier to review and keep public claims aligned | `README.md`, `PROJECT_OVERVIEW.md`, `docs/reports/how_to_review_this_project.md` | v0.1 release | yes |
| PR 2 | Model calibration evidence table | Make prediction-vs-measurement analysis explicit and refreshable | `scripts/build_model_calibration_table.py`, `docs/reports/model_calibration_table.md`, tests | PR 1 | yes |
| PR 3 | GCP A100 acceptance validator | Validate candidate A100 artifacts offline before public claims | `configs/profiling/gcp_a100_acceptance_gate.yaml`, `scripts/validate_gcp_a100_acceptance.py`, fixture tests | PR 2 | yes, implemented |
| PR 4 | Profiler taxonomy report | Summarize profiler-derived kernel families from current evidence | `scripts/summarize_kernel_taxonomy.py`, `docs/reports/profiler_kernel_taxonomy_current_evidence.md` | PR 2 | yes, implemented |
| PR 5 | Experiment card template | Standardize counterfactual experiment design | `docs/experiments/experiment_card_template.md`, `docs/experiments/launch_overhead_counterfactual.md` | PR 1 | yes, implemented |
| PR 6 | GCP Batch dry-run refinement | Improve render-only GCP job generation without API calls | batch template, renderer tests, runbook | PR 3 | yes |
| PR 7 | TPU/JAX sister-lane design | Add future-only workload placeholders without runtime claims | TPU docs and placeholder manifests | PR 1 | yes, implemented |
| PR 8 | Evidence acceptance examples | Add small accepted/rejected examples for profiler-evidence review | methodology docs and fixture tests | PR 3 | yes |
| PR 9 | Public release audit | Verify the public repo still reads as a technical evidence system with guarded claims | `docs/reports/public_release_audit.md`, `scripts/public_check.sh`, methodology tests | PR 1 | yes, implemented |

## Guardrails

- OVH RTX 5000 remains canonical.
- GCP A100 remains pending until pinned artifacts pass the acceptance gate.
- GHZ3 remains portability/calibration evidence, not throughput.
- TPU and QPU lanes stay future-only.
- No broad sweeps, dashboards, or runtime expansion in this phase.
