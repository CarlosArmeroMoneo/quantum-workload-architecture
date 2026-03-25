from importlib.metadata import version as dist_version
from pathlib import Path

from aqs import __version__
from aqs.cli import _json_safe, build_parser, main


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


def test_distribution_metadata_matches_imported_version():
    assert dist_version("aqs") == __version__


def test_cli_description_uses_public_project_name():
    parser = build_parser()
    assert parser.description == "Quantum Workload Architecture CLI"


def test_main_reports_cli_version(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"aqs {__version__}"
