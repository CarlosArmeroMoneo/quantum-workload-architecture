# OVH Persistent Executor Prototype Plan

## Scope

`stack/27-ovh-persistent-executor-prototype` turns the stack/26 worker investigation into a conservative local prototype.

This branch stays performance-only.

It does not:

- change planner ranking
- change Gate A
- change Gate B
- make a calibration claim
- relax compatibility checks

## Frozen Inputs

- stack/24 remains the one-shot reusable-bundle baseline
- stack/26 remains the persistent-executor investigation baseline
- Gate A and Gate B remain unchanged
- Gate P is added as a separate performance-only gate

## Prototype Goals

The branch succeeds only if the worker is:

- explicit to start, inspect, and stop
- strict about compatibility
- clear about provenance
- measurably faster on the canonical OVH trio
- operationally boring enough to support a follow-on productization branch

## User-Facing Surface

The prototype CLI surface is:

```bash
python -m aqs persistent-executor serve --socket /tmp/aqs-ovh.sock
python -m aqs persistent-executor ping --socket /tmp/aqs-ovh.sock
python -m aqs persistent-executor status --socket /tmp/aqs-ovh.sock
python -m aqs persistent-executor shutdown --socket /tmp/aqs-ovh.sock
```

Execution remains:

```bash
python -m aqs tnep execute \
  --manifest ... \
  --system-manifest ... \
  --plan-bundle ... \
  --persistent-worker-socket /tmp/aqs-ovh.sock \
  --execution-intent require_real
```

## Safety Expectations

- live socket refusal unless `--replace-live-worker`
- stale socket cleanup when the old socket is dead
- socket removal on graceful shutdown
- optional `--max-requests` and `--max-session-seconds`
- explicit reject reasons on every incompatible request
- no silent fallback to one-shot execution
- explicit `--allow-one-shot-fallback` only when the caller wants it

## Evidence Package

This branch should emit:

- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/summary.json`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/summary.md`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/per_request.csv`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/sequence_summary.json`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/sequence_summary.md`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/worker_health.jsonl`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/worker_health_start.json`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/worker_health_end.json`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/socket_recovery_checks.json`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/compatibility_reject_matrix.json`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/compatibility_reject_matrix.md`

## Decision Rule

If Gate P passes cleanly, the next branch should stay performance-only and target the remaining outer client / driver tax above the worker.

If Gate P fails operationally, keep the worker experimental and continue performance work without reopening planner ranking or calibration work.
