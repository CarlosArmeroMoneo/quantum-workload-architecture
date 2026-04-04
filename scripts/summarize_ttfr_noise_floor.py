from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ci_half_width_ms(payload: dict[str, Any]) -> float | None:
    ci = payload.get("delta_confidence_interval") or {}
    half_width_s = ci.get("half_width_s")
    if half_width_s is None:
        return None
    return round(float(half_width_s) * 1000.0, 3)


def _ttfr_stat_ms(payload: dict[str, Any], side: str, key: str) -> float | None:
    stats = payload.get(f"{side}_ttfr_stats") or {}
    value = stats.get(key)
    if value is None:
        return None
    return round(float(value) * 1000.0, 3)


def _study_interpretation(rows: list[dict[str, Any]]) -> str:
    half_widths = [row["ci_half_width_ms"] for row in rows if row["ci_half_width_ms"] is not None]
    if not half_widths:
        return "Null-pair uncertainty is unavailable, so the OVH TTFR certification floor is unknown."
    max_half = max(half_widths)
    median_half = sorted(half_widths)[len(half_widths) // 2]
    if max_half >= 5.0 or median_half >= 5.0:
        return (
            "The null-pair uncertainty band is on the order of the 1-5 ms winner gaps we care about, "
            "so exact TTFR top-1 in that regime should stay descriptive-only on this host."
        )
    if max_half < 1.0:
        return (
            "The null-pair uncertainty band is materially below the 1-5 ms winner gaps we care about, "
            "so the current interleaved method is strong enough to certify small TTFR edges."
        )
    return (
        "The null-pair uncertainty band sits between 1 ms and 5 ms, so sub-millisecond claims remain descriptive-only "
        "while larger low-single-digit millisecond gaps may still need targeted confirmation."
    )


def _build_rows(pair_payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for payload in pair_payloads:
        ci = payload.get("delta_confidence_interval") or {}
        rows.append(
            {
                "workload_id": payload.get("workload_id"),
                "manifest_path": payload.get("manifest_path"),
                "pair_mode": payload.get("pair_mode"),
                "left_template": payload.get("left_template"),
                "right_template": payload.get("right_template"),
                "delta_mean_s": payload.get("delta_mean_s"),
                "delta_median_s": payload.get("delta_median_s"),
                "delta_stdev_s": payload.get("delta_stdev_s"),
                "delta_95pct_confidence_interval": {
                    "lower_s": ci.get("lower_s"),
                    "upper_s": ci.get("upper_s"),
                    "half_width_s": ci.get("half_width_s"),
                },
                "ci_half_width_ms": _ci_half_width_ms(payload),
                "left_ttfr_median_ms": _ttfr_stat_ms(payload, "left", "median"),
                "left_ttfr_stdev_ms": _ttfr_stat_ms(payload, "left", "stdev"),
                "right_ttfr_median_ms": _ttfr_stat_ms(payload, "right", "median"),
                "right_ttfr_stdev_ms": _ttfr_stat_ms(payload, "right", "stdev"),
                "conclusion": payload.get("conclusion"),
                "pair_summary_path": payload.get("_pair_summary_path"),
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "workload_id",
        "manifest_path",
        "pair_mode",
        "left_template",
        "right_template",
        "delta_mean_s",
        "delta_median_s",
        "delta_stdev_s",
        "ci_half_width_ms",
        "left_ttfr_median_ms",
        "left_ttfr_stdev_ms",
        "right_ttfr_median_ms",
        "right_ttfr_stdev_ms",
        "conclusion",
        "pair_summary_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# OVH TTFR Noise Floor v1",
        "",
        f"- Pair summaries: `{len(payload.get('rows') or [])}`",
        f"- Max null-pair CI half-width: `{payload.get('max_ci_half_width_ms')} ms`",
        f"- Median null-pair CI half-width: `{payload.get('median_ci_half_width_ms')} ms`",
        f"- Interpretation: {payload.get('interpretation')}",
        "",
        "## Null Pairs",
        "",
        "| Workload | Pair | Delta mean (ms) | Delta median (ms) | Delta stdev (ms) | CI half-width (ms) | Left median (ms) | Right median (ms) | Conclusion |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload.get("rows") or []:
        lines.append(
            f"| `{Path(str(row.get('manifest_path') or '')).name}` | "
            f"`{row.get('left_template')} vs {row.get('right_template')}` | "
            f"{((row.get('delta_mean_s') or 0.0) * 1000.0):.3f} | "
            f"{((row.get('delta_median_s') or 0.0) * 1000.0):.3f} | "
            f"{((row.get('delta_stdev_s') or 0.0) * 1000.0):.3f} | "
            f"{row.get('ci_half_width_ms') or 0.0:.3f} | "
            f"{row.get('left_ttfr_median_ms') or 0.0:.3f} | "
            f"{row.get('right_ttfr_median_ms') or 0.0:.3f} | "
            f"`{row.get('conclusion')}` |"
        )
    lines.extend(
        [
            "",
            "## Paths",
            "",
        ]
    )
    for row in payload.get("rows") or []:
        lines.append(f"- `{row.get('pair_summary_path')}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize interleaved null-pair TTFR runs into a host noise-floor report")
    parser.add_argument("--pair-summary", action="append", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--name", default="ovh_ttfr_noise_floor_v1")
    args = parser.parse_args(argv)

    pair_payloads = []
    for path_str in args.pair_summary:
        path = Path(path_str).resolve()
        payload = _load_json(path)
        payload["_pair_summary_path"] = str(path)
        pair_payloads.append(payload)

    rows = _build_rows(pair_payloads)
    half_widths = [row["ci_half_width_ms"] for row in rows if row["ci_half_width_ms"] is not None]
    payload = {
        "study_name": args.name,
        "row_count": len(rows),
        "max_ci_half_width_ms": round(max(half_widths), 3) if half_widths else None,
        "median_ci_half_width_ms": round(statistics.median(half_widths), 3) if half_widths else None,
        "interpretation": _study_interpretation(rows),
        "rows": rows,
    }

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    json_path = outdir / f"{args.name}.json"
    md_path = outdir / f"{args.name}.md"
    csv_path = outdir / f"{args.name}.csv"
    _dump_json(json_path, payload)
    md_path.write_text(_build_markdown(payload), encoding="utf-8")
    _write_csv(csv_path, rows)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
