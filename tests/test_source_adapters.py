from pathlib import Path

import pytest

from aqs.manifest import load_yaml, validate_workload_manifest
from aqs.normalize import normalize_workload_manifest
from aqs.source_adapters import SourceLoadError, load_circuit_summary, parse_openqasm2_summary
from aqs.tnprobe import ProbeConfig, run_exact_tn_probe


def test_parse_openqasm2_summary_extracts_basic_structure():
    text = """
    OPENQASM 2.0;
    include \"qelib1.inc\";
    qreg q[3];
    h q[0];
    cx q[0],q[1];
    cx q[1],q[2];
    """
    summary = parse_openqasm2_summary(text)
    assert summary.n_qubits == 3
    assert summary.depth == 3
    assert len(summary.operations) == 3
    assert summary.measurement_count == 0


def test_imported_qiskit_qasm_manifest_validates_and_normalizes():
    manifest_path = Path("workloads/manifests/imported/qiskit_qasm2_ghz3.yaml")
    manifest = load_yaml(manifest_path)
    assert validate_workload_manifest(manifest) == []
    summary = load_circuit_summary(manifest)
    assert summary is not None
    assert summary.n_qubits == 3
    ir = normalize_workload_manifest(manifest)
    assert ir["n_qubits"] == 3
    assert ir["depth"] == 3
    assert ir["gate_hist_json"]["cx"] == 2
    assert ir["source_summary_json"]["loader"] == "openqasm2"


def test_structural_real_probe_uses_imported_circuit_source():
    manifest = load_yaml("workloads/manifests/imported/qiskit_qasm2_ghz3.yaml")
    probe = run_exact_tn_probe(manifest, ProbeConfig(probe_strategy="structural_real"))
    assert probe["status"] == "success"
    assert probe["raw_info_json"]["probe_source"] == "structural_real_circuit"


def test_unsupported_source_format_error_uses_non_scaffold_wording():
    manifest = {
        "source_format": "cirq",
        "source": {},
    }

    with pytest.raises(SourceLoadError, match=r"Unsupported source format: 'cirq'"):
        load_circuit_summary(manifest)


def test_imported_cudaq_manifest_validates_and_normalizes():
    manifest_path = Path("workloads/manifests/imported/cudaq_ghz3_amplitude.yaml")
    manifest = load_yaml(manifest_path)
    assert validate_workload_manifest(manifest) == []
    summary = load_circuit_summary(manifest)
    assert summary is not None
    assert summary.n_qubits == 3
    assert summary.loader == "cudaq_python_file"
    ir = normalize_workload_manifest(manifest)
    assert ir["n_qubits"] == 3
    assert ir["depth"] == 3
    assert ir["gate_hist_json"]["cx"] == 2
    assert ir["source_summary_json"]["source_kind"] == "cudaq_kernel_adapter"


def test_cudaq_adapter_ir_matches_qiskit_fixture_for_same_program():
    qiskit_manifest = load_yaml("workloads/manifests/imported/qiskit_qasm2_ghz3.yaml")
    cudaq_manifest = load_yaml("workloads/manifests/imported/cudaq_ghz3_amplitude.yaml")
    qiskit_ir = normalize_workload_manifest(qiskit_manifest)
    cudaq_ir = normalize_workload_manifest(cudaq_manifest)

    comparable_keys = [
        "n_qubits",
        "depth",
        "moments",
        "gate_hist_json",
        "two_qubit_density",
        "non_clifford_fraction",
        "clifford_valid",
        "measurement_count",
        "reset_count",
        "noise_json",
        "observable_json",
        "execution_target_json",
    ]
    assert {key: qiskit_ir[key] for key in comparable_keys} == {key: cudaq_ir[key] for key in comparable_keys}
    assert {key: value for key, value in qiskit_ir["interaction_graph_json"].items() if key != "kind"} == {
        key: value for key, value in cudaq_ir["interaction_graph_json"].items() if key != "kind"
    }


def test_structural_real_probe_matches_qiskit_fixture_for_cudaq_adapter():
    qiskit_manifest = load_yaml("workloads/manifests/imported/qiskit_qasm2_ghz3.yaml")
    cudaq_manifest = load_yaml("workloads/manifests/imported/cudaq_ghz3_amplitude.yaml")
    qiskit_probe = run_exact_tn_probe(qiskit_manifest, ProbeConfig(probe_strategy="structural_real"))
    cudaq_probe = run_exact_tn_probe(cudaq_manifest, ProbeConfig(probe_strategy="structural_real"))

    assert cudaq_probe["status"] == "success"
    assert cudaq_probe["raw_info_json"]["probe_source"] == "structural_real_circuit"
    assert cudaq_probe["largest_intermediate"] == qiskit_probe["largest_intermediate"]
    assert cudaq_probe["optimizer_cost"] == qiskit_probe["optimizer_cost"]


def test_cudaq_batched_adapter_ir_matches_qiskit_fixture():
    qiskit_manifest = load_yaml("workloads/manifests/imported/real_dense_ring6_batched.yaml")
    cudaq_manifest = load_yaml("workloads/manifests/imported/cudaq_dense_ring6_batched.yaml")
    qiskit_ir = normalize_workload_manifest(qiskit_manifest)
    cudaq_ir = normalize_workload_manifest(cudaq_manifest)

    comparable_keys = [
        "n_qubits",
        "depth",
        "moments",
        "gate_hist_json",
        "two_qubit_density",
        "non_clifford_fraction",
        "clifford_valid",
        "measurement_count",
        "reset_count",
        "noise_json",
        "observable_json",
        "execution_target_json",
    ]
    assert {key: qiskit_ir[key] for key in comparable_keys} == {key: cudaq_ir[key] for key in comparable_keys}
    assert {key: value for key, value in qiskit_ir["interaction_graph_json"].items() if key != "kind"} == {
        key: value for key, value in cudaq_ir["interaction_graph_json"].items() if key != "kind"
    }
