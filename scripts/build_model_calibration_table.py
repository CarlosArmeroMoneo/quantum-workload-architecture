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

from aqs.manifest import load_yaml  # noqa: E402


COLUMNS = [
    "case_name",
    "host",
    "workload",
    "evidence_tier",
    "predicted_ttfr_s",
    "actual_ttfr_s",
    "ttfr_error_ratio",
    "predicted_iter_ms",
    "actual_iter_ms",
    "iter_error_ratio",
    "interpretation_class",
    "source_artifact_path",
]


def compute_ratio(actual: Any, predicted: Any) -> float | None:
    try:
        actual_value = float(actual)
        predicted_value = float(predicted)
    except (TypeError, ValueError):
        return None
    if predicted_value <= 0.0:
        return None
    return round(actual_value / predicted_value, 6)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _index_by_run_id(paths: list[Path], run_id_getter: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for path in paths:
        payload = _load_json(path)
        if run_id_getter == "profile":
            run_id = payload.get("run_id")
        elif run_id_getter == "arch":
            run_id = payload.get("source_run_id")
        else:
            run_id = None
        if run_id:
            payload["_source_path"] = _repo_relative(path)
            indexed[str(run_id)] = payload
    return indexed


def _execution_paths(evidence_dir: Path) -> list[Path]:
    candidates = sorted(evidence_dir.glob("*.execution.json"))
    deduped: dict[str, Path] = {}
    for path in candidates:
        payload = _load_json(path)
        run_id = str((payload.get("execution_run") or {}).get("run_id") or path.name)
        deduped[run_id] = path
    return sorted(deduped.values())


def _case_name(path: Path) -> str:
    name = path.name
    if "dense_ring6_batched" in name:
        return "OVH dense ring6 batched"
    if "ghz3_amplitude" in name:
        return "OVH GHZ3 amplitude"
    return path.stem.replace(".", "_")


def _first_nomination(arch: dict[str, Any] | None) -> dict[str, Any]:
    nominations = (arch or {}).get("nominations")
    if isinstance(nominations, list) and nominations and isinstance(nominations[0], dict):
        return nominations[0]
    return {}


def _evidence_tier(run: dict[str, Any], profile: dict[str, Any] | None, arch: dict[str, Any] | None) -> str:
    nomination = _first_nomination(arch)
    if nomination.get("nomination_source") == "real_profiler_analysis":
        return "Tier 3"
    if profile and profile.get("profiler_kind") in {"nsys", "ncu", "both"}:
        return "Tier 2"
    if run.get("execution_source") and run.get("status") == "success":
        return "Tier 1"
    return "Tier 0"


def _interpretation_class(case_name: str, evidence_tier: str) -> str:
    if "GHZ3" in case_name:
        return "tiny_workload_calibration"
    if evidence_tier == "Tier 3":
        return "real_arch_nomination"
    return "performance_only"


def build_rows(
    *,
    evidence_dir: str | Path = "evidence/first_real_profiler_slice",
    gcp_slice_path: str | Path = "configs/profiling/gcp_a100_portability_slice.yaml",
) -> list[dict[str, Any]]:
    evidence_path = REPO_ROOT / evidence_dir if not Path(evidence_dir).is_absolute() else Path(evidence_dir)
    profiles = _index_by_run_id(sorted(evidence_path.glob("*.profile_summary.json")), "profile")
    arches = _index_by_run_id(sorted(evidence_path.glob("*.arch.json")), "arch")
    rows: list[dict[str, Any]] = []

    for path in _execution_paths(evidence_path):
        payload = _load_json(path)
        run = payload.get("execution_run") or {}
        selected_plan = payload.get("selected_plan") or {}
        system_manifest = payload.get("system_manifest") or {}
        run_id = str(run.get("run_id") or "")
        profile = profiles.get(run_id)
        arch = arches.get(run_id)
        evidence_tier = _evidence_tier(run, profile, arch)
        case_name = _case_name(path)
        rows.append(
            {
                "case_name": case_name,
                "host": system_manifest.get("system_name") or payload.get("system_name"),
                "workload": run.get("workload_id") or payload.get("workload_id"),
                "evidence_tier": evidence_tier,
                "predicted_ttfr_s": _safe_float(selected_plan.get("predicted_ttfr_s")),
                "actual_ttfr_s": _safe_float(run.get("ttfr_s")),
                "ttfr_error_ratio": compute_ratio(run.get("ttfr_s"), selected_plan.get("predicted_ttfr_s")),
                "predicted_iter_ms": _safe_float(selected_plan.get("predicted_iter_ms")),
                "actual_iter_ms": _safe_float(run.get("steady_iter_ms")),
                "iter_error_ratio": compute_ratio(run.get("steady_iter_ms"), selected_plan.get("predicted_iter_ms")),
                "interpretation_class": _interpretation_class(case_name, evidence_tier),
                "source_artifact_path": _repo_relative(path),
            }
        )

    gcp_path = REPO_ROOT / gcp_slice_path if not Path(gcp_slice_path).is_absolute() else Path(gcp_slice_path)
    if gcp_path.exists():
        gcp_slice = load_yaml(gcp_path)
        workload = (gcp_slice.get("workload") or {}).get("manifest")
        rows.append(
            {
                "case_name": "GCP A100 GHZ3 portability pending",
                "host": "gcp_a100_sxm4_40gb",
                "workload": workload,
                "evidence_tier": "pending/unaccepted",
                "predicted_ttfr_s": None,
                "actual_ttfr_s": None,
                "ttfr_error_ratio": None,
                "predicted_iter_ms": None,
                "actual_iter_ms": None,
                "iter_error_ratio": None,
                "interpretation_class": "pending_a100_portability_gate",
                "source_artifact_path": _repo_relative(gcp_path),
            }
        )

    return rows


def _fmt(value: Any) -> str:
    if value is None:
        return "pending"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def write_markdown(rows: list[dict[str, Any]], output_path: str | Path) -> None:
    path = REPO_ROOT / output_path if not Path(output_path).is_absolute() else Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Model Calibration Table",
        "",
        "Generated from accepted tracked evidence plus pending acceptance-gated lanes. GCP A100 rows are not accepted evidence until pinned artifacts pass the acceptance gate.",
        "",
        "| Case | Host | Workload | Tier | Pred TTFR s | Actual TTFR s | TTFR Ratio | Pred Iter ms | Actual Iter ms | Iter Ratio | Interpretation | Source |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {case} | {host} | {workload} | {tier} | {pt} | {at} | {tr} | {pi} | {ai} | {ir} | {klass} | `{source}` |".format(
                case=_fmt(row["case_name"]),
                host=_fmt(row["host"]),
                workload=_fmt(row["workload"]),
                tier=_fmt(row["evidence_tier"]),
                pt=_fmt(row["predicted_ttfr_s"]),
                at=_fmt(row["actual_ttfr_s"]),
                tr=_fmt(row["ttfr_error_ratio"]),
                pi=_fmt(row["predicted_iter_ms"]),
                ai=_fmt(row["actual_iter_ms"]),
                ir=_fmt(row["iter_error_ratio"]),
                klass=_fmt(row["interpretation_class"]),
                source=_fmt(row["source_artifact_path"]),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the public model-calibration evidence table")
    parser.add_argument("--evidence-dir", default="evidence/first_real_profiler_slice")
    parser.add_argument("--gcp-slice", default="configs/profiling/gcp_a100_portability_slice.yaml")
    parser.add_argument("--out", default="docs/reports/model_calibration_table.md")
    args = parser.parse_args()

    rows = build_rows(evidence_dir=args.evidence_dir, gcp_slice_path=args.gcp_slice)
    write_markdown(rows, args.out)
    print(f"Wrote {args.out} with {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
