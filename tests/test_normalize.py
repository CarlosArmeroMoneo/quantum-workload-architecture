from aqs.generators import generate_workload_manifest
from aqs.normalize import normalize_workload_manifest


def test_normalize_is_deterministic_for_dense_universal():
    manifest = generate_workload_manifest("dense_universal", "smoke", 101)
    ir1 = normalize_workload_manifest(manifest)
    ir2 = normalize_workload_manifest(manifest)
    assert ir1["ir_hash"] == ir2["ir_hash"]
    assert ir1["n_qubits"] == 12
    assert ir1["depth"] == 4
    assert ir1["interaction_graph_json"]["edge_count"] > 0


def test_qaoa_normalization_emits_observable_metadata():
    manifest = generate_workload_manifest("qaoa_graph", "smoke", 7)
    ir = normalize_workload_manifest(manifest)
    assert ir["observable_json"]["observable_count"] == 1
    assert ir["clifford_valid"] is False
