# OVH Session Runner

## Purpose

Use this runbook to execute a bundle-first request sequence against the local persistent worker on the canonical OVH host.

This is:

- local Unix-socket only
- single-worker
- single-user
- performance-only
- separate from Gate A, Gate B, and Gate P

It is not a ranking or calibration feature.

## Activate The Host Environment

```bash
cd ~/quantum-workload-architecture
source ~/qwa_cuda_env_cu13.sh
test -f ~/.qwa-secrets.sh && source ~/.qwa-secrets.sh || true
```

Use `.venv_cu13/bin/python` explicitly on this host so the worker, the thin client, and the benchmark harness all share the same interpreter.

## Existing-Worker Session

Start the worker:

```bash
.venv_cu13/bin/python -m aqs persistent-executor serve \
  --socket /tmp/aqs-ovh.sock
```

Run a bundle-first session against that worker:

```bash
.venv_cu13/bin/python -m aqs persistent-executor run-session \
  --socket /tmp/aqs-ovh.sock \
  --session-manifest benchmarks/sessions/ovh_gate_s_trio.yaml \
  --outdir artifacts/session_runner/manual_existing_worker
```

Stop the worker:

```bash
.venv_cu13/bin/python -m aqs persistent-executor shutdown \
  --socket /tmp/aqs-ovh.sock
```

## Autospawn Temporary Worker

Use this when you want one self-contained local session:

```bash
.venv_cu13/bin/python -m aqs persistent-executor run-session \
  --spawn-temp-worker \
  --socket /tmp/aqs-ovh-temp.sock \
  --session-manifest benchmarks/sessions/ovh_gate_s_trio.yaml \
  --outdir artifacts/session_runner/manual_autospawn
```

## Strict Compatibility

Default behavior is conservative:

- a compatible persistent bundle request runs
- an incompatible request fails clearly

One-shot fallback is explicit-only:

```bash
.venv_cu13/bin/python -m aqs persistent-executor run-session \
  --socket /tmp/aqs-ovh.sock \
  --session-manifest benchmarks/sessions/ovh_gate_s_trio.yaml \
  --allow-one-shot-fallback \
  --outdir artifacts/session_runner/manual_fallback
```

## Frozen Seed Bundles

The tracked seed bundles under `artifacts/plan_bundles/ovh_v2_seed/` are frozen benchmark inputs for the Gate S evidence chain.

Because bundle compatibility remains strict, later reruns on a different repo commit may require regenerating fresh compatible bundles first.

For live operational use, prefer generating a current bundle on the exact checkout you intend to execute.

## Gate S Benchmark

Run the canonical Gate S benchmark package:

```bash
.venv_cu13/bin/python scripts/benchmark_session_runner.py \
  --outdir artifacts/session_runner/ovh_session_runner_prototype_v1
```

The curated artifact package lands under:

- `artifacts/session_runner/ovh_session_runner_prototype_v1/summary.json`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/summary.md`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/per_request.csv`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/sequence_summary.json`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/sequence_summary.md`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/request_trace.jsonl`
- `artifacts/session_runner/ovh_session_runner_prototype_v1/worker_health.jsonl`

## Interpretation Guardrail

Use session mode to reduce outer client/session overhead above the persistent worker.

Do not describe it as:

- a ranking improvement
- a calibration improvement
- a Gate A or Gate B change
- a new backend capability claim
