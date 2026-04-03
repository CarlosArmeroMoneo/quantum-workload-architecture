from pathlib import Path

import pytest

from aqs.manifest import load_yaml
from aqs.source_adapters import maybe_load_qiskit_circuit


pytestmark = pytest.mark.quantum


def test_qiskit_loader_materializes_imported_qasm_manifest():
    pytest.importorskip("qiskit")
    manifest = load_yaml(Path("workloads/manifests/imported/qiskit_qasm2_ghz3.yaml"))
    circuit = maybe_load_qiskit_circuit(manifest)
    assert circuit is not None
    assert len(circuit.qubits) == 3
