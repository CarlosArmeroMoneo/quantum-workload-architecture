import importlib.util
from pathlib import Path


def _load_module():
    script_path = Path("scripts/build_model_calibration_table.py")
    spec = importlib.util.spec_from_file_location("build_model_calibration_table", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_compute_ratio_handles_normal_and_zero_cases():
    module = _load_module()

    assert module.compute_ratio(4.0, 2.0) == 2.0
    assert module.compute_ratio(4.0, 0.0) is None
    assert module.compute_ratio(None, 2.0) is None


def test_build_rows_includes_pending_gcp_without_artifacts():
    module = _load_module()

    rows = module.build_rows()
    pending = [row for row in rows if row["case_name"] == "GCP A100 GHZ3 portability pending"]
    assert len(pending) == 1
    assert pending[0]["evidence_tier"] == "pending/unaccepted"
    assert pending[0]["actual_ttfr_s"] is None
    assert pending[0]["interpretation_class"] == "pending_a100_portability_gate"


def test_build_rows_keeps_sources_repo_relative():
    module = _load_module()

    rows = module.build_rows()
    for row in rows:
        source = row["source_artifact_path"]
        assert not source.startswith("C:")
        assert "\\" not in source


def test_write_markdown_contains_expected_cases(tmp_path):
    module = _load_module()
    output = tmp_path / "table.md"

    rows = module.build_rows()
    module.write_markdown(rows, output)
    text = output.read_text(encoding="utf-8")

    assert "OVH dense ring6 batched" in text
    assert "OVH GHZ3 amplitude" in text
    assert "GCP A100 GHZ3 portability pending" in text
    assert "not accepted evidence" in text
