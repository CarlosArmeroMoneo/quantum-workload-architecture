# OVH Persistent Executor

## Purpose

Use this runbook to start, inspect, benchmark, and stop the local persistent real-execution worker on the canonical OVH CUDA 13 host.

This is a local Unix-socket prototype.

It is:

- single-worker
- single-user
- performance-only
- separate from Gate A and Gate B

It is not a ranking or calibration feature.

## Activate The Host Environment

```bash
cd ~/quantum-workload-architecture
source .venv_cu13/bin/activate
source ~/qwa_cuda_env_cu13.sh
test -f ~/.qwa-secrets.sh && source ~/.qwa-secrets.sh || true
```

## Worker Lifecycle

Start the worker:

```bash
python -m aqs persistent-executor serve \
  --socket /tmp/aqs-ovh.sock
```

Ping the worker:

```bash
python -m aqs persistent-executor ping \
  --socket /tmp/aqs-ovh.sock
```

Inspect detailed status:

```bash
python -m aqs persistent-executor status \
  --socket /tmp/aqs-ovh.sock
```

Shut the worker down:

```bash
python -m aqs persistent-executor shutdown \
  --socket /tmp/aqs-ovh.sock
```

Optional lifecycle bounds:

```bash
python -m aqs persistent-executor serve \
  --socket /tmp/aqs-ovh.sock \
  --max-requests 16 \
  --max-session-seconds 900
```

Replace a live worker only when you mean to restart the session:

```bash
python -m aqs persistent-executor serve \
  --socket /tmp/aqs-ovh.sock \
  --replace-live-worker
```

## Compatible Execute Flow

Seed a strict reusable plan bundle first:

```bash
python -m aqs tnep execute \
  --manifest workloads/manifests/imported/ovh_v2/01_real_dense_ring6_amplitude.yaml \
  --system-manifest configs/systems/ovh_gra9_rtx5000_28.yml \
  --objective ttfr \
  --probe-strategy real_if_available \
  --planner-budget balanced \
  --measurement-repeats 3 \
  --execution-intent require_real \
  --no-allow-distributed \
  --plan-bundle artifacts/persistent_executor/manual/01.plan_bundle.json \
  --out artifacts/persistent_executor/manual/01.seed.execute.json
```

Run a compatible persistent bundle hit:

```bash
python -m aqs tnep execute \
  --manifest workloads/manifests/imported/ovh_v2/01_real_dense_ring6_amplitude.yaml \
  --system-manifest configs/systems/ovh_gra9_rtx5000_28.yml \
  --objective ttfr \
  --probe-strategy real_if_available \
  --planner-budget balanced \
  --measurement-repeats 3 \
  --execution-intent require_real \
  --no-allow-distributed \
  --plan-bundle artifacts/persistent_executor/manual/01.plan_bundle.json \
  --persistent-worker-socket /tmp/aqs-ovh.sock \
  --out artifacts/persistent_executor/manual/01.persistent.execute.json
```

## Conservative Fallback

Default behavior is strict:

- compatible persistent execution is used, or
- the command fails clearly

If you explicitly want a one-shot fallback, opt in:

```bash
python -m aqs tnep execute \
  --manifest workloads/manifests/imported/ovh_v2/01_real_dense_ring6_amplitude.yaml \
  --system-manifest configs/systems/ovh_gra9_rtx5000_28.yml \
  --objective ttfr \
  --probe-strategy real_if_available \
  --planner-budget balanced \
  --measurement-repeats 3 \
  --execution-intent require_real \
  --no-allow-distributed \
  --plan-bundle artifacts/persistent_executor/manual/01.plan_bundle.json \
  --persistent-worker-socket /tmp/aqs-ovh.sock \
  --allow-one-shot-fallback \
  --out artifacts/persistent_executor/manual/01.fallback.execute.json
```

The output payload should then show:

- `persistent_executor_provenance.requested = true`
- `persistent_executor_provenance.persistent_used = false`
- `persistent_executor_provenance.fallback_used = true`
- a non-empty `fallback_reason`
- top-level `execution_mode = direct_executor`

## Gate P Benchmark

Run the canonical persistent prototype benchmark:

```bash
python scripts/benchmark_persistent_executor.py \
  --manifest workloads/manifests/imported/ovh_v2/01_real_dense_ring6_amplitude.yaml \
  --manifest workloads/manifests/imported/ovh_v2/06_star_graph_phase_amplitude_heldout_low.yaml \
  --manifest workloads/manifests/imported/ovh_v2/08_parity_iqp_batched_heldout_medium.yaml \
  --system-manifest configs/systems/ovh_gra9_rtx5000_28.yml \
  --execution-intent require_real \
  --benchmark-repeats 5 \
  --outdir artifacts/persistent_executor/ovh_persistent_executor_prototype_v1
```

The curated prototype artifact package lands under:

- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/summary.json`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/summary.md`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/per_request.csv`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/sequence_summary.json`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/sequence_summary.md`
- `artifacts/persistent_executor/ovh_persistent_executor_prototype_v1/worker_health.jsonl`

## Session Runner Layer

The session runner is the next local layer above the worker.

It stays performance-only and is tracked under Gate S, not Gate P.

Run it against an existing worker:

```bash
.venv_cu13/bin/python -m aqs persistent-executor run-session \
  --socket /tmp/aqs-ovh.sock \
  --session-manifest benchmarks/sessions/ovh_gate_s_trio.yaml \
  --outdir artifacts/session_runner/manual_existing_worker
```

Or let it autospawn a temporary worker:

```bash
.venv_cu13/bin/python -m aqs persistent-executor run-session \
  --spawn-temp-worker \
  --socket /tmp/aqs-ovh-temp.sock \
  --session-manifest benchmarks/sessions/ovh_gate_s_trio.yaml \
  --outdir artifacts/session_runner/manual_autospawn
```

See `docs/runbooks/ovh_session_runner.md` for the dedicated runbook and Gate S benchmark flow.

## Interpretation Guardrail

Use this feature to reduce end-to-end latency on repeated compatible requests.

Do not describe it as:

- a planner improvement
- a calibration win
- a new backend capability
- a Gate A or Gate B change
