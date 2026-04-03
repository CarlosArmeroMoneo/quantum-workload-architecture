from pathlib import Path

from aqs.manifest import finalize_workload_manifest, load_yaml, validate_manifest


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


def test_workload_templates_validate():
    for path in sorted(Path("workloads/manifests/templates").glob("*.yaml")):
        manifest = load_yaml(path)
        assert validate_manifest(manifest) == [], f"{path} should validate"


def test_validate_manifest_rejects_unknown_mode():
    errors = validate_manifest({"api_version": "aqs.workload.v1"}, mode="nonsense")
    assert errors == ["unsupported validation mode: 'nonsense'"]


def test_implemented_mode_rejects_schema_only_source_formats():
    manifest = load_yaml("workloads/manifests/imported/real_ghz3_amplitude.yaml")
    manifest["source_format"] = "cudaq"
    manifest["source"] = {"loader": "cudaq_python_file", "path": "workloads/sources/cudaq/ghz3.py"}
    manifest.pop("ids", None)
    errors = validate_manifest(manifest, mode="implemented")
    assert "implemented mode supports source_format" in errors[0]


def test_real_mode_rejects_semantics_outside_real_executor():
    manifest = load_yaml("workloads/manifests/imported/real_ghz3_amplitude.yaml")
    manifest["semantic_target"] = "state"
    manifest.pop("execution_target", None)
    manifest.pop("ids", None)
    errors = validate_manifest(manifest, mode="real")
    assert errors == ["real mode supports semantic_target in ['amplitude', 'batched_amplitudes'], got 'state'"]
