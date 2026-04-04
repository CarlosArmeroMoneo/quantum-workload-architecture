from aqs.validation_confidence import annotate_validation_results, build_confidence_summary_markdown, build_replicate_lookup


def _evaluation(plan_id: str, template_name: str, ttfr_s: float, *, stdev: float | None = None) -> dict[str, object]:
    details = {}
    if stdev is not None:
        details = {
            "calibration_ttfr": {
                "ttfr_stats": {
                    "stdev": stdev,
                }
            }
        }
    return {
        "plan_id": plan_id,
        "status": "success",
        "observed_ttfr_s": ttfr_s,
        "candidate": {
            "plan_id": plan_id,
            "template_name": template_name,
        },
        "execution_run": {
            "failure_detail_json": details,
        },
    }


def _interleaved_pair_payload(
    workload_id: str,
    left_template: str,
    right_template: str,
    *,
    replicate_winner_template: str,
    ci_lower_s: float,
    ci_upper_s: float,
    conclusion: str = "winner_stable",
    uncertainty_band_s: float = 0.001,
) -> dict[str, object]:
    return {
        "workload_id": workload_id,
        "pair_mode": "interleaved",
        "left_template": left_template,
        "right_template": right_template,
        "replicate_winner_template": replicate_winner_template,
        "uncertainty_band_s": uncertainty_band_s,
        "conclusion": conclusion,
        "delta_confidence_interval": {
            "lower_s": ci_lower_s,
            "upper_s": ci_upper_s,
            "half_width_s": uncertainty_band_s,
            "level": 0.95,
            "method": "normal_mean_ci",
        },
    }


def test_confidence_marks_near_tie_miss_as_low():
    results = [
        {
            "workload_id": "wkl_low",
            "selected_plan_id": "plan_quick",
            "oracle_best_plan_id": "plan_balanced",
            "evaluations": [
                _evaluation("plan_quick", "quick_turnaround", 0.0108),
                _evaluation("plan_balanced", "balanced", 0.0100),
            ],
        }
    ]
    annotated = annotate_validation_results(results, objective="ttfr")
    row = annotated["results"][0]
    assert row["selection_confidence"] == "low"
    assert row["top1_within_1ms"] is True
    assert row["top1_within_3pct"] is False
    assert annotated["selection_confidence_counts"] == {"low": 1, "medium": 0, "high": 0}


def test_confidence_marks_clear_gap_without_replicates_as_medium():
    results = [
        {
            "workload_id": "wkl_medium",
            "selected_plan_id": "plan_balanced",
            "oracle_best_plan_id": "plan_balanced",
            "evaluations": [
                _evaluation("plan_quick", "quick_turnaround", 0.0150),
                _evaluation("plan_balanced", "balanced", 0.0100),
            ],
        }
    ]
    annotated = annotate_validation_results(results, objective="ttfr")
    row = annotated["results"][0]
    assert row["selection_confidence"] == "medium"
    assert row["winner_template"] == "balanced"
    assert row["runner_up_template"] == "quick_turnaround"
    assert annotated["high_confidence_top1_accuracy"] is None


def test_confidence_uses_external_pair_uncertainty_for_high_confidence():
    results = [
        {
            "workload_id": "wkl_high",
            "selected_plan_id": "plan_balanced",
            "oracle_best_plan_id": "plan_balanced",
            "evaluations": [
                _evaluation("plan_quick", "quick_turnaround", 0.0150),
                _evaluation("plan_balanced", "balanced", 0.0100),
            ],
        }
    ]
    replicate_lookup = build_replicate_lookup(
        [
            {
                "workload_id": "wkl_high",
                "left_template": "quick_turnaround",
                "right_template": "balanced",
                "uncertainty_band_s": 0.001,
                "conclusion": "winner_stable",
            }
        ]
    )
    annotated = annotate_validation_results(results, objective="ttfr", replicate_lookup=replicate_lookup)
    row = annotated["results"][0]
    assert row["selection_confidence"] == "high"
    assert row["replicate_uncertainty_band_s"] == 0.001
    assert row["replicate_uncertainty_source"] == "external_pair_summary"
    assert annotated["high_confidence_top1_accuracy"] == 1.0


def test_confidence_downgrades_when_replicates_flip_the_stored_winner():
    results = [
        {
            "workload_id": "wkl_flip",
            "selected_plan_id": "plan_quick",
            "oracle_best_plan_id": "plan_balanced",
            "evaluations": [
                _evaluation("plan_quick", "quick_turnaround", 0.0200),
                _evaluation("plan_balanced", "balanced", 0.0100),
            ],
        }
    ]
    replicate_lookup = build_replicate_lookup(
        [
            {
                "workload_id": "wkl_flip",
                "left_template": "quick_turnaround",
                "right_template": "balanced",
                "uncertainty_band_s": 0.003,
                "conclusion": "winner_flipped_vs_single_shot",
            }
        ]
    )
    annotated = annotate_validation_results(results, objective="ttfr", replicate_lookup=replicate_lookup)
    row = annotated["results"][0]
    assert row["selection_confidence"] == "medium"
    assert row["replicate_conclusion"] == "winner_flipped_vs_single_shot"


