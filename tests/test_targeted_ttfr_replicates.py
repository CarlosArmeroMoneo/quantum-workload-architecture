from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_targeted_ttfr_replicates.py"
    spec = importlib.util.spec_from_file_location("run_targeted_ttfr_replicates", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _sample(ttfr_s: float, planner_time_s: float = 0.002, setup_time_s: float = 0.001, first_contract_time_s: float = 0.004) -> dict[str, float]:
    return {
        "ttfr_s": ttfr_s,
        "planner_time_s": planner_time_s,
        "setup_time_s": setup_time_s,
        "first_contract_time_s": first_contract_time_s,
    }


def test_interleaved_pair_summary_marks_inconclusive_when_delta_ci_crosses_zero():
    module = _load_module()
    summary = module._build_interleaved_pair_summary(
        {
            "workload_id": "wkl_inconclusive",
            "manifest_path": "workloads/manifests/imported/example.yaml",
            "family_id": "dense_universal",
            "repeat_count_hint": 1,
        },
        "quick_turnaround",
        {"observed_ttfr_s": 0.0102},
        [_sample(0.0100), _sample(0.0104)],
        "balanced",
        {"observed_ttfr_s": 0.0100},
        [_sample(0.0101), _sample(0.0102)],
        left_payload_paths=["/tmp/left0.json", "/tmp/left1.json"],
        right_payload_paths=["/tmp/right0.json", "/tmp/right1.json"],
    )
    assert summary["pair_mode"] == "interleaved"
    assert summary["conclusion"] == "inconclusive_vs_variance"
    delta_ci = summary["delta_confidence_interval"]
    assert float(delta_ci["lower_s"]) <= 0.0 <= float(delta_ci["upper_s"])


def test_interleaved_pair_summary_marks_flipped_winner_when_delta_ci_is_clear():
    module = _load_module()
    summary = module._build_interleaved_pair_summary(
        {
            "workload_id": "wkl_flip",
            "manifest_path": "workloads/manifests/imported/example.yaml",
            "family_id": "dense_universal",
            "repeat_count_hint": 1,
        },
        "quick_turnaround",
        {"observed_ttfr_s": 0.0108},
        [_sample(0.0080), _sample(0.0081), _sample(0.0082)],
        "balanced",
        {"observed_ttfr_s": 0.0100},
        [_sample(0.0094), _sample(0.0096), _sample(0.0095)],
        left_payload_paths=["/tmp/left0.json", "/tmp/left1.json", "/tmp/left2.json"],
        right_payload_paths=["/tmp/right0.json", "/tmp/right1.json", "/tmp/right2.json"],
    )
    assert summary["pair_mode"] == "interleaved"
    assert summary["baseline_winner_template"] == "balanced"
    assert summary["replicate_winner_template"] == "quick_turnaround"
    assert summary["conclusion"] == "winner_flipped_vs_single_shot"
    assert float(summary["delta_confidence_interval"]["lower_s"]) > 0.0
