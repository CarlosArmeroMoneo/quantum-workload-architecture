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

from aqs.validation_confidence import annotate_validation_summary, build_replicate_lookup  # noqa: E402


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

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    json_path = outdir / "confidence_summary.json"
    md_path = outdir / "confidence_summary.md"

    json_path.write_text(json.dumps(annotated, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Validation Confidence Summary",
        "",
        f"- Source summary: `{Path(args.summary).resolve()}`",
        f"- Dataset: `{annotated.get('dataset_name')}`",
        f"- Confidence version: `{annotated.get('confidence_version')}`",
        f"- Workloads: `{annotated.get('workload_count')}`",
        f"- top1_accuracy: `{annotated.get('top1_accuracy')}`",
        f"- top1_within_1ms_rate: `{annotated.get('top1_within_1ms_rate')}`",
        f"- top1_within_3pct_rate: `{annotated.get('top1_within_3pct_rate')}`",
        f"- high_confidence_top1_accuracy: `{annotated.get('high_confidence_top1_accuracy')}`",
        f"- selection_confidence_counts: `{annotated.get('selection_confidence_counts')}`",
        "",
        "## Workloads",
        "",
        "| Workload | Selected | Winner | Runner-up | Winner gap (ms) | top1<=1ms | top1<=3pct | Confidence |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for workload in annotated.get("results", []):
        lines.append(
            f"| `{Path(str(workload.get('manifest_path') or '')).name}` | "
            f"`{workload.get('selected_template')}` | "
            f"`{workload.get('winner_template')}` | "
            f"`{workload.get('runner_up_template')}` | "
            f"{((workload.get('winner_gap_s') or 0.0) * 1000.0):.3f} | "
            f"`{workload.get('top1_within_1ms')}` | "
            f"`{workload.get('top1_within_3pct')}` | "
            f"`{workload.get('selection_confidence')}` |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `top1_within_1ms_rate` and `top1_within_3pct_rate` are additive to `top1_accuracy`; they do not replace it.",
            "- `selection_confidence_counts` currently bucket workloads as low / medium / high using the existing near-tie thresholds `0.001 s` or `3%`.",
            f"- Heldout metrics remain descriptive while `heldout_workload_count={annotated.get('heldout_workload_count')}` is below `5`.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
