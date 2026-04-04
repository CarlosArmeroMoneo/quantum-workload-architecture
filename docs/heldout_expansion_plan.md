# OVH Heldout Expansion v1

This document defines the next benchmark milestone after confidence-aware validation defaulting. The goal is to expand the OVH real-host heldout slice so heldout metrics become meaningful for merge decisions.

## Why This Is Next

- The frozen OVH baseline is now solid enough to act as the reference point.
- Confidence-aware validation strengthens the current `no retune yet` conclusion.
- Heldout coverage is still too thin: the current baseline has `heldout_workload_count=1`.
- Until the heldout slice reaches at least `5` workloads, heldout metrics remain descriptive and should not drive planner retunes by themselves.

## Target

Add at least `4` new `heldout_family` manifests so the OVH heldout slice reaches `heldout_workload_count >= 5`.

Required coverage:

- amplitude low repeat
- amplitude medium repeat
- batched medium repeat
- batched high repeat

## Manifest Requirements

Each new heldout manifest must satisfy all of the following:

- `api_version: aqs.workload.v1`
- `source_format: qiskit`
- imported source path that already exists in the repo
- executable `execution_target`
- `split_tag: heldout_family`
- `family_id` not already represented in the training slice used by the OVH measured-validation manifest
- parameter metadata sufficient to distinguish repeat regime and circuit family

## Benchmark Outputs Required

Once the new heldout manifests exist, the milestone must:

- rerun Gate A: the top-2 `require_real` OVH slice
- rerun Gate B: the OVH top-3 slice
- regenerate `summary.json`
- regenerate `confidence_summary.json`
- regenerate `confidence_summary.md`

## Current Blockers

The repo does not yet contain enough real-host-compatible imported source circuits from genuinely new family IDs to satisfy the target coverage without reusing the current training families.

Needed inputs are:

- additional imported real-host-compatible amplitude workloads
- additional imported real-host-compatible batched workloads
- repeat variants that cover low, medium, and high repeat regimes
- family IDs not already present in the current training slice

## Policy Until Expansion Lands

- Do not fabricate heldout workloads or synthetic stand-ins.
- Keep the validation warning when `heldout_workload_count < 5`.
- Treat heldout metrics as descriptive until the threshold is reached.
- Do not use a thin heldout slice as the sole justification for a planner behavior change.
