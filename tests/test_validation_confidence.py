from aqs.validation_confidence import annotate_validation_results, build_replicate_lookup


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
