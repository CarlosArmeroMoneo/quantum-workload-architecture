from pathlib import Path

from aqs.cli import _json_safe


def test_json_safe_serializes_nested_path_objects():
    payload = {
        "root": Path("artifacts") / "real_profile_runs" / "run.json",
        "nested": [
            {"profile": Path("artifacts") / "profiles" / "sample.profile_summary.json"},
            (Path("configs") / "systems" / "ovh_gra9_rtx5000_28.yml",),
        ],
        "paths": {
            Path("docs") / "runbooks" / "ovh_cu13_real_execution.md",
            Path("README.md"),
        },
    }

    safe = _json_safe(payload)

    assert safe["root"] == "artifacts/real_profile_runs/run.json"
    assert safe["nested"][0]["profile"] == "artifacts/profiles/sample.profile_summary.json"
    assert safe["nested"][1][0] == "configs/systems/ovh_gra9_rtx5000_28.yml"
    assert safe["paths"] == [
        "README.md",
        "docs/runbooks/ovh_cu13_real_execution.md",
    ]
