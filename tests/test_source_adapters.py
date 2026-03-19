from pathlib import Path

from aqs.manifest import load_yaml, validate_workload_manifest
from aqs.normalize import normalize_workload_manifest
from aqs.source_adapters import load_circuit_summary, parse_openqasm2_summary
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
