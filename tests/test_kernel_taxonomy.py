from aqs.kernel_taxonomy import classify_kernel_name, occupancy_band, summarize_kernel_families


def test_kernel_taxonomy_classifies_expected_families():
    cases = [
        (
            "void cutensor_internal_namespace::tiny_mnk::contraction_tiny_mnk_kernel<double2>(...)",
            "cutensor_contraction_tiny_mnk",
            "contraction",
        ),
        ("cutensor contraction kernel", "cutensor_contraction", "contraction"),
        ("cudaMemcpyAsync", "memory_copy", "memory_copy"),
        ("block_reduce_kernel", "reduction", "reduction"),
        ("cupy_arange_kernel", "array_arange_init", "arange_init"),
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
        "memory_copy": 1,
    }
    assert summary["kernel_category_counts"] == {
        "contraction": 2,
        "memory_copy": 1,
    }
    assert summary["top_kernel_families"][0]["kernel_family"] == "cutensor_contraction"
    assert summary["occupancy_band"] == "medium"


def test_occupancy_band_boundaries():
    assert occupancy_band(None) == "unknown"
    assert occupancy_band(10.0) == "low"
    assert occupancy_band(50.0) == "medium"
    assert occupancy_band(80.0) == "high"
