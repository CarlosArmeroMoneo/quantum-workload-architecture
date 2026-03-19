from pathlib import Path

from aqs.benchmark import run_benchmark_manifest


def test_benchmark_runner_emits_summary_for_structural_qasm_slice(tmp_path):
    summary = run_benchmark_manifest(
        "benchmarks/manifests/templates/tnep_qasm2_structural.yaml",
        outdir=tmp_path / "bench_run",
    )
    assert summary["workload_count"] >= 1
    assert summary["probe_strategy"] == "structural_real"
    assert Path(summary["outdir"]).joinpath("summary.json").exists()
    first = summary["results"][0]
    assert first["probe_status"] in {"success", "unsupported", "probe_fail"}
