from aqs.features import extract_feature_snapshot
from aqs.generators import generate_workload_manifest
from aqs.normalize import normalize_workload_manifest


def test_feature_snapshot_contains_statevector_estimates_and_graph_proxies():
    manifest = generate_workload_manifest("dense_universal", "smoke", 101)
    ir = normalize_workload_manifest(manifest)
    snapshot = extract_feature_snapshot(manifest, ir)
    assert snapshot["statevec_mem_est_fp32_bytes"] == (2 ** ir["n_qubits"]) * 8
    assert snapshot["statevec_mem_est_fp64_bytes"] == (2 ** ir["n_qubits"]) * 16
    assert "cutwidth_proxy" in snapshot["graph_features"]
    assert snapshot["feature_id"].startswith("feat_")
