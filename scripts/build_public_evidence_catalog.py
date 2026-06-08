from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aqs.evidence_catalog import build_evidence_catalog, write_catalog_csv, write_catalog_markdown  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the public curated-evidence catalog")
    parser.add_argument("--evidence-dir", default="evidence/first_real_profiler_slice")
    parser.add_argument("--out-csv")
    parser.add_argument("--out-md")
    parser.add_argument("--json", action="store_true", help="Print catalog rows as JSON")
    args = parser.parse_args()

    rows = build_evidence_catalog(REPO_ROOT / args.evidence_dir)
    if args.out_csv:
        write_catalog_csv(rows, REPO_ROOT / args.out_csv)
    if args.out_md:
        write_catalog_markdown(rows, REPO_ROOT / args.out_md)
    if args.json or (not args.out_csv and not args.out_md):
        print(json.dumps(rows, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
