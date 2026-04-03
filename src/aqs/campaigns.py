from __future__ import annotations

import csv
import json
import shutil
from copy import deepcopy
from itertools import product
from pathlib import Path
from typing import Any

from .campaign_metrics import build_campaign_metrics
from .db import (
    apply_schema,
    insert_accuracy_eval,
    insert_campaign_cell,
    insert_campaign_profile,
    insert_campaign_registry,
    insert_campaign_run,
    insert_execution_run,
    insert_feature_snapshot,
    insert_plan_candidate,
    insert_probe_observation,
    insert_profile_summary,
    insert_system_profile,
    insert_workload_and_ir,
)
from .doctor import collect_system_profile
from .execution import ExecutionConfig, execute_plan_candidate_bundle
from .features import extract_feature_snapshot
from .io import dump_json
from .manifest import finalize_workload_manifest, load_yaml, validate_manifest, validate_workload_manifest
from .normalize import normalize_workload_manifest
from .paths import repo_root
from .planner import PlanConfig, generate_plan_candidates, load_system_manifest, select_top_plan
from .repo_metadata import capture_repo_metadata
from .tnprobe import ProbeConfig, run_exact_tn_probe
from .utils import canonical_json, sha256_text


CAMPAIGN_RUNNER_VERSION = "aqs.campaign_runner.v1"


class CampaignError(RuntimeError):
    pass


