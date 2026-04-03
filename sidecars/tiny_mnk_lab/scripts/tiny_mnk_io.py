from __future__ import annotations

import csv
import re
from pathlib import Path
from statistics import median
from typing import Any


TINY_MNK_TOKEN = "tiny_mnk::contraction_tiny_mnk_kernel"


def normalize_path(path_like: str | Path) -> str:
    return str(Path(path_like)).replace("\\", "/")


def shape_key(m: int, n: int, k: int) -> str:
    return f"m{m}_n{n}_k{k}"


def parse_tiny_mnk_shape(kernel_name: str) -> tuple[int, int, int]:
    dims = [int(value) for value in re.findall(r"\(int\)(\d+)", kernel_name)]
    if len(dims) < 3:
        raise ValueError(f"could not parse tiny-MNK shape from kernel name: {kernel_name}")
    return dims[-3], dims[-2], dims[-1]


def extract_tiny_mnk_kernels_from_csv(csv_path: str | Path) -> list[dict[str, Any]]:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in reader:
            kernel_name = str(row.get("Kernel Name") or row.get("Name") or "").strip()
            if TINY_MNK_TOKEN not in kernel_name:
                continue
            m, n, k = parse_tiny_mnk_shape(kernel_name)
            block_size = str(row.get("Block Size") or "")
            grid_size = str(row.get("Grid Size") or "")
            key = (kernel_name, block_size, grid_size)
            entry = grouped.setdefault(
                key,
                {
                    "kernel_family": "cutensor_internal_tiny_mnk",
                    "kernel_name": kernel_name,
                    "shape_key": shape_key(m, n, k),
                    "m": m,
                    "n": n,
                    "k": k,
                    "block_size": block_size,
                    "grid_size": grid_size,
                    "occurrences": 0,
                    "kernel_ids": [],
                },
            )
            entry["occurrences"] += 1
            kernel_id = str(row.get("ID") or "").strip()
            if kernel_id and kernel_id not in entry["kernel_ids"] and len(entry["kernel_ids"]) < 16:
                entry["kernel_ids"].append(kernel_id)
    return sorted(grouped.values(), key=lambda item: (item["m"], item["n"], item["k"], item["kernel_name"]))


def load_benchmark_rows(csv_path: str | Path) -> list[dict[str, Any]]:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, Any]] = []
        for row in reader:
            rows.append(
                {
                    "label": str(row.get("label") or "").strip() or "tiny_mnk",
                    "m": int(row["m"]),
                    "n": int(row["n"]),
                    "k": int(row["k"]),
                    "iteration": int(row.get("iteration") or 0),
                    "latency_ms": float(row["latency_ms"]),
                    "gflops": float(row["gflops"]),
                    "status": str(row.get("status") or "ok"),
                }
            )
    return rows


def aggregate_benchmark_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(shape_key(int(row["m"]), int(row["n"]), int(row["k"])), []).append(row)

    aggregates: list[dict[str, Any]] = []
    for key in sorted(grouped):
        samples = grouped[key]
        latencies = [float(row["latency_ms"]) for row in samples]
        gflops = [float(row["gflops"]) for row in samples]
        aggregates.append(
            {
                "shape_key": key,
                "m": int(samples[0]["m"]),
                "n": int(samples[0]["n"]),
                "k": int(samples[0]["k"]),
                "run_count": len(samples),
                "latency_ms_min": round(min(latencies), 6),
                "latency_ms_median": round(median(latencies), 6),
                "latency_ms_max": round(max(latencies), 6),
                "gflops_max": round(max(gflops), 6),
                "labels": sorted({str(row["label"]) for row in samples}),
                "status_counts": _status_counts(samples),
            }
        )
    return aggregates


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "ok")
        counts[status] = counts.get(status, 0) + 1
    return counts


__all__ = [
    "TINY_MNK_TOKEN",
    "aggregate_benchmark_rows",
    "extract_tiny_mnk_kernels_from_csv",
    "load_benchmark_rows",
    "normalize_path",
    "parse_tiny_mnk_shape",
    "shape_key",
]
