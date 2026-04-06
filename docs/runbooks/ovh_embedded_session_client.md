# OVH Embedded Session Client

## Purpose

Use this runbook to drive the local persistent worker from a reusable Python API instead of invoking the CLI once per request.

This path is:

- local Unix-socket only
- single-worker
- single-user
- experimental
- performance-only
- separate from Gate A, Gate B, Gate P, and Gate S semantics

It is not a ranking or calibration feature.

## Activate The Host Environment

```bash
cd ~/quantum-workload-architecture
source ~/qwa_cuda_env_cu13.sh
test -f ~/.qwa-secrets.sh && source ~/.qwa-secrets.sh || true
```

Use `.venv_cu13/bin/python` explicitly on this host.

## Existing Worker Example

Start the worker:

```bash
.venv_cu13/bin/python -m aqs persistent-executor serve \
  --socket /tmp/aqs-ovh.sock
```

Use the embedded client:

```bash
.venv_cu13/bin/python - <<'PY'
from aqs.embedded_session_client import PersistentSession

with PersistentSession(socket_path="/tmp/aqs-ovh.sock") as session:
    payload = session.execute_bundle(
        workload_manifest="workloads/manifests/imported/ovh_v2/01_real_dense_ring6_amplitude.yaml",
        plan_bundle="artifacts/plan_bundles/ovh_v2_seed/01_real_dense_ring6_amplitude.bundle.json",
        system_manifest="configs/systems/ovh_gra9_rtx5000_28.yml",
        execution_intent="require_real",
    )
    print(payload["selected_plan"]["plan_id"])
    print(session.status()["worker_session_id"])
PY
```

Stop the worker:

```bash
.venv_cu13/bin/python -m aqs persistent-executor shutdown \
  --socket /tmp/aqs-ovh.sock
```

## Autospawn Example

```bash
.venv_cu13/bin/python - <<'PY'
from aqs.embedded_session_client import PersistentSession

with PersistentSession(
    socket_path="/tmp/aqs-ovh-embedded.sock",
    spawn_temp_worker=True,
) as session:
    payload = session.execute_bundle(
        workload_manifest="workloads/manifests/imported/ovh_v2/06_star_graph_phase_amplitude_heldout_low.yaml",
        plan_bundle="artifacts/plan_bundles/ovh_v2_seed/06_star_graph_phase_amplitude_heldout_low.bundle.json",
        system_manifest="configs/systems/ovh_gra9_rtx5000_28.yml",
        execution_intent="require_real",
    )
    print(payload["selected_plan"]["plan_id"])
PY
```

## Strict Compatibility

Default behavior is conservative:

- a compatible persistent bundle request runs
- an incompatible request fails clearly
- there is no silent fallback

If fallback is explicitly enabled in Python, the returned payload still says:

- persistent execution was requested
- persistent execution was not used
- fallback was used
- why fallback happened

## Gate-S-Regime Benchmark

Run the canonical embedded-session benchmark package:

```bash
.venv_cu13/bin/python scripts/benchmark_embedded_session_client.py \
  --outdir artifacts/embedded_session/ovh_embedded_session_client_v1
```

The curated artifact package lands under:

- `artifacts/embedded_session/ovh_embedded_session_client_v1/summary.json`
- `artifacts/embedded_session/ovh_embedded_session_client_v1/summary.md`
- `artifacts/embedded_session/ovh_embedded_session_client_v1/per_request.csv`
- `artifacts/embedded_session/ovh_embedded_session_client_v1/sequence_summary.json`
- `artifacts/embedded_session/ovh_embedded_session_client_v1/sequence_summary.md`
- `artifacts/embedded_session/ovh_embedded_session_client_v1/request_trace.jsonl`
- `artifacts/embedded_session/ovh_embedded_session_client_v1/worker_health.jsonl`

## Interpretation Guardrail

Use the embedded session client to package the already-proven OVH fast path into reusable local Python code.

Do not describe it as:

- a ranking improvement
- a calibration improvement
- a Gate A, Gate B, Gate P, or Gate S semantics change
- a broader backend capability claim
