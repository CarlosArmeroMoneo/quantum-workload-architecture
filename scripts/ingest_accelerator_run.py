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

from aqs.calibration import annotate_calibration_record  # noqa: E402
from aqs.manifest import load_yaml  # noqa: E402


REAL_EXECUTION_SOURCE = "cuquantum_tensornet_gpu"
REAL_PROFILE_SOURCES = {"real_ncu_profile", "real_nsys_profile"}


def _resolve(path: str | None) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def _repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _load_json(path: Path | None) -> tuple[dict[str, Any] | None, str | None]:
    if path is None:
        return None, "path not provided"
    if not path.exists():
        return None, f"path does not exist: {_repo_path(path)}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "expected JSON object"
    return payload, None


def _discover(artifact_dir: Path | None, suffix: str) -> Path | None:
    if artifact_dir is None or not artifact_dir.exists():
        return None
    matches = sorted(path for path in artifact_dir.glob(f"*{suffix}") if path.is_file())
    return matches[0] if matches else None


def _execution_run(execution: dict[str, Any] | None) -> dict[str, Any]:
    if not execution:
        return {}
    run = execution.get("execution_run")
    return run if isinstance(run, dict) else execution


def _accuracy_status(execution: dict[str, Any] | None) -> str | None:
    if not execution:
        return None
    accuracy = execution.get("accuracy_eval")
    if isinstance(accuracy, dict):
        value = accuracy.get("status")
        return str(value) if value is not None else None
    return None


def _execution_system(execution: dict[str, Any] | None) -> dict[str, Any]:
    if not execution:
        return {}
    system = execution.get("system_manifest")
    return system if isinstance(system, dict) else {}


def _profile_source(profile: dict[str, Any] | None) -> str | None:
    if not profile:
        return None
    derived = profile.get("derived_signals_json")
    if isinstance(derived, dict) and isinstance(derived.get("profile_source"), str):
        return derived["profile_source"]
    if isinstance(profile.get("profile_source"), str):
        return str(profile["profile_source"])
    kind = profile.get("profiler_kind")
    if kind == "ncu":
        return "real_ncu_profile"
    if kind == "nsys":
        return "real_nsys_profile"
    return None


def _profile_is_sparse(profile: dict[str, Any] | None) -> bool:
    if not profile:
        return True
    top_kernels = profile.get("top_kernels_json")
    phase_times = profile.get("nvtx_phase_times_json")
    derived = profile.get("derived_signals_json")
    csv_nonempty = isinstance(derived, dict) and derived.get("csv_nonempty") is True
    return not bool(top_kernels) and not bool(phase_times) and not csv_nonempty


def _first_number(*values: Any) -> float | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _calibration_record(
    *,
    execution: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    system_manifest: dict[str, Any],
    workload_manifest: dict[str, Any],
    workload_path: Path | None,
) -> dict[str, Any]:
    run = _execution_run(execution)
    selected_plan = (execution or {}).get("selected_plan") if execution else {}
    selected_plan = selected_plan if isinstance(selected_plan, dict) else {}
    params = workload_manifest.get("parameters") if isinstance(workload_manifest.get("parameters"), dict) else {}
    derived = profile.get("derived_signals_json") if profile and isinstance(profile.get("derived_signals_json"), dict) else {}

    setup_share = _first_number(derived.get("setup_share_pct"), run.get("setup_share_pct"))
    contract_share = _first_number(derived.get("contract_share_pct"), run.get("contract_share_pct"))
    if setup_share is None:
        phase_times = run.get("failure_detail_json", {}).get("phase_times") if isinstance(run.get("failure_detail_json"), dict) else {}
        if isinstance(phase_times, dict) and phase_times:
            total = sum(float(value) for value in phase_times.values() if isinstance(value, (int, float)))
            contract = sum(float(phase_times.get(key) or 0.0) for key in ("contract_first", "contract_warm", "graph_replay_steady"))
            if total > 0.0:
                contract_share = (contract / total) * 100.0
                setup_share = max(0.0, 100.0 - contract_share)

    n_qubits = params.get("n_qubits")
    if n_qubits is None and "rows" in params and "cols" in params:
        try:
            n_qubits = int(params["rows"]) * int(params["cols"])
        except (TypeError, ValueError):
            n_qubits = None

    record = {
        "run_id": run.get("run_id"),
        "workload_id": (workload_manifest.get("ids") or {}).get("workload_id") or _repo_path(workload_path),
        "host_id": system_manifest.get("system_name"),
        "gpu_model": system_manifest.get("gpu_model"),
        "evidence_tier": "pending/unaccepted",
        "n_qubits": n_qubits,
        "depth": params.get("depth") or params.get("layers") or params.get("steps"),
        "tensor_count": _first_number(derived.get("tensor_count"), run.get("tensor_count"), max(float(n_qubits or 0), 1.0) * 2.0),
        "largest_intermediate": selected_plan.get("largest_intermediate"),
        "num_slices": selected_plan.get("num_slices"),
        "predicted_ttfr_s": selected_plan.get("predicted_ttfr_s"),
        "actual_ttfr_s": run.get("ttfr_s"),
        "predicted_iter_ms": selected_plan.get("predicted_iter_ms"),
        "actual_iter_ms": run.get("steady_iter_ms"),
        "setup_share_pct": setup_share,
        "contract_share_pct": contract_share,
        "profiler_kind": profile.get("profiler_kind") if profile else None,
    }
    return annotate_calibration_record(record)


