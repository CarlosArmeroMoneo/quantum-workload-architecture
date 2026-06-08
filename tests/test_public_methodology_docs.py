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
    template = _text("docs/experiments/experiment_card_template.md")
    experiment = _text("docs/experiments/launch_overhead_counterfactual.md")

    for term in [
        "cutensor_contraction",
        "cutensor_tiny_mnk",
        "memory_transfer",
        "framework_overhead",
        "launch_overhead",
        "profiler_replay_distortion",
        "launch_bound_signal",
        "memory_bound_signal",
        "low_utilization_tiny_workload",
        "contraction_kernel_family_present",
        "profiler_replay_warning",
        "sparse_profile_summary_warning",
    ]:
        assert term in taxonomy

    for section in [
        "## Title",
        "## Source Nomination",
        "## Evidence Tier",
        "## Observation",
        "## Hypothesis",
        "## Counterfactual Knobs",
        "## Expected Measurements",
        "## Success Criterion",
        "## Stop Criterion",
        "## Risks And Confounders",
        "## Required Artifacts",
        "## Acceptance Rule",
    ]:
        assert section in template
        assert section in experiment

    assert "real_dense_ring6_batched" in experiment
    assert "setup/load/convert/postprocess overhead at about `21.86%`" in experiment
    assert "`persistent_executor`: `off`, `on`" in experiment
    assert "`plan_bundle_reuse`: `off`, `on`" in experiment
    assert "`repeat_count_hint`: `1`, `8`, `32`, `128`" in experiment
    assert "`cache_workspace_gb`: `0`, `2`, `8`, `16`" in experiment
    assert "prewarm mode: `none`, `light`, `full` if supported" in experiment
    assert "Profiler-backed evidence remains real, not synthetic." in experiment
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


def test_readme_and_project_overview_link_methodology_package():
    readme = _text("README.md")
    overview = _text("PROJECT_OVERVIEW.md")

    required_links = [
        "docs/reports/how_to_review_this_project.md",
        "docs/reports/public_release_audit.md",
        "docs/architecture/evidence_contract.md",
        "docs/architecture/profiler_signal_taxonomy.md",
        "docs/reports/profiler_kernel_taxonomy_current_evidence.md",
        "docs/experiments/experiment_card_template.md",
        "docs/experiments/launch_overhead_counterfactual.md",
        "docs/reports/model_calibration_table.md",
        "docs/reports/v0_1_first_real_profiler_slice_release_notes.md",
        "docs/reports/next_pr_roadmap.md",
    ]
    for link in required_links:
        assert link in readme
        assert link in overview

    assert "docs/runbooks/gcp_a100_acceptance_gate.md" in readme
    assert "docs/architecture/tpu_sister_workload_lane.md" in readme
    assert "PROJECT_OVERVIEW.md" in readme


def test_public_release_audit_keeps_claims_and_language_safe():
    text = _text("docs/reports/public_release_audit.md")

    required = [
        "OVH RTX 5000 remains the canonical",
        "GCP A100 remains pending",
        "GCP Batch renderer is dry-run only",
        "TPU/JAX sister lane remains future-only",
        "not cuQuantum on TPU",
        "CUDA-Q remains adapter-backed",
        "python -m pytest -m \"not gpu and not profiler\" -q",
        "python -m mypy src/aqs",
        "bash scripts/public_check.sh",
    ]
    for phrase in required:
        assert phrase in text

    forbidden_terms = [
        "Career " + "Package",
        "resume" + "_bullets",
        "Interview " + "Walkthrough",
        "NVIDIA" + "-facing",
        "job" + "-application",
        "application " + "snippets",
        "role " + "alignment",
        "hir" + "ing",
        "ba" + "it",
        "revolution" + "ary",
        "game" + "-changing",
        "world" + "-class",
        "ground" + "breaking",
        "state" + "-of-the-art",
    ]
    for term in forbidden_terms:
        assert term not in text


def test_public_docs_do_not_expose_career_positioning():
    public_paths = [
        Path("README.md"),
        Path("PROJECT_OVERVIEW.md"),
        Path("docs/reports/how_to_review_this_project.md"),
        Path("docs/reports/public_release_audit.md"),
        Path("docs/reports/next_pr_roadmap.md"),
        Path("docs/reports/v0_1_first_real_profiler_slice_release_notes.md"),
    ]
    forbidden_terms = [
        "/".join(["docs", "career"]),
        "Career " + "Package",
        "resume" + "_bullets",
        "Interview " + "Walkthrough",
        "NVIDIA" + "-facing",
        "job" + "-application",
        "application " + "snippets",
        "role " + "alignment",
        "hir" + "ing",
        "ba" + "it",
        "portfolio " + "anchor",
        "nvidia" + "_project_pitch",
        "nvidia" + "_methodology",
        "nvidia" + "_role_alignment",
    ]

    assert not (Path("docs") / "career").exists()
    for path in public_paths:
        text = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            assert term not in text


def test_review_guide_is_time_boxed_and_claim_safe():
    text = _text("docs/reports/how_to_review_this_project.md")

    assert "If You Have 3 Minutes" in text
    assert "If You Have 10 Minutes" in text
    assert "If You Have 30 Minutes" in text
    assert "OVH RTX 5000 remains the canonical" in text
    assert "GCP A100 remains pending" in text
    assert "CUDA-Q is adapter-backed structural planning only" in text


def test_next_pr_roadmap_keeps_later_work_scoped():
    text = _text("docs/reports/next_pr_roadmap.md")

    assert "PR 1" in text
    assert "PR 8" in text
    assert "PR 9" in text
    assert "Public release audit" in text
    assert "No broad sweeps, dashboards, or runtime expansion" in text
    assert "Release tags should stay fixed except for explicit public-hygiene corrections" in text


def test_v0_1_release_notes_keep_pending_lanes_pending():
    text = _text("docs/reports/v0_1_first_real_profiler_slice_release_notes.md")

    assert "Evidence tier: Tier 3 architecture nomination" in text
    assert "Nomination: `launch_overhead` from `real_profiler_analysis`" in text
    assert "GCP A100 evidence remains pending" in text
    assert "CUDA-Q is adapter-backed" in text
    assert "TPU work is roadmap-only" in text
