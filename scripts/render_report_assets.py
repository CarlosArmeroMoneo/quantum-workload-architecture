from __future__ import annotations

import argparse
from pathlib import Path


PORTFOLIO_ITEMS = [
    ("stack/00-truth-capability-matrix", "Truth pass and capability matrix", "complete"),
    ("stack/01-lineage-and-explicit-execution", "Repo metadata and explicit execution lineage", "complete"),
    ("stack/02-test-buckets-and-ci", "Test buckets, CI, and truth-pass fixtures", "complete"),
    ("stack/03-campaign-manifest-and-db", "Campaign manifests and experiment schema", "complete"),
    ("stack/04-campaign-runner-and-reporting", "Campaign runner and reporting", "complete"),
    ("stack/05-repeat-roi-foundation", "Repeat ROI dry-run foundation", "complete"),
    ("stack/06-ncu-diagnostics-foundation", "NCU diagnostics foundation", "complete"),
    ("stack/07-cuda-graphs-foundation", "CUDA Graph execution foundation", "complete"),
    ("stack/08-cudaq-adapter", "Adapter-backed CUDA-Q manifests", "complete"),
    ("stack/09-tiny-mnk-sidecar-foundation", "Tiny-MNK sidecar foundation", "complete"),
    ("stack/10-remote-repeat-roi-results", "Measured repeat ROI results on the OVH CUDA host", "complete"),
    ("stack/11-remote-ncu-and-graphs-results", "Measured diagnostic NCU and graph A/B results", "complete"),
    ("stack/12-remote-cudaq-and-sidecar-results", "Measured CUDA-Q adapter comparison and sidecar results", "complete"),
    ("stack/13-portfolio-packaging", "Portfolio packaging and release manifest", "complete"),
]

STATUS_COLORS = {
    "complete": "#1f7a1f",
}

STATUS_LABELS = {
    "complete": "Complete",
}


def render_svg(output_path: str | Path) -> None:
    width = 1080
    row_height = 34
    header_height = 72
    height = header_height + (len(PORTFOLIO_ITEMS) * row_height) + 24
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
        '<style>',
        'text{font-family:Consolas,Menlo,monospace;fill:#17202a}',
        '.title{font-size:22px;font-weight:700}',
        '.subtitle{font-size:12px;fill:#52606d}',
        '.branch{font-size:12px;font-weight:700}',
        '.detail{font-size:12px}',
        '.status{font-size:11px;font-weight:700}',
        '</style>',
        '<rect x="0" y="0" width="1080" height="100%" fill="#f8fafc"/>',
        '<text x="28" y="34" class="title">Portfolio Stack Status</text>',
        '<text x="28" y="56" class="subtitle">The measured OVH host pass now completes stack/10 through stack/12, and stack/13 packages the curated evidence.</text>',
    ]
    for index, (branch, detail, status) in enumerate(PORTFOLIO_ITEMS):
        y = header_height + (index * row_height)
        fill = "#ffffff" if index % 2 == 0 else "#f1f5f9"
        lines.append(f'<rect x="24" y="{y - 20}" width="1032" height="28" rx="6" fill="{fill}"/>')
        lines.append(f'<text x="36" y="{y}" class="branch">{branch}</text>')
        lines.append(f'<text x="360" y="{y}" class="detail">{detail}</text>')
        lines.append(f'<text x="980" y="{y}" class="status" text-anchor="end" fill="{STATUS_COLORS[status]}">{STATUS_LABELS[status]}</text>')
    lines.append("</svg>")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render portfolio report SVG assets")
    parser.add_argument(
        "--output",
        default="docs/reports/assets/portfolio_status.svg",
        help="SVG output path",
    )
    args = parser.parse_args(argv)
    render_svg(args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
