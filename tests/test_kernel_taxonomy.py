from pathlib import Path

from aqs.kernel_taxonomy import classify_kernel_name, derive_profiler_signals, occupancy_band, summarize_kernel_families
from scripts.summarize_kernel_taxonomy import summarize_profile, write_markdown


def test_kernel_taxonomy_classifies_expected_families():
    cases = [
        (
            "void cutensor_internal_namespace::tiny_mnk::contraction_tiny_mnk_kernel<double2>(...)",
            "cutensor_tiny_mnk",
            "cutensor_tiny_mnk",
        ),
        ("cutensor contraction kernel", "cutensor_contraction", "cutensor_contraction"),
        ("contract_kernel", "generic_contraction", "unknown"),
        ("cudaMemcpyAsync", "memory_transfer", "memory_transfer"),
        ("block_reduce_kernel", "reduction", "reduction"),
        ("cupy_arange_kernel", "initialization", "initialization"),
        ("cupy_elementwise_add", "framework_overhead", "framework_overhead"),
        ("some_unrecognized_kernel", "unknown", "unknown"),
    ]

    for name, family, category in cases:
        classification = classify_kernel_name(name)
        assert classification["kernel_family"] == family
        assert classification["kernel_category"] == category


def test_kernel_family_summary_counts_and_occupancy_band():
    summary = summarize_kernel_families(
        [
            {"name": "cutensor contraction kernel", "time_s": 0.2},
            {"name": "cutensor contraction kernel", "time_s": 0.3},
            {"name": "cudaMemcpyAsync", "time_s": 0.1},
        ],
        occupancy_pct=48.0,
    )

    assert summary["kernel_family_counts"] == {
        "cutensor_contraction": 2,
        "memory_transfer": 1,
    }
    assert summary["kernel_category_counts"] == {
        "cutensor_contraction": 2,
        "memory_transfer": 1,
    }
    assert summary["top_kernel_families"][0]["kernel_family"] == "cutensor_contraction"
    assert summary["occupancy_band"] == "medium"
    assert summary["signals"]["contraction_kernel_family_present"] is True


def test_occupancy_band_boundaries():
    assert occupancy_band(None) == "unknown"
    assert occupancy_band(10.0) == "low"
    assert occupancy_band(50.0) == "medium"
    assert occupancy_band(80.0) == "high"


def test_profiler_signals_cover_sparse_and_memory_bound_cases():
    sparse = derive_profiler_signals({})
    assert sparse["launch_bound_signal"] is True
    assert sparse["sparse_profile_summary_warning"] is True

    memory = derive_profiler_signals({"memory_transfer": 3, "cutensor_contraction": 1})
    assert memory["memory_bound_signal"] is True
    assert memory["contraction_kernel_family_present"] is True


def test_report_generator_handles_missing_fields(tmp_path: Path):
    profile = tmp_path / "minimal.profile_summary.json"
    profile.write_text('{"run_id": "run_minimal", "profiler_kind": "nsys"}', encoding="utf-8")

    row = summarize_profile(profile)
    assert row["kernel_count"] == 0
    assert row["signals"]["sparse_profile_summary_warning"] is True

    out = tmp_path / "report.md"
    write_markdown([row], out)
    text = out.read_text(encoding="utf-8")
    assert "Profiler Kernel Taxonomy: Current Evidence" in text
    assert "sparse-profile warning" in text
