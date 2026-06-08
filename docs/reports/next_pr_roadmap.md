# Next PR Roadmap

This roadmap keeps post-v0.1 work small and evidence-gated. Do not modify the v0.1 tag as part of these PRs.

| PR | Title | Goal | Expected Files | Dependency | No-GPU Safe |
| --- | --- | --- | --- | --- | --- |
| PR 1 | Post-v0.1 cleanup and public-release hardening | Make the released portfolio easier to review and keep public claims aligned | `README.md`, `PORTFOLIO.md`, `docs/reports/how_to_review_this_project.md` | v0.1 release | yes |
| PR 2 | Model calibration evidence table | Make prediction-vs-measurement analysis explicit and refreshable | `scripts/build_model_calibration_table.py`, `docs/reports/model_calibration_table.md`, tests | PR 1 | yes |
| PR 3 | GCP A100 acceptance validator | Validate candidate A100 artifacts offline before public claims | `configs/profiling/gcp_a100_acceptance_gate.yaml`, `scripts/validate_gcp_a100_acceptance.py`, fixture tests | PR 2 | yes |
| PR 4 | Profiler taxonomy report | Summarize profiler-derived kernel families from current evidence | `docs/reports/profiler_kernel_taxonomy_current_evidence.md`, optional summary script | PR 2 | yes |
| PR 5 | Experiment card template | Standardize counterfactual experiment design | `docs/experiments/experiment_card_template.md` | PR 1 | yes |
| PR 6 | GCP Batch dry-run refinement | Improve render-only GCP job generation without API calls | batch template, renderer tests, runbook | PR 3 | yes |
| PR 7 | TPU/JAX sister-lane design | Add future-only workload placeholders without runtime claims | TPU docs and placeholder manifests | PR 1 | yes |
| PR 8 | Evidence acceptance examples | Add accepted and rejected profiler-evidence examples | `docs/reports/public_evidence_catalog.md` | PR 1 | yes |

## Guardrails

- OVH RTX 5000 remains canonical.
- GCP A100 remains pending until pinned artifacts pass the acceptance gate.
- GHZ3 remains portability/calibration evidence, not throughput.
- TPU and QPU lanes stay future-only.
- No broad sweeps, dashboards, or runtime expansion in this phase.
