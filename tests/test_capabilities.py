from pathlib import Path

from aqs.capabilities import CAPABILITY_MATRIX, IMPLEMENTED_SUPPORT, capability_matrix_rows
from aqs.manifest import load_yaml, validate_manifest


def test_capability_matrix_rows_expose_readme_truth_fields():
    rows = capability_matrix_rows()
    assert len(rows) == len(CAPABILITY_MATRIX)
    assert {row["area"] for row in rows} >= {
        "Manifest ontology",
        "Real cuTensorNet execution",
        "Profiler reduction",
    }


def test_implemented_support_matches_stage_zero_truth_subset():
    assert IMPLEMENTED_SUPPORT["normalization"]["source_formats"] == {"qiskit", "cudaq", "normalized_ir"}
    assert IMPLEMENTED_SUPPORT["real_execution"]["source_formats"] == {"qiskit"}
    assert IMPLEMENTED_SUPPORT["real_execution"]["semantic_targets"] == {"amplitude", "batched_amplitudes"}


def test_implemented_mode_accepts_cpu_smoke_manifest():
    manifest = load_yaml(Path("workloads/manifests/generated/dense_universal_smoke.yaml"))
    assert validate_manifest(manifest, mode="implemented") == []


def test_implemented_mode_accepts_adapter_backed_cudaq_manifest():
    manifest = load_yaml(Path("workloads/manifests/imported/cudaq_ghz3_amplitude.yaml"))
    assert validate_manifest(manifest, mode="implemented") == []


def test_real_mode_accepts_canonical_real_manifest():
    manifest = load_yaml(Path("workloads/manifests/imported/real_ghz3_amplitude.yaml"))
    assert validate_manifest(manifest, mode="real") == []
