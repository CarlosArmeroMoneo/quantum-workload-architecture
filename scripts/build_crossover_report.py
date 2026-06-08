from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def _resolve(path: str | None) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def _load_records(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return [row for row in loaded if isinstance(row, dict)]
    if isinstance(loaded, dict) and isinstance(loaded.get("records"), list):
        return [row for row in loaded["records"] if isinstance(row, dict)]
    return []


def _fmt(value: Any) -> str:
    if value is None:
        return "pending"
    return str(value)


def build_report(records: list[dict[str, Any]]) -> str:
    lines = [
        "# Crossover Calibration Report",
        "",
        "Status: generated offline from accepted or pending calibration records.",
        "",
        "This report does not promote pending GCP, Hyperstack, TPU, QPU, or local laptop evidence.",
        "",
        "| Run | Host | Tier | Setup % | Contract % | TTFR Ratio | Iter Ratio | Class |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    if not records:
        lines.append("| pending | pending | pending | pending | pending | pending | pending | insufficient_evidence |")
    for row in records:
        lines.append(
            "| {run} | {host} | {tier} | {setup} | {contract} | {ttfr} | {iter_ratio} | {klass} |".format(
                run=_fmt(row.get("run_id")),
                host=_fmt(row.get("host_id")),
                tier=_fmt(row.get("evidence_tier")),
                setup=_fmt(row.get("setup_share_pct")),
                contract=_fmt(row.get("contract_share_pct")),
                ttfr=_fmt(row.get("ttfr_error_ratio")),
                iter_ratio=_fmt(row.get("iter_error_ratio")),
                klass=_fmt(row.get("interpretation_class")),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The classifier is a transparent heuristic layer. It should be revised only when new accepted evidence justifies changing the thresholds.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a markdown crossover calibration report from normalized records")
    parser.add_argument("--calibration-table-json", help="JSON list of calibration records")
    parser.add_argument("--out", default="docs/reports/crossover_calibration_generated.md")
    args = parser.parse_args()

    records = _load_records(_resolve(args.calibration_table_json))
    output = _resolve(args.out)
    assert output is not None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_report(records), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
