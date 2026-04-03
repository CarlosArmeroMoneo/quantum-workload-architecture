import json
from pathlib import Path


def test_truth_pass_artifacts_exist_and_show_distinct_replicates():
    root = Path("artifacts/truth_pass")
    validation = json.loads((root / "manifest_implemented_validation.json").read_text(encoding="utf-8"))
    replicate_0 = json.loads((root / "replicate_0.execution.json").read_text(encoding="utf-8"))
    replicate_1 = json.loads((root / "replicate_1.execution.json").read_text(encoding="utf-8"))

    assert validation["mode"] == "implemented"
    assert validation["status"] == "success"
    assert replicate_0["execution_run"]["replicate_idx"] == 0
    assert replicate_1["execution_run"]["replicate_idx"] == 1
    assert replicate_0["execution_run"]["run_id"] != replicate_1["execution_run"]["run_id"]
