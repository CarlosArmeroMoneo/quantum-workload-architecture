from __future__ import annotations

import argparse
import json
from pathlib import Path

from tiny_mnk_io import extract_tiny_mnk_kernels_from_csv, normalize_path


def build_reference_payload(ncu_csv_path: str | Path, *, profile_summary_path: str | Path | None = None) -> dict:
    kernels = extract_tiny_mnk_kernels_from_csv(ncu_csv_path)
    if not kernels:
        raise SystemExit(f"no tiny-MNK kernels found in {ncu_csv_path}")
    return {
        "api_version": "aqs.tiny_mnk_reference.v1",
        "source_ncu_csv": normalize_path(ncu_csv_path),
        "source_profile_summary": normalize_path(profile_summary_path) if profile_summary_path else None,
        "reference_kernels": kernels,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract tiny-MNK reference kernels from an Nsight Compute CSV")
    parser.add_argument("--input", required=True, help="Path to the Nsight Compute CSV export")
    parser.add_argument("--output", required=True, help="Path to write the extracted reference JSON")
    parser.add_argument("--profile-summary", help="Optional profile_summary.json path to record alongside the CSV")
    args = parser.parse_args(argv)

    payload = build_reference_payload(args.input, profile_summary_path=args.profile_summary)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
