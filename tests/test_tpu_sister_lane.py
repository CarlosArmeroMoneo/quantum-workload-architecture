from pathlib import Path

from aqs.manifest import load_yaml


ARCH_DOC = Path("docs/architecture/tpu_sister_workload_lane.md")
RUNBOOK = Path("docs/runbooks/gcp_tpu_jax_workloads.md")
PLACEHOLDERS = [
    Path("workloads/tpu_sister_workloads/jax_batched_contract.yaml"),
    Path("workloads/tpu_sister_workloads/jax_compile_vs_execute.yaml"),
]


def test_tpu_sister_lane_docs_are_future_only_and_separate_from_cuquantum():
    text = ARCH_DOC.read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")

    required_phrases = [
        "future-only",
        "JAX/XLA sister-workload",
        "not cuQuantum on TPU",
        "conceptual/workload-structural",
        "No TPU runtime is implemented today",
        "No QPU provider adapter or QPU execution evidence is implemented",
    ]
    for phrase in required_phrases:
        assert phrase in text

    assert "This runbook defines how a future TPU lane would be operated" in runbook
    assert "The lane is not cuQuantum on TPU" in runbook
    assert "No TPU artifact is pinned or accepted today" in runbook
    assert "Do not run broad sweeps" in runbook


def test_tpu_sister_workload_placeholders_parse_and_stay_future_only():
    for path in PLACEHOLDERS:
        manifest = load_yaml(path)

        assert manifest["api_version"] == "qwa.tpu_sister_workload.v1"
        assert manifest["status"] == "future_only_placeholder"
        assert manifest["execution_backend"] == "jax_xla"
        assert manifest["target_platform"] == "tpu"
        assert manifest["not_cuquantum_on_tpu"] is True
        assert manifest["not_qpu_execution"] is True
        assert manifest["acceptance_boundary"]["future_only"] is True
        assert manifest["acceptance_boundary"]["requires_real_tpu_payload"] is True
        assert manifest["acceptance_boundary"]["requires_pinned_artifacts"] is True
        assert "compile_time_s" in manifest["suggested_metrics"]
        assert "first_execute_s" in manifest["suggested_metrics"]
        assert "steady_iter_ms" in manifest["suggested_metrics"]
        assert "shape_signature" in manifest["suggested_metrics"]


def test_tpu_system_template_is_roadmap_only():
    manifest = load_yaml("configs/systems/gcp_tpu_v6e.yml")

    assert manifest["status"] == "roadmap_template_no_evidence"
    assert manifest["gpu_count"] == 0
    assert manifest["gpu_model"] is None
    assert manifest["gpu_arch_target"] == "xla_tpu"
    assert manifest["xla_backend"] == "tpu"
    assert "not a cuQuantum execution target" in manifest["notes"]