def test_high_confidence_top1_accuracy_counts_only_high_rows_when_correct():
    replicate_lookup = build_replicate_lookup(
        [
            {
                "workload_id": "wkl_high_correct",
                "left_template": "quick_turnaround",
                "right_template": "balanced",
                "uncertainty_band_s": 0.001,
                "conclusion": "winner_stable",
            }
        ]
    )
    results = [
        {
            "workload_id": "wkl_high_correct",
            "selected_plan_id": "plan_balanced",
            "oracle_best_plan_id": "plan_balanced",
            "evaluations": [
                _evaluation("plan_quick", "quick_turnaround", 0.0150),
                _evaluation("plan_balanced", "balanced", 0.0100),
            ],
        },
        {
            "workload_id": "wkl_medium_correct",
            "selected_plan_id": "plan_balanced_m",
            "oracle_best_plan_id": "plan_balanced_m",
            "evaluations": [
                _evaluation("plan_quick_m", "quick_turnaround", 0.0150),
                _evaluation("plan_balanced_m", "balanced", 0.0100),
            ],
        },
    ]
    annotated = annotate_validation_results(results, objective="ttfr", replicate_lookup=replicate_lookup)
    assert annotated["selection_confidence_counts"] == {"low": 0, "medium": 1, "high": 1}
    assert annotated["high_confidence_top1_accuracy"] == 1.0


def test_high_confidence_top1_accuracy_counts_only_high_rows_when_wrong():
    replicate_lookup = build_replicate_lookup(
        [
            {
                "workload_id": "wkl_high_wrong",
                "left_template": "quick_turnaround",
                "right_template": "balanced",
                "uncertainty_band_s": 0.001,
                "conclusion": "winner_stable",
            }
        ]
    )
    results = [
        {
            "workload_id": "wkl_high_wrong",
            "selected_plan_id": "plan_quick",
            "oracle_best_plan_id": "plan_balanced",
            "evaluations": [
                _evaluation("plan_quick", "quick_turnaround", 0.0150),
                _evaluation("plan_balanced", "balanced", 0.0100),
            ],
        },
        {
            "workload_id": "wkl_medium_correct",
            "selected_plan_id": "plan_balanced_m",
            "oracle_best_plan_id": "plan_balanced_m",
            "evaluations": [
                _evaluation("plan_quick_m", "quick_turnaround", 0.0150),
                _evaluation("plan_balanced_m", "balanced", 0.0100),
            ],
        },
    ]
    annotated = annotate_validation_results(results, objective="ttfr", replicate_lookup=replicate_lookup)
    assert annotated["selection_confidence_counts"] == {"low": 0, "medium": 1, "high": 1}
    assert annotated["high_confidence_top1_accuracy"] == 0.0


def test_high_confidence_top1_accuracy_is_none_when_no_high_rows_exist():
    results = [
        {
            "workload_id": "wkl_medium",
            "selected_plan_id": "plan_balanced",
            "oracle_best_plan_id": "plan_balanced",
            "evaluations": [
                _evaluation("plan_quick", "quick_turnaround", 0.0150),
                _evaluation("plan_balanced", "balanced", 0.0100),
            ],
        },
        {
            "workload_id": "wkl_low",
            "selected_plan_id": "plan_quick_low",
            "oracle_best_plan_id": "plan_balanced_low",
            "evaluations": [
                _evaluation("plan_quick_low", "quick_turnaround", 0.0108),
                _evaluation("plan_balanced_low", "balanced", 0.0100),
            ],
        },
    ]
    annotated = annotate_validation_results(results, objective="ttfr")
    assert annotated["selection_confidence_counts"] == {"low": 1, "medium": 1, "high": 0}
    assert annotated["high_confidence_top1_accuracy"] is None


def test_confidence_summary_note_marks_heldout_boundary_as_reached():
    markdown = build_confidence_summary_markdown(
        {
            "summary_path": "artifacts/example/summary.json",
            "dataset_name": "example",
            "confidence_version": "aqs.validation_confidence.v1",
            "workload_count": 5,
            "top1_accuracy": 0.8,
            "mean_regret": 0.001,
            "heldout_mean_regret": 0.0,
            "top1_within_1ms_rate": 1.0,
            "top1_within_3pct_rate": 1.0,
            "high_confidence_top1_accuracy": None,
            "selection_confidence_counts": {"low": 1, "medium": 4, "high": 0},
            "stable_selected_miss_count": 0,
            "selected_dominated_by_top2_count": 0,
            "anchor_candidate_count": 0,
            "anchor_candidate_workloads": [],
            "heldout_workload_count": 5,
            "warnings": [],
            "results": [],
        }
    )
    assert "heldout_workload_count=5" in markdown
    assert "meets or exceeds `5`" in markdown
    assert "below `5`" not in markdown


