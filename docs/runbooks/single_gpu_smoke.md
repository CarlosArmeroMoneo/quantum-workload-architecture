# Single-GPU Smoke Runbook

## Purpose
Bring up the repo on a GPU-capable machine, create the DuckDB warehouse, and capture one system profile row.

Note:
- this is the generic single-GPU smoke runbook
- for the first profiler-backed exact-TN slice, use `docs/runbooks/profiler_linux_host.md` together with `configs/profiling/first_real_profiler_slice.yaml`

## Steps

```bash
python -m pip install -e .[db]
python scripts/init_db.py --db benchmarks/warehouse/aqs.duckdb --schema benchmarks/warehouse/schema.sql
python -m aqs doctor --db benchmarks/warehouse/aqs.duckdb
python -m aqs workload generate --family dense_universal --preset smoke --seed 101   --out workloads/manifests/generated/dense_universal_smoke.yaml
python -m aqs manifest validate --fix-workload-ids workloads/manifests/generated/dense_universal_smoke.yaml

# Real imported-circuit slice (requires GPU + CuPy + cuQuantum + Qiskit)
python -m aqs manifest validate workloads/manifests/imported/real_ghz3_amplitude.yaml
python -m aqs tnep execute \
  --manifest workloads/manifests/imported/real_ghz3_amplitude.yaml \
  --system-manifest configs/systems/ovh_gra9_rtx5000_28.yml \
  --execution-intent require_real \
  --measurement-repeats 2

# Representative profiler captures
python -m aqs profile nsys \
  --manifest workloads/manifests/imported/real_ghz3_amplitude.yaml \
  --system-manifest configs/systems/ovh_gra9_rtx5000_28.yml \
  --measurement-repeats 2 \
  --db benchmarks/warehouse/aqs.duckdb

python -m aqs profile ncu \
  --manifest workloads/manifests/imported/real_dense_ring6_batched.yaml \
  --system-manifest configs/systems/ovh_gra9_rtx5000_28.yml \
  --measurement-repeats 2 \
  --db benchmarks/warehouse/aqs.duckdb
```

## Success conditions
- `benchmarks/warehouse/aqs.duckdb` exists
- one row appears in `meta.system_profile`
- the generated workload manifest validates cleanly
- real runs fail loudly when the cuQuantum stack is unavailable
- profiled runs link raw reports and reduced profile summaries into the warehouse
