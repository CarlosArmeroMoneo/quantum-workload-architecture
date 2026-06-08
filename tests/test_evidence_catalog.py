import csv
import json
from pathlib import Path

from aqs.evidence_catalog import build_evidence_catalog, write_catalog_csv, write_catalog_markdown


def test_public_evidence_catalog_extracts_tracked_ovh_runs(tmp_path):
    rows = build_evidence_catalog("evidence/first_real_profiler_slice")

    by_run = {row["run_id"]: row for row in rows}
    assert set(by_run) == {"run_6e3b0bf4154a4a94", "run_219ba8a96d5d0d44"}

    batched = by_run["run_6e3b0bf4154a4a94"]
    assert batched["system_name"] == "ovh_gra9_rtx5000_28"
    assert batched["execution_source"] == "cuquantum_tensornet_gpu"
    assert batched["profiler_kind"] == "ncu"
    assert batched["ttfr_error_ratio"] == 2.166399
    assert batched["iter_error_ratio"] == 59.094829
    assert batched["bottleneck_family"] == "launch_overhead"
    assert batched["nomination_source"] == "real_profiler_analysis"
    assert json.loads(batched["kernel_family_counts_json"]) == {"cutensor_tiny_mnk": 4}
    assert batched["interpretation_class"] == "real_arch_nomination"
    assert batched["tiny_workload_warning"] is False

    ghz = by_run["run_219ba8a96d5d0d44"]
    assert ghz["profiler_kind"] == "nsys"
    assert ghz["tiny_workload_warning"] is True
    assert ghz["interpretation_class"] == "real_arch_nomination"

    csv_path = tmp_path / "catalog.csv"
    md_path = tmp_path / "catalog.md"
    write_catalog_csv(rows, csv_path)
    write_catalog_markdown(rows, md_path)

    with csv_path.open(encoding="utf-8", newline="") as handle:
        written_rows = list(csv.DictReader(handle))
    assert len(written_rows) == 2
    assert Path(md_path).read_text(encoding="utf-8").startswith("# Public Evidence Catalog")
