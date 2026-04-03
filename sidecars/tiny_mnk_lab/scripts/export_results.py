from __future__ import annotations

import argparse
import json
from pathlib import Path

from tiny_mnk_io import (
    aggregate_benchmark_rows,
    extract_tiny_mnk_kernels_from_csv,
    load_benchmark_rows,
    normalize_path,
)


def build_sidecar_summary(
    *,
    reference_json_path: str | Path,
    benchmark_csv_path: str | Path,
    ncu_csv_path: str | Path | None = None,
) -> dict:
    reference = json.loads(Path(reference_json_path).read_text(encoding="utf-8"))
    benchmark_rows = load_benchmark_rows(benchmark_csv_path)
    aggregates = aggregate_benchmark_rows(benchmark_rows)
    reference_shape_keys = sorted({entry["shape_key"] for entry in reference.get("reference_kernels") or []})
    profile_kernels = extract_tiny_mnk_kernels_from_csv(ncu_csv_path) if ncu_csv_path else []
    profile_shape_keys = sorted({entry["shape_key"] for entry in profile_kernels})
    aggregate_shape_keys = [entry["shape_key"] for entry in aggregates]

    return {
        "api_version": "aqs.tiny_mnk_sidecar.v1",
        "reference_json_path": normalize_path(reference_json_path),
        "benchmark_csv_path": normalize_path(benchmark_csv_path),
        "ncu_csv_path": normalize_path(ncu_csv_path) if ncu_csv_path else None,
        "benchmark_run_count": len(benchmark_rows),
        "shape_count": len(aggregates),
        "reference_shape_keys": reference_shape_keys,
        "benchmark_shape_keys": aggregate_shape_keys,
        "profile_shape_keys": profile_shape_keys,
        "matched_reference_shape_keys": sorted(set(reference_shape_keys) & set(aggregate_shape_keys)),
        "reference_kernels": reference.get("reference_kernels") or [],
        "profile_kernels": profile_kernels,
        "aggregates": aggregates,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a tiny-MNK sidecar summary JSON from benchmark and profiler CSVs")
    parser.add_argument("--reference-json", required=True, help="Tracked reference kernel JSON")
    parser.add_argument("--benchmark-csv", required=True, help="Benchmark CSV emitted by tiny_mnk_bench")
    parser.add_argument("--output", required=True, help="Path to write the sidecar summary JSON")
    parser.add_argument("--ncu-csv", help="Optional Nsight Compute CSV for the sidecar run")
    args = parser.parse_args(argv)

    payload = build_sidecar_summary(
        reference_json_path=args.reference_json,
        benchmark_csv_path=args.benchmark_csv,
        ncu_csv_path=args.ncu_csv,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
