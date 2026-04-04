import json
from pathlib import Path

from aqs.manifest import load_yaml, validate_system_manifest


def test_linux_profiler_node_template_is_valid():
    manifest = load_yaml("configs/systems/linux_profiler_node.template.yml")
    assert validate_system_manifest(manifest) == []


def test_frozen_local_profiler_host_manifest_is_valid():
    manifest = load_yaml("configs/systems/ubuntu2404_wsl2_rtx4050.yml")
    assert validate_system_manifest(manifest) == []
    assert manifest["appliance_image"]["ref"].startswith("aqs-cuquantum-appliance:25.11-local@sha256:")
    assert manifest["profiling_host"]["tool_paths"]["nsys"].endswith("/nsys")
    assert manifest["profiling_host"]["tool_paths"]["qdstrm_importer"].endswith("/QdstrmImporter")
    assert manifest["profiling_host"]["gpu_performance_counters"] == "blocked_on_host_policy"


def test_canonical_ovh_profiler_host_manifest_is_valid():
    manifest = load_yaml("configs/systems/ovh_gra9_rtx5000_28.yml")
    assert validate_system_manifest(manifest) == []
    assert manifest["os_release"] == "Ubuntu 25.04"
    assert manifest["kernel_version"] == "6.14.0-34-generic"
    assert manifest["driver_version"] == "580.95.05"
    assert manifest["profiling_host"]["canonical_tool_source"] == {
        "nsys": "host_installed_ubuntu_repo",
        "qdstrm_importer": "host_installed_ubuntu_repo",
        "ncu": "host_installed_ubuntu_repo",
    }
    assert manifest["profiling_host"]["tool_paths"]["nsys"] == "/usr/bin/nsys"
    assert manifest["profiling_host"]["tool_paths"]["qdstrm_importer"] == "/usr/lib/nsight-systems/host-linux-x64/QdstrmImporter"
    assert manifest["profiling_host"]["tool_paths"]["ncu"] == "/usr/bin/ncu"


def test_first_real_profiler_slice_freeze_references_existing_inputs():
    manifest = load_yaml("configs/profiling/first_real_profiler_slice.yaml")
    assert manifest["blessed_environment"]["canonical_tool_source"] == {
        "nsys": "host_installed_ubuntu_repo",
        "qdstrm_importer": "host_installed_ubuntu_repo",
        "ncu": "host_installed_ubuntu_repo",
    }
    assert manifest["system_manifest"] == "configs/systems/ovh_gra9_rtx5000_28.yml"
    assert Path(manifest["readiness_artifact"]).exists()
    assert Path(manifest["artifact_index"]).exists()
    assert Path(manifest["system_manifest"]).exists()
    assert Path(manifest["workloads"]["amplitude"]).exists()
    assert Path(manifest["workloads"]["batched_amplitudes"]).exists()
    protocol = manifest["execution_protocol"]
    assert protocol["precision"] == "complex128"
    assert protocol["measurement_repeats"] == 2
    assert protocol["expected_warm_repeats"] == 2
    assert protocol["probe_strategy"] == "cuquantum_if_available"
    assert "expected_selected_plan" not in protocol


def test_non_h100_profiler_slice_freeze_references_frozen_host_manifest():
    manifest = load_yaml("configs/profiling/first_real_profiler_slice_ubuntu2404_wsl2_rtx4050.yaml")
    assert manifest["blessed_environment"]["canonical_tool_source"] == {
        "nsys": "container_bundled",
        "qdstrm_importer": "container_bundled",
        "ncu": "container_bundled",
    }
    assert Path(manifest["system_manifest"]).exists()
    assert Path(manifest["workloads"]["amplitude"]).exists()
    assert Path(manifest["workloads"]["batched_amplitudes"]).exists()
    protocol = manifest["execution_protocol"]
    assert protocol["precision"] == "complex128"
    assert protocol["measurement_repeats"] == 2
    assert protocol["expected_warm_repeats"] == 2
    assert "expected_selected_plan" not in protocol


def test_ovh_readiness_json_is_present_and_host_specific():
    payload = json.loads(Path("configs/systems/ovh_gra9_rtx5000_28.profiling_ready.json").read_text(encoding="utf-8"))

    assert payload["profiling_readiness"]["profiling_ready"] is True
    assert payload["profiling_readiness"]["nsys"]["path"] == "/usr/bin/nsys"
    assert payload["profiling_readiness"]["nsys"]["qdstrm_importer_path"] == "/usr/lib/nsight-systems/host-linux-x64/QdstrmImporter"
    assert payload["profiling_readiness"]["ncu"]["path"] == "/usr/bin/ncu"
    assert payload["system_profile"]["gpu_model"] == "Quadro RTX 5000"
    assert payload["system_profile"]["driver_version"] == "580.95.05"


