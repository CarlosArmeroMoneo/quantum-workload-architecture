from aqs.generators import generate_workload_manifest
from aqs.manifest import validate_manifest


def test_dense_universal_generation_is_deterministic():
    m1 = generate_workload_manifest("dense_universal", "smoke", 101)
    m2 = generate_workload_manifest("dense_universal", "smoke", 101)
    assert m1["ids"]["workload_id"] == m2["ids"]["workload_id"]
    assert m1["ids"]["source_hash"] == m2["ids"]["source_hash"]
    assert validate_manifest(m1) == []


def test_qec_clifford_smoke_generation_is_valid():
    manifest = generate_workload_manifest("qec_clifford", "smoke", 401)

    assert manifest["source_format"] == "normalized_ir"
    assert manifest["semantic_target"] == "detectors"
    assert manifest["parameters"]["distance"] == 3
    assert validate_manifest(manifest) == []
