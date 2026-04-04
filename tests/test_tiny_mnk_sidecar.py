from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def test_extract_reference_kernel_finds_tracked_tiny_mnk_shape(tmp_path):
    output_path = tmp_path / "observed.json"
    command = [
        sys.executable,
        "sidecars/tiny_mnk_lab/scripts/extract_reference_kernel.py",
        "--input",
        "evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.ncu.csv",
        "--profile-summary",
        "evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.profile_summary.json",
        "--output",
        str(output_path),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["api_version"] == "aqs.tiny_mnk_reference.v1"
    assert payload["reference_kernels"][0]["shape_key"] == "m32_n256_k75"
    assert payload["reference_kernels"][0]["occurrences"] >= 1
    assert payload["source_profile_summary"].endswith(".profile_summary.json")


def test_export_results_aggregates_benchmark_csv_against_reference(tmp_path):
    benchmark_csv = tmp_path / "benchmark.csv"
    with benchmark_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["label", "m", "n", "k", "iteration", "latency_ms", "gflops", "status"],
        )
        writer.writeheader()
        writer.writerow({"label": "tiny_mnk_reference", "m": 32, "n": 256, "k": 75, "iteration": 0, "latency_ms": 0.320, "gflops": 15.2, "status": "ok"})
        writer.writerow({"label": "tiny_mnk_reference", "m": 32, "n": 256, "k": 75, "iteration": 1, "latency_ms": 0.300, "gflops": 16.1, "status": "ok"})
        writer.writerow({"label": "control_shape", "m": 16, "n": 64, "k": 32, "iteration": 0, "latency_ms": 0.180, "gflops": 5.4, "status": "ok"})

    summary_path = tmp_path / "summary.json"
    command = [
        sys.executable,
        "sidecars/tiny_mnk_lab/scripts/export_results.py",
        "--reference-json",
        "sidecars/tiny_mnk_lab/config/observed_tiny_mnk_kernels.json",
        "--benchmark-csv",
        str(benchmark_csv),
        "--ncu-csv",
        "evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.ncu.csv",
        "--output",
        str(summary_path),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["api_version"] == "aqs.tiny_mnk_sidecar.v1"
    assert payload["shape_count"] == 2
    assert payload["matched_reference_shape_keys"] == ["m32_n256_k75"]
    assert payload["profile_shape_keys"] == ["m32_n256_k75"]
    aggregate = next(item for item in payload["aggregates"] if item["shape_key"] == "m32_n256_k75")
    assert aggregate["run_count"] == 2
    assert aggregate["latency_ms_median"] == 0.31


def test_export_results_records_sidecar_kernel_when_ncu_csv_uses_bench_name(tmp_path):
    benchmark_csv = tmp_path / "benchmark.csv"
    with benchmark_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["label", "m", "n", "k", "iteration", "latency_ms", "gflops", "status"],
        )
        writer.writeheader()
        writer.writerow({"label": "tiny_mnk_reference", "m": 32, "n": 256, "k": 75, "iteration": 0, "latency_ms": 1.0, "gflops": 1.0, "status": "ok"})

    ncu_csv = tmp_path / "tiny_mnk.ncu.csv"
    with ncu_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ID", "Kernel Name", "Block Size", "Grid Size"])
        writer.writeheader()
        writer.writerow(
            {
                "ID": "0",
                "Kernel Name": "<unnamed>::tiny_mnk_gemm_kernel(const double2 *, const double2 *, double2 *, int, int, int)",
                "Block Size": "(16, 16, 1)",
                "Grid Size": "(16, 2, 1)",
            }
        )

    summary_path = tmp_path / "summary.json"
    command = [
        sys.executable,
        "sidecars/tiny_mnk_lab/scripts/export_results.py",
        "--reference-json",
        "sidecars/tiny_mnk_lab/config/observed_tiny_mnk_kernels.json",
        "--benchmark-csv",
        str(benchmark_csv),
        "--ncu-csv",
        str(ncu_csv),
        "--output",
        str(summary_path),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["profile_shape_keys"] == ["m32_n256_k75"]
    assert payload["profile_kernels"][0]["kernel_family"] == "tiny_mnk_sidecar_kernel"
    assert payload["profile_kernels"][0]["occurrences"] == 1
