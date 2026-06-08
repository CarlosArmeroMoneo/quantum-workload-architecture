from pathlib import Path

from aqs.manifest import load_yaml


def test_workload_scale_ladder_references_existing_manifests_and_claim_boundaries():
    manifest = load_yaml("configs/experiments/workload_scale_ladder_v0_2.yaml")

    assert manifest["api_version"] == "qwa.workload_scale_ladder.v0_2"
    assert manifest["broad_sweeps_allowed"] is False
    assert manifest["claim_policy"]["local_nvidia_laptop_6gb"] == "preflight_only"

    levels = manifest["levels"]
    assert [level["level"] for level in levels] == [0, 1, 2, 3]
    for level in levels:
        path = level["workload_manifest"]
        assert "*" not in path
        assert "?" not in path
        assert Path(path).exists()
        assert level["expected_role"]
        assert level["evidence_restrictions"]

    assert levels[0]["local_6gb_allowed"] is True
    assert levels[2]["cloud_gpu_preferred"] is True


def test_workload_ladder_docs_keep_tiny_and_local_caveats_visible():
    text = Path("docs/architecture/workload_scale_ladder.md").read_text(encoding="utf-8")

    assert "GHZ3 is not a throughput benchmark" in text
    assert "Local 6GB is a constrained preflight host only" in text
    assert "GCP A100 remains pending" in text
