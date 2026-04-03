from importlib.metadata import version as dist_version
import json
from pathlib import Path
import shutil

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


def test_manifest_validate_expands_globs(capsys, monkeypatch, tmp_path):
    source = Path("workloads/manifests/templates/dense_universal.template.yaml")
    copied = tmp_path / source.name
    shutil.copyfile(source, copied)
    monkeypatch.chdir(tmp_path)

    assert main(["manifest", "validate", "*.yaml"]) == 0
    assert f"[OK] {copied.name}" in capsys.readouterr().out


def test_campaign_cli_validate_and_run(capsys, tmp_path):
    assert main(["campaign", "validate", "--manifest", "configs/campaigns/cpu_dry_run_v1.yaml"]) == 0
    validate_payload = json.loads(capsys.readouterr().out)
    assert validate_payload["cell_count"] == 8

    outdir = tmp_path / "campaign"
    assert main(["campaign", "run", "--manifest", "configs/campaigns/cpu_dry_run_v1.yaml", "--outdir", str(outdir)]) == 0
    run_payload = json.loads(capsys.readouterr().out)
    assert run_payload["status_counts"] == {"success": 16}
    assert (outdir / "summary.json").exists()

    assert main(["campaign", "summarize", "--manifest", "configs/campaigns/cpu_dry_run_v1.yaml", "--outdir", str(outdir)]) == 0
    summarize_payload = json.loads(capsys.readouterr().out)
    assert summarize_payload["campaign_id"] == run_payload["campaign_id"]
