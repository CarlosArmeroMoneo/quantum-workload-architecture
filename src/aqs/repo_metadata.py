from __future__ import annotations

import platform
from pathlib import Path
import subprocess
from typing import Any

from . import __version__
from .paths import repo_root


def _git(command: list[str], *, cwd: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *command],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return (completed.stdout or "").strip() or None


def capture_repo_metadata(root: str | Path | None = None) -> dict[str, Any]:
    root_path = Path(root) if root else repo_root()
    commit = _git(["rev-parse", "HEAD"], cwd=root_path)
    branch = _git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd=root_path)
    dirty_output = _git(["status", "--short"], cwd=root_path) or ""

    return {
        "repo_root": str(root_path).replace("\\", "/"),
        "git_commit": commit,
        "git_dirty": bool(dirty_output.strip()),
        "git_ref_kind": "branch" if branch else "detached",
        "git_branch": branch,
        "python_version": platform.python_version(),
        "package_version": __version__,
    }


__all__ = ["capture_repo_metadata"]