def test_miss_anchor_marks_selected_dominated_by_top2_when_pairwise_evidence_is_clear():
    results = [
        {
            "workload_id": "wkl_anchor",
            "manifest_path": "workloads/manifests/imported/ovh_v2/01_anchor.yaml",
            "selected_plan_id": "plan_quick",
            "oracle_best_plan_id": "plan_deep",
            "evaluations": [
                _evaluation("plan_quick", "quick_turnaround", 0.0300),
                _evaluation("plan_balanced", "balanced", 0.0210),
                _evaluation("plan_deep", "deep_search", 0.0200),
            ],
        }
    ]
    replicate_lookup = build_replicate_lookup(
        [
            _interleaved_pair_payload(
                "wkl_anchor",
                "quick_turnaround",
                "deep_search",
                replicate_winner_template="deep_search",
                ci_lower_s=-0.0110,
                ci_upper_s=-0.0090,
            ),
            _interleaved_pair_payload(
                "wkl_anchor",
                "quick_turnaround",
                "balanced",
                replicate_winner_template="balanced",
                ci_lower_s=-0.0100,
                ci_upper_s=-0.0080,
            ),
        ]
    )
    annotated = annotate_validation_results(results, objective="ttfr", replicate_lookup=replicate_lookup)
    row = annotated["results"][0]
    assert row["selected_dominated_by_top2"] is True
    assert row["miss_anchor_confidence"] == "high"
    assert row["retune_anchor_candidate"] is True
    assert row["selected_vs_winner_replicate_stability"] == "winner_stable"
    assert row["selected_vs_runner_up_replicate_stability"] == "winner_stable"
    assert annotated["selected_dominated_by_top2_count"] == 1
    assert annotated["stable_selected_miss_count"] == 1
    assert annotated["anchor_candidate_count"] == 1


def test_miss_anchor_requires_clear_pairwise_loss_to_runner_up():
    results = [
        {
            "workload_id": "wkl_runner_up_inconclusive",
            "selected_plan_id": "plan_quick",
            "oracle_best_plan_id": "plan_deep",
            "evaluations": [
                _evaluation("plan_quick", "quick_turnaround", 0.0300),
                _evaluation("plan_balanced", "balanced", 0.0210),
                _evaluation("plan_deep", "deep_search", 0.0200),
            ],
        }
    ]
    replicate_lookup = build_replicate_lookup(
        [
            _interleaved_pair_payload(
                "wkl_runner_up_inconclusive",
                "quick_turnaround",
                "deep_search",
                replicate_winner_template="deep_search",
                ci_lower_s=-0.0110,
                ci_upper_s=-0.0090,
            ),
            _interleaved_pair_payload(
                "wkl_runner_up_inconclusive",
                "quick_turnaround",
                "balanced",
                replicate_winner_template="balanced",
                ci_lower_s=-0.0010,
                ci_upper_s=0.0010,
                conclusion="inconclusive_vs_variance",
            ),
        ]
    )
    annotated = annotate_validation_results(results, objective="ttfr", replicate_lookup=replicate_lookup)
    row = annotated["results"][0]
    assert row["selected_dominated_by_top2"] is False
    assert row["miss_anchor_confidence"] == "medium"
    assert row["retune_anchor_candidate"] is True


def test_miss_anchor_can_be_high_even_when_winner_confidence_stays_low():
    results = [
        {
            "workload_id": "wkl_near_tie_up_top",
            "selected_plan_id": "plan_quick",
            "oracle_best_plan_id": "plan_deep",
            "evaluations": [
                _evaluation("plan_quick", "quick_turnaround", 0.0300),
                _evaluation("plan_balanced", "balanced", 0.0205),
                _evaluation("plan_deep", "deep_search", 0.0200),
            ],
        }
    ]
    replicate_lookup = build_replicate_lookup(
        [
            _interleaved_pair_payload(
                "wkl_near_tie_up_top",
                "quick_turnaround",
                "deep_search",
                replicate_winner_template="deep_search",
                ci_lower_s=-0.0110,
                ci_upper_s=-0.0090,
            ),
            _interleaved_pair_payload(
                "wkl_near_tie_up_top",
                "quick_turnaround",
                "balanced",
                replicate_winner_template="balanced",
                ci_lower_s=-0.0105,
                ci_upper_s=-0.0085,
            ),
        ]
    )
    annotated = annotate_validation_results(results, objective="ttfr", replicate_lookup=replicate_lookup)
    row = annotated["results"][0]
    assert row["selection_confidence"] == "low"
    assert row["miss_anchor_confidence"] == "high"
    assert row["retune_anchor_candidate"] is True


def test_miss_anchor_stays_false_without_replicate_evidence():
    results = [
        {
            "workload_id": "wkl_no_replicates",
            "selected_plan_id": "plan_quick",
            "oracle_best_plan_id": "plan_balanced",
            "evaluations": [
                _evaluation("plan_quick", "quick_turnaround", 0.0200),
                _evaluation("plan_balanced", "balanced", 0.0100),
                _evaluation("plan_deep", "deep_search", 0.0110),
            ],
        }
    ]
    annotated = annotate_validation_results(results, objective="ttfr")
    row = annotated["results"][0]
    assert row["selected_dominated_by_top2"] is False
    assert row["retune_anchor_candidate"] is False
