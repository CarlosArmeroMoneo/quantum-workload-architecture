from pathlib import Path

from aqs.manifest import load_yaml


def _text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_evidence_contract_defines_tiers_and_claim_boundaries():
    text = _text("docs/architecture/evidence_contract.md")

    for tier in ["Tier 0", "Tier 1", "Tier 2", "Tier 3"]:
        assert tier in text

    assert "OVH `real_dense_ring6_batched`: Tier 3" in text
    assert "GCP A100 GHZ3 lane: pending" in text
    assert "WSL2 RTX4050 host: negative-control" in text
    assert "Rejected local GCP draft: no A100 tier" in text
    assert "CUDA-Q runtime evidence" in text
    assert "TPU evidence" in text


def test_profiler_signal_taxonomy_and_counterfactual_are_public_safe():
    taxonomy = _text("docs/architecture/profiler_signal_taxonomy.md")
    experiment = _text("docs/experiments/launch_overhead_counterfactual.md")

    for term in [
        "cutensor_contraction",
        "cutensor_contraction_tiny_mnk",
        "memory_transfer",
        "framework_overhead",
        "launch_overhead",
        "profiler_replay_distortion",
    ]:
        assert term in taxonomy

    assert "real_dense_ring6_batched" in experiment
    assert "setup/load/convert/postprocess overhead at about `21.86%`" in experiment
    assert "less than `10%`" in experiment
    assert "do not claim the bottleneck is resolved" in experiment


def test_gcp_a100_next_cases_are_narrow_and_acceptance_gated():
    manifest = load_yaml("configs/profiling/gcp_a100_next_validated_cases.yaml")

    assert manifest["status"] == "pending_quota"
    assert manifest["broad_sweep_allowed"] is False
    assert manifest["system_manifest"] == "configs/systems/gcp_a100_sxm4_40gb.yml"
    assert Path(manifest["acceptance_gate"]).exists()

    cases = manifest["cases"]
    assert len(cases) == 2
    assert [case["case_id"] for case in cases] == [
        "canonical_batched_exact_tn",
        "medium_ladder_brickwork_amplitude",
    ]
    for case in cases:
        assert Path(case["manifest"]).exists()
        assert case["intended_tier"].startswith("Tier 2")

    gate = _text("docs/runbooks/gcp_a100_acceptance_gate.md")
    assert "Device identity verified as `NVIDIA A100-SXM4-40GB`" in gate
    assert "execution_source=cuquantum_tensornet_gpu" in gate
    assert "Rejected" not in gate
    assert "GHZ3 result should be Tier 2 portability/calibration evidence only" in gate


def test_readme_and_portfolio_link_methodology_package():
    readme = _text("README.md")
    portfolio = _text("PORTFOLIO.md")

    required_links = [
        "docs/architecture/evidence_contract.md",
        "docs/architecture/profiler_signal_taxonomy.md",
        "docs/experiments/launch_overhead_counterfactual.md",
        "docs/reports/v0_1_first_real_profiler_slice_release_notes.md",
        "docs/architecture/profiler_signal_taxonomy.md",
    ]
    for link in required_links:
        assert link in readme
        assert link in portfolio

    assert "docs/runbooks/gcp_a100_acceptance_gate.md" in readme
    assert "docs/architecture/evidence_contract.md" in portfolio


def test_v0_1_release_notes_keep_pending_lanes_pending():
    text = _text("docs/reports/v0_1_first_real_profiler_slice_release_notes.md")

    assert "Evidence tier: Tier 3 architecture nomination" in text
    assert "Nomination: `launch_overhead` from `real_profiler_analysis`" in text
    assert "GCP A100 evidence remains pending" in text
    assert "CUDA-Q is adapter-backed" in text
    assert "TPU work is roadmap-only" in text
