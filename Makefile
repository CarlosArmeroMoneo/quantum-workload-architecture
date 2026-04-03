.PHONY: init-db doctor validate-smoke lint typecheck test test-core test-db test-quantum test-live-gpu test-profiler

init-db:
	python scripts/init_db.py --db benchmarks/warehouse/aqs.duckdb --schema benchmarks/warehouse/schema.sql

doctor:
	python -m aqs doctor --db benchmarks/warehouse/aqs.duckdb

validate-smoke:
	python -m aqs manifest validate workloads/manifests/templates/*.yaml configs/systems/*.yml benchmarks/manifests/templates/*.yaml

test-core:
	pytest -q -m "not db and not quantum and not gpu and not profiler" tests

test-db:
	pytest -q -m "db and not gpu and not profiler" tests

test-quantum:
	pytest -q -m "quantum and not gpu and not profiler" tests

test-live-gpu:
	pytest -q -m "gpu and not profiler" tests

test-profiler:
	pytest -q -m "profiler" tests

lint:
	python -m ruff check src tests scripts

typecheck:
	python -m mypy src/aqs

test:
	pytest -q
