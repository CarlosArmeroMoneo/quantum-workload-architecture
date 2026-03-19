.PHONY: init-db doctor validate-smoke test

init-db:
	python scripts/init_db.py --db benchmarks/warehouse/aqs.duckdb --schema benchmarks/warehouse/schema.sql

doctor:
	python -m aqs doctor --db benchmarks/warehouse/aqs.duckdb

validate-smoke:
	python -m aqs manifest validate workloads/manifests/templates/*.yaml configs/systems/*.yml benchmarks/manifests/templates/*.yaml

test:
	pytest -q
