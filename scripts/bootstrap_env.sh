#!/usr/bin/env bash
set -euo pipefail

python -m pip install -e .[db]
python scripts/init_db.py --db benchmarks/warehouse/aqs.duckdb --schema benchmarks/warehouse/schema.sql
python -m aqs doctor || true
