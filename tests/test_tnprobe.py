from aqs.generators import generate_workload_manifest
from aqs.tnprobe import ProbeConfig, run_exact_tn_probe


def test_exact_tn_probe_returns_probe_payload_for_dense_universal():
    manifest = generate_workload_manifest("dense_universal", "smoke", 101)
    probe = run_exact_tn_probe(manifest, ProbeConfig(precision="complex128"))
    assert probe["status"] == "success"
    assert probe["probe_kind"] == "tn_contract_path"
    assert probe["mode"] == "exact_tn"
    assert probe["optimizer_cost"] is not None
    assert probe["largest_intermediate"] is not None
    assert probe["raw_info_json"]["backend"] in {"opt_einsum", "cuquantum"}


def test_exact_tn_probe_supports_qaoa_graph():
    manifest = generate_workload_manifest("qaoa_graph", "smoke", 13)
    probe = run_exact_tn_probe(manifest, ProbeConfig(precision="complex128"))
    assert probe["status"] == "success"
    assert probe["raw_info_json"]["family_id"] == "qaoa_graph"
