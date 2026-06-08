from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aqs.kernel_taxonomy import derive_profiler_signals, summarize_kernel_families  # noqa: E402


DEFAULT_PROFILE_GLOB = "evidence/first_real_profiler_slice/*.profile_summary.json"


def _repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {_repo_path(path)}")
    return payload


def _profile_paths(profile_summary: str | None, profile_glob: str | None) -> list[Path]:
    if profile_summary:
        path = Path(profile_summary)
        return [path if path.is_absolute() else REPO_ROOT / path]
    pattern = profile_glob or DEFAULT_PROFILE_GLOB
    paths = [Path(item) for item in glob.glob(str(REPO_ROOT / pattern), recursive=True)]
    return sorted(path for path in paths if path.is_file())


def summarize_profile(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    top_kernels = payload.get("top_kernels_json")
    kernels = top_kernels if isinstance(top_kernels, list) else []
    derived = payload.get("derived_signals_json")
    derived = derived if isinstance(derived, dict) else {}
    taxonomy = summarize_kernel_families(kernels, occupancy_pct=payload.get("occupancy_pct"))
    signals = dict(taxonomy["signals"])
    replay_passes = _safe_int(derived.get("profiler__replayer_passes") or derived.get("profiler_replayer_passes"))
    if replay_passes is not None:
        signals.update(
            derive_profiler_signals(
                taxonomy["kernel_family_counts"],
                occupancy_pct=payload.get("occupancy_pct"),
                profiler_replay_passes=replay_passes,
            )
        )

    return {
        "path": _repo_path(path),
        "run_id": payload.get("run_id"),
        "profile_id": payload.get("profile_id"),
        "profiler_kind": payload.get("profiler_kind"),
        "profile_source": derived.get("profile_source"),
        "kernel_count": len(kernels),
        "kernel_family_counts": taxonomy["kernel_family_counts"],
        "kernel_category_counts": taxonomy["kernel_category_counts"],
        "top_kernel_families": taxonomy["top_kernel_families"],
        "occupancy_band": taxonomy["occupancy_band"],
        "signals": signals,
    }


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _fmt_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"`{key}`={value}" for key, value in sorted(counts.items()))


def _fmt_signals(signals: dict[str, bool]) -> str:
    return ", ".join(f"`{key}`={str(value).lower()}" for key, value in sorted(signals.items()))


def write_markdown(rows: list[dict[str, Any]], out: str | Path) -> None:
    output_path = Path(out)
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Profiler Kernel Taxonomy: Current Evidence",
        "",
        "This report summarizes accepted tracked profile summaries only. It does not add new profiling evidence and does not change the OVH RTX 5000 canonical result.",
        "",
        "## Why Normalize Kernel Names",
        "",
        "Raw Nsight kernel names are long, backend-specific, and unstable across library versions. Atlas maps them into workload-level families so architecture analysis can reason about contraction work, memory movement, initialization, framework overhead, sparse summaries, and profiler replay cautions without overfitting to one mangled symbol.",
        "",
        "## Current Accepted Evidence",
        "",
        "| Profile | Profiler | Kernels | Families | Signals |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| `{path}` | {profiler} | {kernels} | {families} | {signals} |".format(
                path=row["path"],
                profiler=row.get("profiler_kind") or "",
                kernels=row["kernel_count"],
                families=_fmt_counts(row["kernel_family_counts"]),
                signals=_fmt_signals(row["signals"]),
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The accepted OVH Nsight Compute batched profile contains `cutensor_tiny_mnk` contraction kernels, so the contraction kernel family is present.",
            "- The accepted OVH Nsight Systems GHZ3 profile has no top-kernel rows in the reduced summary, so it carries a sparse-profile warning rather than a kernel-family claim.",
            "- Tiny workloads and tiny-MNK kernels are not throughput benchmarks. They are useful for evidence mechanics, portability checks, and launch/setup analysis.",
            "- `launch_bound_signal` is a prompt for a counterfactual experiment, not proof that launch overhead has been solved.",
            "- `memory_bound_signal` should not be inferred unless memory-transfer families dominate the reduced summary.",
            "",
            "## Limits",
            "",
            "- NCU metrics in the current public profile are intentionally reduced and metrics-thin.",
            "- Occupancy is unavailable in the accepted summaries, so utilization claims remain conservative.",
            "- Future A100, H100, TPU, or CUDA-Q runtime claims require separate accepted evidence.",
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize kernel taxonomy from reduced profile summaries")
    parser.add_argument("--profile-summary", help="Single profile_summary JSON")
    parser.add_argument("--profile-glob", help="Glob of profile_summary JSON files")
    parser.add_argument("--out", default="docs/reports/profiler_kernel_taxonomy_current_evidence.md")
    parser.add_argument("--json", action="store_true", help="Print summary rows as JSON")
    args = parser.parse_args()

    paths = _profile_paths(args.profile_summary, args.profile_glob)
    if not paths:
        print("no profile summary files matched", file=sys.stderr)
        return 2

    rows = [summarize_profile(path) for path in paths]
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    write_markdown(rows, args.out)
    if not args.json:
        print(f"Wrote {args.out} with {len(rows)} profile summaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