def classify_ingestion(
    *,
    execution: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    system_manifest: dict[str, Any],
    workload_manifest: dict[str, Any],
    workload_path: Path | None,
    load_errors: dict[str, str | None],
) -> dict[str, Any]:
    reasons: list[str] = []
    pending: list[str] = []
    rejected: list[str] = []

    for name, error in load_errors.items():
        if error:
            if name == "profile_summary":
                pending.append(f"{name}:{error}")
            else:
                rejected.append(f"{name}:{error}")

    run = _execution_run(execution)
    details = run.get("failure_detail_json") if isinstance(run.get("failure_detail_json"), dict) else {}
    source = run.get("execution_source") or details.get("execution_source")
    if source != REAL_EXECUTION_SOURCE:
        rejected.append("execution_source_not_real_cuquantum")
    if run.get("status") != "success":
        rejected.append("execution_status_not_success")
    if _accuracy_status(execution) != "pass":
        rejected.append("accuracy_missing_or_not_pass")

    expected_model = system_manifest.get("gpu_model")
    actual_model = _execution_system(execution).get("gpu_model") if execution else None
    if expected_model and actual_model and expected_model != actual_model:
        rejected.append("system_gpu_model_mismatch")

    profile_source = _profile_source(profile)
    if profile is None:
        pending.append("profile_summary_missing")
    elif profile_source not in REAL_PROFILE_SOURCES:
        pending.append("profile_source_not_confirmed_real")
    elif _profile_is_sparse(profile):
        pending.append("sparse_profile_summary")

    if rejected:
        status = "rejected"
        evidence_tier = "rejected"
    elif pending:
        status = "pending"
        evidence_tier = "pending/unaccepted"
    else:
        status = "accepted"
        evidence_tier = "Tier 2"
        reasons.append("offline_acceptance_passed")

    calibration = _calibration_record(
        execution=execution,
        profile=profile,
        system_manifest=system_manifest,
        workload_manifest=workload_manifest,
        workload_path=workload_path,
    )
    calibration["evidence_tier"] = evidence_tier
    calibration = annotate_calibration_record(calibration)

    return {
        "api_version": "qwa.accelerator_run_record.v1",
        "status": status,
        "evidence_tier": evidence_tier,
        "reason_codes": reasons + pending + rejected,
        "run_id": run.get("run_id"),
        "system_manifest": system_manifest.get("system_name"),
        "workload_manifest": _repo_path(workload_path),
        "profile_source": profile_source,
        "calibration_record": calibration,
    }


def _append_table(path: Path, record: dict[str, Any]) -> None:
    rows: list[Any] = []
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, list):
            rows = loaded
        elif isinstance(loaded, dict) and isinstance(loaded.get("records"), list):
            rows = loaded["records"]
    rows.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a local accelerator artifact set into a normalized offline record")
    parser.add_argument("--artifact-dir", help="Directory containing execution/profile artifacts")
    parser.add_argument("--execution-payload", "--execution", dest="execution_payload", help="Execution payload JSON")
    parser.add_argument("--profile-summary", help="Reduced profile summary JSON")
    parser.add_argument("--system-manifest", required=True, help="System manifest YAML")
    parser.add_argument("--workload-manifest", required=True, help="Workload manifest YAML")
    parser.add_argument("--arch-output", help="Optional architecture output JSON")
    parser.add_argument("--output", help="Write normalized record JSON")
    parser.add_argument("--calibration-table-json", help="Append calibration record to a JSON list")
    args = parser.parse_args()

    artifact_dir = _resolve(args.artifact_dir)
    execution_path = _resolve(args.execution_payload) or _discover(artifact_dir, ".execution.json")
    profile_path = _resolve(args.profile_summary) or _discover(artifact_dir, ".profile_summary.json")
    system_path = _resolve(args.system_manifest)
    workload_path = _resolve(args.workload_manifest)
    assert system_path is not None
    assert workload_path is not None

    system_manifest = load_yaml(system_path)
    workload_manifest = load_yaml(workload_path)
    execution, execution_error = _load_json(execution_path)
    profile, profile_error = _load_json(profile_path)
    record = classify_ingestion(
        execution=execution,
        profile=profile,
        system_manifest=system_manifest,
        workload_manifest=workload_manifest,
        workload_path=workload_path,
        load_errors={"execution": execution_error, "profile_summary": profile_error},
    )
    record["inputs"] = {
        "artifact_dir": _repo_path(artifact_dir),
        "execution_payload": _repo_path(execution_path),
        "profile_summary": _repo_path(profile_path),
        "system_manifest": _repo_path(system_path),
        "workload_manifest": _repo_path(workload_path),
    }

    output = _resolve(args.output)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    table_path = _resolve(args.calibration_table_json)
    if table_path is not None:
        _append_table(table_path, record["calibration_record"])

    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record["status"] == "accepted" else 1 if record["status"] == "pending" else 2


if __name__ == "__main__":
    raise SystemExit(main())
