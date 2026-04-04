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


def test_implemented_mode_accepts_adapter_backed_cudaq_source():
    manifest = load_yaml("workloads/manifests/imported/cudaq_ghz3_amplitude.yaml")
    assert validate_manifest(manifest, mode="implemented") == []


def test_implemented_mode_rejects_broken_cudaq_adapter_path():
    manifest = load_yaml("workloads/manifests/imported/cudaq_ghz3_amplitude.yaml")
    manifest["source"] = {"loader": "cudaq_python_file", "path": "workloads/sources/cudaq/missing.py"}
    manifest.pop("ids", None)
    errors = validate_manifest(manifest, mode="implemented")
    assert len(errors) == 1
    assert "implemented mode could not load the adapter-backed cudaq source" in errors[0]
    assert "workloads/sources/cudaq/missing.py" in errors[0].replace("\\", "/")


def test_real_mode_rejects_semantics_outside_real_executor():
    manifest = load_yaml("workloads/manifests/imported/real_ghz3_amplitude.yaml")
    manifest["semantic_target"] = "state"
    manifest.pop("execution_target", None)
    manifest.pop("ids", None)
    errors = validate_manifest(manifest, mode="real")
    assert errors == ["real mode supports semantic_target in ['amplitude', 'batched_amplitudes'], got 'state'"]


def test_campaign_manifest_accepts_policy_hook_fields():
    manifest = load_yaml("configs/campaigns/repeat_roi_cpu_dry_run_v1.yaml")
    assert validate_manifest(manifest) == []


def test_campaign_manifest_accepts_graph_mode_matrix():
    manifest = load_yaml("configs/campaigns/cuda_graphs_ablation_v1.yaml")
    assert validate_manifest(manifest) == []


def test_ovh_input_manifests_validate_in_implemented_and_real_modes():
    for path in sorted(Path("workloads/manifests/imported/ovh_inputs").glob("*.yaml")):
        manifest = load_yaml(path)
        assert validate_manifest(manifest, mode="implemented") == [], f"{path} should validate in implemented mode"
        assert validate_manifest(manifest, mode="real") == [], f"{path} should validate in real mode"
