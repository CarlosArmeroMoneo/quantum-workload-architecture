from aqs.manifest import finalize_workload_manifest, validate_manifest


def test_manifest_fixup_matches_canonical_hash():
    manifest = {
        "api_version": "aqs.workload.v1",
        "family_id": "dense_universal",
        "family_version": "0.1.0",
        "generator_name": "dense_universal",
        "generator_version": "0.1.0",
        "source_format": "normalized_ir",
        "semantic_target": "amplitude",
        "reference_tier": "smoke",
        "split_tag": "demo",
        "repeat_count_hint": 1,
        "seed": 1,
        "parameters": {
            "n_qubits": 12,
            "depth": 4,
            "topology": "ring",
            "two_qubit_density": "medium",
            "measurement_pattern": "terminal_all",
        },
    }
    fixed = finalize_workload_manifest(manifest)
    assert validate_manifest(fixed) == []
