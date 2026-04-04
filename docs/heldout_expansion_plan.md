# Heldout Expansion Plan

The current OVH measured-validation baseline has `heldout_workload_count=1`, which is too small to use heldout metrics as a primary merge gate.

## Target

Add at least 4 new `heldout_family` manifests for real-host measured validation, covering:

- amplitude low repeat
- amplitude medium repeat
- batched medium repeat
- batched high repeat

## Requirements

Each new manifest must satisfy all of the following:

- `api_version: aqs.workload.v1`
- `source_format: qiskit`
- imported source path that already exists in the repo
- executable `execution_target`
- `split_tag: heldout_family`
- `family_id` not already represented in the training slice used by the OVH measured-validation manifest
- parameter metadata sufficient to distinguish repeat regime and circuit family

## Missing Inputs Today

- Additional imported real-host-compatible source circuits from families not already represented in the current training slice
- Enough low/medium/high repeat variants to build a heldout set without reusing the same family IDs already present in train

## Interim Policy

- Do not fabricate new heldout manifests without matching source circuits and real execution targets.
- When `heldout_workload_count < 5`, treat `heldout_mean_regret` as descriptive only and keep that warning in validation outputs.
