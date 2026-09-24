import json

import pytest

from aqs.arch import ArchAnalysisError, analyze_execution_json, analyze_execution_payload


def _payload():
    return {
        "execution_run": {
            "run_id": "run_expected",
            "wall_s": 0.1,
            "failure_detail_json": {
                "nvtx_phase_version": "aqs.nvtx.v1",
                "phase_times": {"load_circuit": 0.03, "contract_first": 0.01},
            },
        },
        "profile_summary": None,
    }


def _summary(run_id):
    return {"run_id": run_id, "profile_id": "prof_expected", "profiler_kind": "ncu"}


@pytest.mark.parametrize("profile_run_id", ["run_other", None, ""])
def test_adjacent_profile_without_matching_identity_is_not_attached(tmp_path, profile_run_id):
    path = tmp_path / "case.execution.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")
    (tmp_path / "case.profile_summary.json").write_text(json.dumps(_summary(profile_run_id)), encoding="utf-8")
    result = analyze_execution_json(path)
    assert result["source_profile_id"] is None
    assert result["nominations"]
    assert all(row["nomination_source"] == "measured_runtime_analysis" for row in result["nominations"])


def test_discovery_skips_wrong_run_and_finds_matching_sibling(tmp_path):
    path = tmp_path / "case.execution.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")
    (tmp_path / "case.profile_summary.json").write_text(json.dumps(_summary("run_other")), encoding="utf-8")
    (tmp_path / "valid.profile_summary.json").write_text(json.dumps(_summary("run_expected")), encoding="utf-8")
    result = analyze_execution_json(path)
    assert result["source_profile_id"] == "prof_expected"
    assert all(row["nomination_source"] == "real_profiler_analysis" for row in result["nominations"])


def test_explicit_profile_identity_mismatch_is_rejected():
    payload = _payload()
    payload["profile_summary"] = _summary("run_other")
    with pytest.raises(ArchAnalysisError, match="run_id does not match"):
        analyze_execution_payload(payload)


def test_missing_execution_identity_does_not_attach_a_profile(tmp_path):
    payload = _payload()
    payload["execution_run"]["run_id"] = ""
    path = tmp_path / "case.execution.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "case.profile_summary.json").write_text(json.dumps(_summary("")), encoding="utf-8")
    assert analyze_execution_json(path)["source_profile_id"] is None