def _resolve_repo_path(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return repo_root() / path


def _load_campaign_manifest(path: str | Path) -> tuple[Path, dict[str, Any]]:
    manifest_path = Path(path)
    manifest = load_yaml(manifest_path)
    errors = validate_manifest(manifest)
    if errors:
        raise CampaignError(f"Invalid campaign manifest {manifest_path}: {errors}")
    return manifest_path, manifest


def _campaign_id(manifest_path: Path, manifest: dict[str, Any]) -> str:
    return "camp_" + sha256_text(
        canonical_json(
            {
                "manifest_path": str(manifest_path).replace("\\", "/"),
                "campaign_name": manifest["campaign_name"],
                "matrix": manifest["matrix"],
                "workloads": manifest["workloads"],
                "runner_version": CAMPAIGN_RUNNER_VERSION,
            }
        )
    )[:16]


def _expand_matrix(matrix: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = sorted(matrix.keys())
    values = [matrix[key] for key in keys]
    return [dict(zip(keys, combo)) for combo in product(*values)] if keys else [{}]


def _stable_plan_id(workload_id: str, plan: dict[str, Any]) -> str:
    return "plan_" + sha256_text(
        canonical_json(
            {
                "workload_id": workload_id,
                "plan": plan,
                "runner_version": CAMPAIGN_RUNNER_VERSION,
            }
        )
    )[:16]


def _materialize_workload_manifest(base_manifest: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    manifest = deepcopy(base_manifest)
    if "repeat_count_hint" in params:
        manifest["repeat_count_hint"] = int(params["repeat_count_hint"])
        manifest = finalize_workload_manifest(manifest)
    return manifest


def _load_plan_from_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(_resolve_repo_path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        if isinstance(payload.get("selected_plan"), dict):
            return dict(payload["selected_plan"])
        if isinstance(payload.get("plan"), dict):
            return dict(payload["plan"])
        return dict(payload)
    raise CampaignError(f"Plan JSON at {path} must decode to a mapping")


def _resolve_policy_overrides(plan_source: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    policy_path = plan_source.get("policy_path")
    if policy_path:
        payload = load_yaml(_resolve_repo_path(policy_path))
        if not isinstance(payload, dict):
            raise CampaignError(f"Planner policy payload at {policy_path} must be a mapping")
        merged.update({key: value for key, value in payload.items() if key != "policy_version"})
    inline = plan_source.get("policy_overrides")
    if inline is not None:
        if not isinstance(inline, dict):
            raise CampaignError("plan_source.policy_overrides must be a mapping when provided")
        merged.update(inline)
    return merged


def _materialize_plan(
    campaign: dict[str, Any],
    workload_manifest: dict[str, Any],
    features: dict[str, Any],
    probe: dict[str, Any],
    system_manifest: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    base_plan: dict[str, Any]
    if campaign["plan_source"]["kind"] == "planner_templates":
        candidates = generate_plan_candidates(
            workload_manifest,
            features,
            probe,
            system_manifest,
            config=PlanConfig(
                objective=str(campaign["objective"]),
                planner_budget=str(params.get("planner_budget") or "balanced"),
                allow_distributed=bool(params.get("allow_distributed", False)),
                max_candidates=params.get("max_candidates"),
                policy_overrides=dict(campaign.get("planner_policy") or {}),
            ),
        )
        base_plan = select_top_plan(candidates, objective=str(campaign["objective"])) or (candidates[0] if candidates else {})
        if not base_plan:
            raise CampaignError(f"Planner did not materialize a plan for workload {workload_manifest['ids']['workload_id']}")
        base_plan = dict(base_plan)
    else:
        base_plan = _load_plan_from_json(params["plan_json"]) if params.get("plan_json") else {}

    plan = dict(base_plan)
    for key in ("mode", "precision", "workspace_gb", "cache_workspace_gb", "hyper_samples", "autotune", "reuse_cache", "mpi_ranks"):
        if key in params:
            plan[key] = params[key]
    plan.setdefault("project", "tnep")
    plan.setdefault("planner_version", "aqs.campaign_materialized.v1")
    plan.setdefault("objective", campaign["objective"])
    plan.setdefault("mode", "exact_tn")
    plan.setdefault("precision", "complex128")
    plan.setdefault("feasibility_label", "feasible")
    plan.setdefault("explanation_json", [])
    plan["explanation_json"] = list(plan.get("explanation_json") or []) + [
        {
            "kind": "campaign_cell",
            "campaign_name": campaign["campaign_name"],
            "parameters": params,
        }
    ]
    plan["plan_id"] = _stable_plan_id(workload_manifest["ids"]["workload_id"], plan)
    return plan


def enumerate_campaign_cells(campaign_manifest_path: str | Path) -> dict[str, Any]:
    manifest_path, campaign = _load_campaign_manifest(campaign_manifest_path)
    campaign_id = _campaign_id(manifest_path, campaign)
    system_manifest = load_system_manifest(str(_resolve_repo_path(campaign["system_manifest"])))
    repo_metadata = capture_repo_metadata()
    cells: list[dict[str, Any]] = []

    for workload_entry in campaign["workloads"]:
        workload_path = _resolve_repo_path(workload_entry)
        workload_manifest = load_yaml(workload_path)
        errors = validate_workload_manifest(workload_manifest)
        if errors:
            raise CampaignError(f"Invalid workload manifest {workload_path}: {errors}")
        for params in _expand_matrix(campaign["matrix"]):
            manifest_for_cell = _materialize_workload_manifest(workload_manifest, params)
            ir = normalize_workload_manifest(manifest_for_cell)
            features = extract_feature_snapshot(manifest_for_cell, ir)
            probe = run_exact_tn_probe(
                manifest_for_cell,
                ProbeConfig(
                    objective=str(campaign["objective"]),
                    probe_strategy=str(campaign.get("probe_strategy") or "surrogate_only"),
                ),
            )
            plan = _materialize_plan(campaign, manifest_for_cell, features, probe, system_manifest, params)
            cell_id = "cell_" + sha256_text(
                canonical_json(
                    {
                        "campaign_id": campaign_id,
                        "workload_id": manifest_for_cell["ids"]["workload_id"],
                        "params": params,
                        "plan_id": plan["plan_id"],
                    }
                )
            )[:16]
            cells.append(
                {
                    "campaign_id": campaign_id,
                    "campaign_name": campaign["campaign_name"],
                    "cell_id": cell_id,
                    "manifest_path": str(workload_path).replace("\\", "/"),
                    "workload_id": manifest_for_cell["ids"]["workload_id"],
                    "parameter_json": params,
                    "plan_json": plan,
                    "probe": probe,
                    "normalized_ir": ir,
                    "feature_snapshot": features,
                    "replicate_count": int(campaign["replicates"]),
                    "measurement_repeats": int(params.get("measurement_repeats", 3)),
                }
            )

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign["campaign_name"],
        "api_version": campaign["api_version"],
        "manifest_path": str(manifest_path).replace("\\", "/"),
        "system_manifest": str(_resolve_repo_path(campaign["system_manifest"])).replace("\\", "/"),
        "outdir": str(_resolve_repo_path(campaign["outdir"])).replace("\\", "/"),
        "objective": campaign["objective"],
        "execution_intent": campaign["execution_intent"],
        "probe_strategy": campaign["probe_strategy"],
        "planner_policy": _resolve_policy_overrides(campaign["plan_source"]),
        "profile_policy": campaign.get("profile_policy") or {},
        "repo_metadata": repo_metadata,
        "cells": cells,
    }


def _effective_outdir(preview: dict[str, Any], outdir: str | Path | None = None) -> Path:
    if outdir is not None:
        return Path(outdir)
    return Path(preview["outdir"])


def _reset_campaign_outdir(outdir: Path) -> None:
    for directory in ("cells", "runs", "plots"):
        target = outdir / directory
        if target.exists():
            shutil.rmtree(target)
    for filename in ("summary.json", "results.csv", "report.md"):
        target = outdir / filename
        if target.exists():
            target.unlink()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _svg_bar_chart(path: Path, title: str, rows: list[tuple[str, float]]) -> None:
    width = 960
    height = 360
    margin_left = 220
    margin_top = 50
    chart_width = width - margin_left - 40
    bar_height = 24
    gap = 12
    max_value = max((value for _, value in rows), default=1.0) or 1.0
    content = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Consolas,Menlo,monospace;font-size:12px;fill:#1f2933}.title{font-size:16px;font-weight:bold}.bar{fill:#2563eb}.label{fill:#334155}</style>',
        f'<text x="24" y="28" class="title">{title}</text>',
    ]
    for idx, (label, value) in enumerate(rows[:8]):
        y = margin_top + idx * (bar_height + gap)
        bar_width = 0 if max_value <= 0 else chart_width * (value / max_value)
        content.append(f'<text x="24" y="{y + 16}" class="label">{label}</text>')
        content.append(f'<rect x="{margin_left}" y="{y}" width="{bar_width:.2f}" height="{bar_height}" rx="4" class="bar"/>')
        content.append(f'<text x="{margin_left + bar_width + 8:.2f}" y="{y + 16}">{value:.6f}</text>')
    content.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(content), encoding="utf-8")


def _status_plot(path: Path, counts: dict[str, int]) -> None:
    rows = [(status, float(count)) for status, count in sorted(counts.items())]
    _svg_bar_chart(path, "Run Status Counts", rows)


def _repeat_roi_break_even_plot(path: Path, findings: list[dict[str, Any]]) -> None:
    rows = [
        (finding["cell_id"], float(finding["break_even_extra_repeats"]))
        for finding in findings
        if finding.get("break_even_extra_repeats") is not None and finding.get("roi_label") == "positive"
    ]
    _svg_bar_chart(path, "Repeat ROI Break-Even (Extra Repeats)", rows or [("no_positive_roi", 0.0)])


def _profile_recommendations(rows: list[dict[str, Any]], profile_policy: dict[str, Any]) -> dict[str, list[str]]:
    successful = [row for row in rows if row["status"] == "success"]
    by_cell: dict[str, dict[str, Any]] = {}
    for row in successful:
        existing = by_cell.get(row["cell_id"])
        if existing is None or (row.get("ttfr_s") or float("inf")) < (existing.get("ttfr_s") or float("inf")):
            by_cell[row["cell_id"]] = row
    representative_rows = list(by_cell.values())
    recommendations: dict[str, list[str]] = {}
    for profiler_kind in ("nsys", "ncu"):
        policy = str(profile_policy.get(profiler_kind) or "never")
        if policy == "never" or not representative_rows:
            recommendations[profiler_kind] = []
            continue
        if policy == "all":
            recommendations[profiler_kind] = sorted(by_cell.keys())
            continue
        chosen: list[str] = []
        fastest = min(representative_rows, key=lambda row: row.get("ttfr_s") or float("inf"))
        slowest = max(representative_rows, key=lambda row: row.get("ttfr_s") or 0.0)
        highest_repeat = max(representative_rows, key=lambda row: row["repeat_count_hint"])
        for candidate in (fastest, slowest, highest_repeat):
            if candidate["cell_id"] not in chosen:
                chosen.append(candidate["cell_id"])
        seen_workloads: set[str] = set()
        for row in sorted(representative_rows, key=lambda item: (item["workload_id"], item["cell_id"])):
            if row["workload_id"] in seen_workloads:
                continue
            seen_workloads.add(row["workload_id"])
            if row["cell_id"] not in chosen:
                chosen.append(row["cell_id"])
        recommendations[profiler_kind] = chosen
    return recommendations


def _summarize_outputs(preview: dict[str, Any], outdir: Path) -> dict[str, Any]:
    cell_specs: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []

    expected_cells = sorted(preview["cells"], key=lambda item: item["cell_id"])
    for preview_cell in expected_cells:
        cell_file = outdir / "cells" / f"{preview_cell['cell_id']}.json"
        if not cell_file.exists():
            raise CampaignError(f"Missing campaign cell artifact {cell_file}")
        cell = json.loads(cell_file.read_text(encoding="utf-8"))
        cell_specs.append(cell)
    for cell in cell_specs:
        run_dir = outdir / "runs" / cell["cell_id"]
        for run_file in sorted(run_dir.glob("replicate_*.execution.json")):
            payload = json.loads(run_file.read_text(encoding="utf-8"))
            run = payload["execution_run"]
            params = cell["parameter_json"]
            profile = payload.get("profile_summary") or {}
            derived = profile.get("derived_signals_json") or {}
            run_rows.append(
                {
                    "campaign_id": cell["campaign_id"],
                    "campaign_name": cell["campaign_name"],
                    "cell_id": cell["cell_id"],
                    "manifest_path": cell["manifest_path"],
                    "workload_id": cell["workload_id"],
                    "plan_id": cell["plan_json"]["plan_id"],
                    "run_id": run["run_id"],
                    "replicate_idx": run["replicate_idx"],
                    "status": run["status"],
                    "planner_budget": params.get("planner_budget"),
                    "repeat_count_hint": int(params.get("repeat_count_hint", 1)),
                    "measurement_repeats": int(params.get("measurement_repeats", 3)),
                    "autotune": params.get("autotune"),
                    "reuse_cache": params.get("reuse_cache"),
                    "execution_source": run.get("execution_source"),
                    "ttfr_s": run.get("ttfr_s"),
                    "steady_iter_ms": run.get("steady_iter_ms"),
                    "wall_s": run.get("wall_s"),
                    "gpu_seconds": run.get("gpu_seconds"),
                    "predicted_ttfr_s": cell["plan_json"].get("predicted_ttfr_s"),
                    "predicted_iter_ms": cell["plan_json"].get("predicted_iter_ms"),
                    "predicted_gpu_seconds": cell["plan_json"].get("predicted_gpu_seconds"),
                    "planner_share_pct": derived.get("planner_share_pct"),
                    "launch_share_pct": derived.get("launch_share_pct"),
                    "contract_share_pct": derived.get("contract_share_pct"),
                }
            )

    status_counts: dict[str, int] = {}
    for row in run_rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    profile_recommendations = _profile_recommendations(run_rows, preview.get("profile_policy") or {})
    for row in run_rows:
        row["profile_candidate_nsys"] = row["cell_id"] in set(profile_recommendations.get("nsys", []))
        row["profile_candidate_ncu"] = row["cell_id"] in set(profile_recommendations.get("ncu", []))

    ttfr_by_cell: list[tuple[str, float]] = []
    seen_cells: dict[str, list[float]] = {}
    for row in run_rows:
        if row["ttfr_s"] is None:
            continue
        seen_cells.setdefault(row["cell_id"], []).append(float(row["ttfr_s"]))
    for cell_id, values in sorted(seen_cells.items()):
        ttfr_by_cell.append((cell_id, sum(values) / len(values)))
    metrics = build_campaign_metrics(cell_specs, run_rows)

    summary = {
        "campaign_id": preview["campaign_id"],
        "campaign_name": preview["campaign_name"],
        "api_version": preview["api_version"],
        "campaign_manifest": preview["manifest_path"],
        "runner_version": CAMPAIGN_RUNNER_VERSION,
        "objective": preview["objective"],
        "execution_intent": preview["execution_intent"],
        "probe_strategy": preview["probe_strategy"],
        "planner_policy": preview.get("planner_policy") or {},
        "system_manifest": preview["system_manifest"],
        "outdir": str(outdir).replace("\\", "/"),
        "repo_metadata": preview["repo_metadata"],
        "cell_count": len(cell_specs),
        "run_count": len(run_rows),
        "status_counts": status_counts,
        "profile_recommendations": profile_recommendations,
        "cells": cell_specs,
        **metrics,
    }
    dump_json(summary, outdir / "summary.json")
    _write_csv(outdir / "results.csv", run_rows)
    _svg_bar_chart(outdir / "plots" / "ttfr_by_cell.svg", "Average TTFR by Cell", ttfr_by_cell or [("no_successful_runs", 0.0)])
    _status_plot(outdir / "plots" / "status_counts.svg", status_counts or {"no_runs": 0})
    _repeat_roi_break_even_plot(outdir / "plots" / "repeat_roi_break_even.svg", summary["repeat_roi"]["findings"])

    report_lines = [
        f"# Campaign Report: {preview['campaign_name']}",
        "",
        f"- Campaign ID: `{preview['campaign_id']}`",
        f"- Objective: `{preview['objective']}`",
        f"- Cell count: `{len(cell_specs)}`",
        f"- Run count: `{len(run_rows)}`",
        f"- Status counts: `{status_counts}`",
        f"- Planner policy hooks: `{preview.get('planner_policy') or {}}`",
        f"- Recommended `nsys` follow-up cells: `{profile_recommendations.get('nsys', [])}`",
        f"- Recommended `ncu` follow-up cells: `{profile_recommendations.get('ncu', [])}`",
        "",
        "## Workloads",
        "",
    ]
    for cell in cell_specs[:12]:
        report_lines.append(
            f"- `{cell['cell_id']}`: workload `{cell['workload_id']}`, params `{cell['parameter_json']}`, plan `{cell['plan_json']['plan_id']}`"
        )
    report_lines.extend(
        [
            "",
            "## Repeat ROI Foundation",
            "",
            "- This report is a structural/local dry run unless the execution source is the real cuTensorNet GPU backend.",
            f"- Dry-run only: `{summary['repeat_roi']['dry_run_only']}`",
            f"- Suggested planner policy overrides: `{summary['repeat_roi']['suggested_policy_overrides']}`",
            "",
            "### Top Findings",
            "",
        ]
    )
    for finding in summary["repeat_roi"]["findings"][:12]:
        report_lines.append(
            "- "
            + (
                f"`{finding['cell_id']}` repeat={finding['repeat_count_hint']} autotune={finding['autotune']} "
                f"reuse_cache={finding['reuse_cache']} roi={finding['roi_label']} "
                f"break_even_extra_repeats={finding['break_even_extra_repeats']}"
            )
        )
    (outdir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return summary


def validate_campaign(campaign_manifest_path: str | Path) -> dict[str, Any]:
    preview = enumerate_campaign_cells(campaign_manifest_path)
    return {
        "campaign_id": preview["campaign_id"],
        "campaign_name": preview["campaign_name"],
        "cell_count": len(preview["cells"]),
        "cell_ids": [cell["cell_id"] for cell in preview["cells"]],
        "manifest_path": preview["manifest_path"],
    }


def run_campaign_manifest(
    campaign_manifest_path: str | Path,
    *,
    db_path: str | Path | None = None,
    outdir: str | Path | None = None,
) -> dict[str, Any]:
    preview = enumerate_campaign_cells(campaign_manifest_path)
    outdir_path = _effective_outdir(preview, outdir=outdir)
    outdir_path.mkdir(parents=True, exist_ok=True)
    _reset_campaign_outdir(outdir_path)
    system_profile = collect_system_profile()
    if db_path and not Path(db_path).exists():
        apply_schema(db_path)
    if db_path:
        insert_system_profile(db_path, system_profile)
    insert_campaign_registry(
        db_path,
        {
            "campaign_id": preview["campaign_id"],
            "campaign_name": preview["campaign_name"],
            "api_version": preview["api_version"],
            "manifest_path": preview["manifest_path"],
            "objective": preview["objective"],
            "system_manifest": preview["system_manifest"],
            "outdir": str(outdir_path).replace("\\", "/"),
            "repo_metadata": preview["repo_metadata"],
            "summary_json": None,
        },
    ) if db_path else None

    system_manifest = load_system_manifest(preview["system_manifest"])
    for cell in preview["cells"]:
        cell_payload = {
            "campaign_id": preview["campaign_id"],
            "campaign_name": preview["campaign_name"],
            "cell_id": cell["cell_id"],
            "manifest_path": cell["manifest_path"],
            "workload_id": cell["workload_id"],
            "parameter_json": cell["parameter_json"],
            "plan_json": cell["plan_json"],
            "replicate_count": cell["replicate_count"],
        }
        dump_json(cell_payload, outdir_path / "cells" / f"{cell['cell_id']}.json")
        if db_path:
            insert_campaign_cell(db_path, cell_payload)
            manifest = load_yaml(cell["manifest_path"])
            materialized_manifest = _materialize_workload_manifest(manifest, cell["parameter_json"])
            insert_workload_and_ir(db_path, materialized_manifest, cell["normalized_ir"])
            insert_feature_snapshot(db_path, cell["feature_snapshot"])
            insert_probe_observation(db_path, materialized_manifest["ids"]["workload_id"], system_profile["system_id"], cell["probe"], project="tnep")
            insert_plan_candidate(db_path, materialized_manifest["ids"]["workload_id"], cell["plan_json"])

        base_manifest = load_yaml(cell["manifest_path"])
        manifest_for_cell = _materialize_workload_manifest(base_manifest, cell["parameter_json"])
        for replicate_idx in range(cell["replicate_count"]):
            bundle = execute_plan_candidate_bundle(
                manifest_for_cell,
                cell["plan_json"],
                system_profile=system_profile,
                system_manifest=system_manifest,
                probe=cell["probe"],
                config=ExecutionConfig(
                    objective=str(preview["objective"]),
                    precision=str(cell["plan_json"].get("precision") or "complex128"),
                    probe_strategy=str(preview["probe_strategy"]),
                    measurement_repeats=cell["measurement_repeats"],
                    execution_intent=str(preview["execution_intent"]),
                    replicate_idx=replicate_idx,
                ),
            )
            payload = {
                "campaign_id": preview["campaign_id"],
                "campaign_name": preview["campaign_name"],
                "campaign_cell_id": cell["cell_id"],
                "campaign_parameters": cell["parameter_json"],
                "repo_metadata": preview["repo_metadata"],
                "selected_plan": cell["plan_json"],
                "probe": cell["probe"],
                "execution_run": bundle["execution_run"],
                "profile_summary": bundle.get("profile_summary"),
                "accuracy_eval": bundle.get("accuracy_eval"),
                "linked_assets": bundle.get("linked_assets", []),
            }
            run_path = outdir_path / "runs" / cell["cell_id"] / f"replicate_{replicate_idx}.execution.json"
            dump_json(payload, run_path)
            if db_path:
                insert_execution_run(db_path, bundle["execution_run"])
                insert_campaign_run(db_path, preview["campaign_id"], cell["cell_id"], bundle["execution_run"])
                accuracy = bundle.get("accuracy_eval") or {}
                for row in accuracy.get("rows", []):
                    insert_accuracy_eval(db_path, row)
                if bundle.get("profile_summary"):
                    insert_profile_summary(db_path, bundle["profile_summary"])
                    insert_campaign_profile(
                        db_path,
                        preview["campaign_id"],
                        cell["cell_id"],
                        bundle["profile_summary"]["profile_id"],
                        bundle["profile_summary"]["profiler_kind"],
                    )
    summary = _summarize_outputs(preview, outdir_path)
    if db_path:
        insert_campaign_registry(
            db_path,
            {
                "campaign_id": preview["campaign_id"],
                "campaign_name": preview["campaign_name"],
                "api_version": preview["api_version"],
                "manifest_path": preview["manifest_path"],
                "objective": preview["objective"],
                "system_manifest": preview["system_manifest"],
                "outdir": str(outdir_path).replace("\\", "/"),
                "repo_metadata": preview["repo_metadata"],
                "summary_json": summary,
            },
        )
    return summary


def summarize_campaign_manifest(
    campaign_manifest_path: str | Path,
    *,
    outdir: str | Path | None = None,
) -> dict[str, Any]:
    preview = enumerate_campaign_cells(campaign_manifest_path)
    outdir_path = _effective_outdir(preview, outdir=outdir)
    if not (outdir_path / "cells").exists():
        raise CampaignError(f"No campaign cell artifacts found under {outdir_path}")
    return _summarize_outputs(preview, outdir_path)


__all__ = [
    "CAMPAIGN_RUNNER_VERSION",
    "CampaignError",
    "enumerate_campaign_cells",
    "run_campaign_manifest",
    "summarize_campaign_manifest",
    "validate_campaign",
]
