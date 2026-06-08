# v0.2 Crossover Calibration Release Notes

Status: release note for the v0.2 crossover calibration and preflight planning layer.

## Release Boundary

This release prepares the next evidence-gated phase of Quantum Workload Atlas. It does not replace the current accepted evidence chain and does not promote any pending accelerator lane.

- OVH RTX 5000 remains the canonical accepted profiler-backed architecture slice.
- The accepted nomination remains `launch_overhead` from `real_profiler_analysis`.
- GCP A100 remains pending until confirmed A100 artifacts pass the offline acceptance gate.
- Local NVIDIA 6GB is a constrained preflight/dev host only.
- Hyperstack is future campaign preparation only; no Hyperstack result is claimed.
- TPU/JAX and QPU lanes remain future-only design lanes.

## What Changed

- Added a local 6GB NVIDIA preflight lane with a system template, runbook, optional probe script, and tests that prevent local evidence from satisfying public performance or A100 acceptance claims.
- Added a transparent crossover calibration classifier for setup-dominated, contraction-dominated, model-miscalibrated, tiny-workload-risk, and insufficient-evidence cases.
- Added a v0.2 workload scale ladder to keep tiny, small, medium, and repeated-structure cases distinct.
- Added an offline run triage planner that recommends local preflight, Hyperstack budget campaign, GCP quota wait, or do-not-run without launching GPU or cloud work.
- Added Hyperstack A100/A6000 campaign templates with budget caps, stop rules, and artifact requirements.
- Added post-run ingestion and crossover report tooling for future artifact directories.
- Added a bounded launch-overhead counterfactual plan and runbook.
- Added a v0.2 report skeleton so future runs answer a specific crossover calibration question.

## Public Hygiene

The release keeps local planning notes, private folders, rejected GCP draft files, profiler binaries, caches, and Antigravity/Gemini scratch work out of Git. Large or private artifacts remain outside the repository unless separately curated and pinned.

## Validation

The local release candidate was validated with:

```bash
git diff --check
python -m ruff check src tests scripts
python -m mypy src/aqs
python -m pytest -m "not gpu and not profiler" -q
bash -n scripts/local_gpu_probe.sh
python scripts/triage_run_target.py --help
python scripts/ingest_accelerator_run.py --help
python scripts/build_crossover_report.py --help
bash scripts/public_check.sh
```

No GPU, profiler, Hyperstack, GCP, TPU, or QPU execution is required to validate this release.
