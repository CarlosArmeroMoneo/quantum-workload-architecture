from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_render_report_assets_emits_portfolio_svg(tmp_path):
    output_path = tmp_path / "portfolio_status.svg"
    completed = subprocess.run(
        [sys.executable, "scripts/render_report_assets.py", "--output", str(output_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    svg_text = output_path.read_text(encoding="utf-8")
    assert "stack/09-tiny-mnk-sidecar-foundation" in svg_text
    assert "Blocked: Remote Host Required" in svg_text


def test_portfolio_release_manifest_and_checksums_are_present():
    manifest_path = Path("docs/reports/portfolio_release_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["api_version"] == "aqs.portfolio_release.v1"
    for artifact in manifest["artifacts"]:
        assert Path(artifact["path"]).exists(), artifact["path"]

    checksums = Path("SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    assert any(line.endswith("docs/reports/portfolio_index.md") for line in checksums)
    assert any(line.endswith("scripts/render_report_assets.py") for line in checksums)
