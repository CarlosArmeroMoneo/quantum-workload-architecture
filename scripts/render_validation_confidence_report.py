from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aqs.validation_confidence import annotate_validation_summary, build_replicate_lookup, write_confidence_summary_artifacts  # noqa: E402


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render confidence-aware validation metrics from a stored summary")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--pair-summary", action="append", default=[])
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args(argv)

    summary = _load_json(Path(args.summary))
    pair_payloads = [_load_json(Path(path)) for path in args.pair_summary]
    annotated = annotate_validation_summary(summary, replicate_lookup=build_replicate_lookup(pair_payloads))
    annotated["summary_path"] = str(Path(args.summary).resolve())

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    artifact_paths = write_confidence_summary_artifacts(annotated, outdir)

    print(f"Wrote {artifact_paths['confidence_summary_json_path']}")
    print(f"Wrote {artifact_paths['confidence_summary_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
