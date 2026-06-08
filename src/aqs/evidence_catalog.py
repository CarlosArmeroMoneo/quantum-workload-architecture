from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .kernel_taxonomy import summarize_kernel_families


CATALOG_COLUMNS = [
    "run_id",
    "system_name",
    "gpu_model",
    "workload_id",
    "execution_source",
    "profiler_kind",
    "predicted_ttfr_s",
    "actual_ttfr_s",
    "ttfr_error_ratio",
    "predicted_iter_ms",
    "actual_iter_ms",
    "iter_error_ratio",
    "bottleneck_family",
    "nomination_source",
    "kernel_family_counts_json",
    "interpretation_class",
    "tiny_workload_warning",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_ratio(actual: Any, predicted: Any) -> float | None:
    try:
        predicted_value = float(predicted)
        actual_value = float(actual)
    except (TypeError, ValueError):
        return None
    if predicted_value <= 0.0:
        return None
    return round(actual_value / predicted_value, 6)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_nomination(arch_payload: dict[str, Any] | None) -> dict[str, Any]:
    nominations = (arch_payload or {}).get("nominations")
    if not isinstance(nominations, list) or not nominations:
        return {}
    return nominations[0] if isinstance(nominations[0], dict) else {}


def _qubit_count(payload: dict[str, Any]) -> int | None:
    raw_info = ((payload.get("probe") or {}).get("raw_info_json") or {})
    value = raw_info.get("qubit_count")
    if isinstance(value, int):
        return value
    target = ((payload.get("execution_run") or {}).get("failure_detail_json") or {}).get("execution_target") or {}
    bitstring = target.get("bitstring")
    if isinstance(bitstring, str) and bitstring:
        return len(bitstring)
    return None


def _tiny_workload_warning(payload: dict[str, Any], profile: dict[str, Any] | None) -> bool:
    derived = (profile or {}).get("derived_signals_json") or {}
    if derived.get("tiny_workload_overhead_dominated") is True:
        return True
    qubits = _qubit_count(payload)
    if qubits is not None and qubits <= 3:
        return True
    run = payload.get("execution_run") or {}
    wall_s = _safe_float(run.get("wall_s"))
    steady_iter_ms = _safe_float(run.get("steady_iter_ms"))
    if wall_s is not None and steady_iter_ms is not None and wall_s < 0.05 and steady_iter_ms < 1.0:
        return True
    return False


def _interpretation_class(payload: dict[str, Any], profile: dict[str, Any] | None, arch_payload: dict[str, Any] | None, tiny: bool) -> str:
    nomination = _first_nomination(arch_payload)
    if nomination.get("nomination_source") == "real_profiler_analysis":
        return "real_arch_nomination"

    system_manifest = payload.get("system_manifest") or {}
    system_name = str(system_manifest.get("system_name") or payload.get("system_name") or "").lower()
    if system_name.startswith("gcp_") and (profile or payload.get("execution_run", {}).get("execution_source")):
        return "portability_validation"

    if tiny:
        return "tiny_workload_overhead_dominated"

    run = payload.get("execution_run") or {}
    if run.get("status") == "success" and run.get("execution_source") not in {None, "synthetic"}:
        return "performance_only"

    return "synthetic_fallback"


def _index_profiles(evidence_dir: Path) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for path in sorted(evidence_dir.glob("*.profile_summary.json")):
        payload = _load_json(path)
        run_id = payload.get("run_id")
        if run_id:
            profiles[str(run_id)] = payload
    return profiles


def _index_arch_outputs(evidence_dir: Path) -> dict[str, dict[str, Any]]:
    arches: dict[str, dict[str, Any]] = {}
    for path in sorted(evidence_dir.glob("*.arch.json")):
        payload = _load_json(path)
        run_id = payload.get("source_run_id")
        if not run_id:
            nomination = _first_nomination(payload)
            run_id = nomination.get("run_id")
        if run_id:
            arches[str(run_id)] = payload
    return arches


def _execution_paths(evidence_dir: Path) -> list[Path]:
    candidates = list(evidence_dir.glob("*.execution.json"))
    candidates.extend(evidence_dir.glob("*.execute.*.json"))
    selected: dict[str, tuple[int, Path]] = {}
    for path in sorted(set(candidates)):
        try:
            payload = _load_json(path)
        except Exception:
            continue
        run_id = str((payload.get("execution_run") or {}).get("run_id") or path.name)
        priority = 0 if path.name.endswith(".execution.json") else 1
        current = selected.get(run_id)
        if current is None or priority < current[0]:
            selected[run_id] = (priority, path)
    return [item[1] for item in sorted(selected.values(), key=lambda item: item[1].name)]


def build_evidence_catalog(evidence_dir: str | Path) -> list[dict[str, Any]]:
    evidence_path = Path(evidence_dir)
    profiles = _index_profiles(evidence_path)
    arches = _index_arch_outputs(evidence_path)
    rows: list[dict[str, Any]] = []

    for path in _execution_paths(evidence_path):
        payload = _load_json(path)
        run = payload.get("execution_run") or {}
        run_id = str(run.get("run_id") or "")
        if not run_id:
            continue
        selected_plan = payload.get("selected_plan") or {}
        system_manifest = payload.get("system_manifest") or {}
        profile = profiles.get(run_id) or payload.get("profile_summary") or None
        arch_payload = arches.get(run_id)
        nomination = _first_nomination(arch_payload)
        taxonomy = summarize_kernel_families((profile or {}).get("top_kernels_json") or [], occupancy_pct=(profile or {}).get("occupancy_pct"))
        tiny = _tiny_workload_warning(payload, profile)

        rows.append(
            {
                "run_id": run_id,
                "system_name": system_manifest.get("system_name") or payload.get("system_name"),
                "gpu_model": system_manifest.get("gpu_model"),
                "workload_id": run.get("workload_id") or payload.get("workload_id"),
                "execution_source": run.get("execution_source"),
                "profiler_kind": (profile or {}).get("profiler_kind"),
                "predicted_ttfr_s": _safe_float(selected_plan.get("predicted_ttfr_s")),
                "actual_ttfr_s": _safe_float(run.get("ttfr_s")),
                "ttfr_error_ratio": _safe_ratio(run.get("ttfr_s"), selected_plan.get("predicted_ttfr_s")),
                "predicted_iter_ms": _safe_float(selected_plan.get("predicted_iter_ms")),
                "actual_iter_ms": _safe_float(run.get("steady_iter_ms")),
                "iter_error_ratio": _safe_ratio(run.get("steady_iter_ms"), selected_plan.get("predicted_iter_ms")),
                "bottleneck_family": nomination.get("bottleneck_family"),
                "nomination_source": nomination.get("nomination_source"),
                "kernel_family_counts_json": json.dumps(taxonomy["kernel_family_counts"], sort_keys=True),
                "interpretation_class": _interpretation_class(payload, profile, arch_payload, tiny),
                "tiny_workload_warning": tiny,
            }
        )

    return rows


def write_catalog_csv(rows: list[dict[str, Any]], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CATALOG_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in CATALOG_COLUMNS})


def write_catalog_markdown(rows: list[dict[str, Any]], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Public Evidence Catalog",
        "",
        "Generated from tracked curated evidence. GCP A100 remains pending until confirmed A100 artifacts are pinned.",
        "",
        "| Run | System | Profiler | TTFR Ratio | Iter Ratio | Nomination | Class | Tiny |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {run_id} | {system_name} | {profiler_kind} | {ttfr} | {itr} | {bottleneck} | {klass} | {tiny} |".format(
                run_id=row.get("run_id") or "",
                system_name=row.get("system_name") or "",
                profiler_kind=row.get("profiler_kind") or "",
                ttfr="" if row.get("ttfr_error_ratio") is None else row["ttfr_error_ratio"],
                itr="" if row.get("iter_error_ratio") is None else row["iter_error_ratio"],
                bottleneck=row.get("bottleneck_family") or "",
                klass=row.get("interpretation_class") or "",
                tiny=str(bool(row.get("tiny_workload_warning"))).lower(),
            )
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = [
    "CATALOG_COLUMNS",
    "build_evidence_catalog",
    "write_catalog_csv",
    "write_catalog_markdown",
]