def test_ovh_exact_artifact_manifest_references_pinned_digests_and_synced_files():
    payload = json.loads(Path("configs/profiling/first_real_profiler_slice_ovh_gra9_rtx5000_28.artifacts.json").read_text(encoding="utf-8"))

    assert payload["artifact_manifest_version"] == "aqs.real_profiler_artifacts.v2"
    assert payload["release_assets"] == {
        "repository": "CarlosArmeroMoneo/quantum-workload-architecture",
        "tag": "v0.5.0-evidence",
        "archive_asset": "first-real-profiler-slice-evidence.zip",
        "checksum_asset": "SHA256SUMS.txt",
        "release_url": "https://github.com/CarlosArmeroMoneo/quantum-workload-architecture/releases/tag/v0.5.0-evidence",
        "archive_root": "first-real-profiler-slice-evidence",
    }
    assert payload["amplitude_nsys"]["digest"] == "f6bc40e76bb947a6"
    assert payload["batched_ncu"]["digest"] == "0e70e7aabe3342c1"

    assert "f6bc40e76bb947a6" in payload["amplitude_nsys"]["execution_json"]["repo_path"]
    assert "0e70e7aabe3342c1" in payload["batched_ncu"]["execution_json"]["repo_path"]

    tracked_paths = [
        payload["unprofiled_execute"]["repo_path"],
        payload["amplitude_nsys"]["execution_json"]["repo_path"],
        payload["amplitude_nsys"]["profile_summary_json"]["repo_path"],
        payload["amplitude_nsys"]["arch_output"]["repo_path"],
        payload["batched_ncu"]["execution_json"]["repo_path"],
        payload["batched_ncu"]["profile_summary_json"]["repo_path"],
        payload["batched_ncu"]["csv"]["repo_path"],
        payload["batched_ncu"]["arch_output"]["repo_path"],
    ]
    for path in tracked_paths:
        assert Path(path).exists()

    release_paths = [
        payload["amplitude_nsys"]["report"]["release_archive_path"],
        payload["amplitude_nsys"]["qdstrm"]["release_archive_path"],
        payload["amplitude_nsys"]["sqlite"]["release_archive_path"],
        payload["amplitude_nsys"]["attempt_json"]["release_archive_path"],
        payload["amplitude_nsys"]["stats"]["cudaapisum"]["release_archive_path"],
        payload["amplitude_nsys"]["stats"]["gpukernsum"]["release_archive_path"],
        payload["amplitude_nsys"]["stats"]["nvtxsum"]["release_archive_path"],
        payload["batched_ncu"]["report"]["release_archive_path"],
        payload["batched_ncu"]["attempt_json"]["release_archive_path"],
    ]
    for path in release_paths:
        assert path.startswith("first-real-profiler-slice-evidence/")


def test_curated_real_execution_evidence_is_host_specific_and_not_template_derived():
    curated_paths = [
        "evidence/first_real_profiler_slice/real_ghz3_amplitude.execute.cu13.json",
        "evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.execution.json",
        "evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.execution.json",
    ]
    forbidden_tokens = [
        "fill_me",
        "optional_if",
        "linux_profiler_node_template",
    ]

    for path in curated_paths:
        text = Path(path).read_text(encoding="utf-8")
        payload = json.loads(text)

        for token in forbidden_tokens:
            assert token not in text

        assert payload["system_name"] == "ovh_gra9_rtx5000_28"
        assert payload["selected_plan"]["gpu_arch_target"] == "sm75"

        system_manifest = payload["system_manifest"]
        assert system_manifest["system_name"] == "ovh_gra9_rtx5000_28"
        assert system_manifest["gpu_model"] == "Quadro RTX 5000"
        assert system_manifest["gpu_arch_target"] == "sm75"
        assert system_manifest["node_label"] == "ovh-gra9-rtx5000-28"
        assert system_manifest["driver_version"] == "580.126.09"
        assert system_manifest["profiling_host"]["canonical_tool_source"] == {
            "nsys": "host_installed_ubuntu_repo",
            "qdstrm_importer": "host_installed_ubuntu_repo",
            "ncu": "host_installed_ubuntu_repo",
        }
        assert system_manifest["profiling_host"]["readiness_artifact"] == "configs/systems/ovh_gra9_rtx5000_28.profiling_ready.json"
        assert system_manifest["profiling_host"]["execution_runbook"] == "docs/runbooks/ovh_cu13_real_execution.md"
