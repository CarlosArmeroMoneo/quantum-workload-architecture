from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aqs.manifest import load_yaml  # noqa: E402


DEFAULT_GATE = "configs/profiling/gcp_a100_acceptance_gate.yaml"
ACCEPTED = "accepted"
PENDING = "pending"
REJECTED = "rejected"
PATH_KEYS = ("path", "uri", "url", "asset")


def _repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def _load_json(path: Path | None) -> tuple[dict[str, Any] | None, str | None]:
    if path is None:
        return None, "path not provided"
    if not path.exists():
        return None, f"path does not exist: {_repo_path(path)}"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in {_repo_path(path)}: {exc}"
    if not isinstance(loaded, dict):
        return None, f"expected JSON object in {_repo_path(path)}"
    return loaded, None


def _walk(obj: Any, prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            rows.append((path, value))
            rows.extend(_walk(value, path))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            path = f"{prefix}[{index}]"
            rows.append((path, value))
            rows.extend(_walk(value, path))
    return rows


def _values_for_key(obj: Any, key: str) -> list[Any]:
    return [value for path, value in _walk(obj) if path.split(".")[-1].split("[")[0] == key]


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _execution_run(execution: dict[str, Any] | None) -> dict[str, Any]:
    if not execution:
        return {}
    nested = execution.get("execution_run")
    if isinstance(nested, dict):
        return nested
    return execution


def _failure_details(run: dict[str, Any]) -> dict[str, Any]:
    details = run.get("failure_detail_json")
    return details if isinstance(details, dict) else {}


def _profile_source(profile: dict[str, Any] | None) -> str | None:
    if not profile:
        return None
    derived = profile.get("derived_signals_json")
    if isinstance(derived, dict):
        source = _first_text(derived.get("profile_source"))
        if source:
            return source
    return _first_text(profile.get("profile_source"))


def _artifact_path_values(artifact_manifest: dict[str, Any] | None) -> list[tuple[str, str]]:
    if not artifact_manifest:
        return []
    paths: list[tuple[str, str]] = []
    for key_path, value in _walk(artifact_manifest):
        leaf = key_path.split(".")[-1].split("[")[0].lower()
        if isinstance(value, str) and any(marker in leaf for marker in PATH_KEYS):
            if value.strip():
                paths.append((key_path, value.strip()))
    return paths


def _contains_wildcard(value: str, wildcards: list[str]) -> bool:
    return any(marker in value for marker in wildcards)


def _candidate_files(evidence_dir: Path, pattern: str) -> list[Path]:
    return sorted(path for path in evidence_dir.glob(pattern) if path.is_file())


def _run_id_from_execution(path: Path) -> str:
    payload, _ = _load_json(path)
    return str(_execution_run(payload).get("run_id") or "")


def _run_id_from_profile(path: Path) -> str:
    payload, _ = _load_json(path)
    return str((payload or {}).get("run_id") or "")


def _resolve_evidence_dir(evidence_dir: Path) -> dict[str, Path | None]:
    executions = _candidate_files(evidence_dir, "*.execution.json")
    if not executions:
        executions = _candidate_files(evidence_dir, "*.execute.*.json")
    execution = executions[0] if executions else None
    run_id = _run_id_from_execution(execution) if execution else ""

    profile = None
    profiles = _candidate_files(evidence_dir, "*.profile_summary.json")
    if run_id:
        for candidate in profiles:
            if _run_id_from_profile(candidate) == run_id:
                profile = candidate
                break
    if profile is None and profiles:
        profile = profiles[0]

    manifests = [
        path
        for path in sorted(evidence_dir.glob("*.json"))
        if path.is_file()
        and not path.name.endswith(".execution.json")
        and ".execute." not in path.name
        and not path.name.endswith(".profile_summary.json")
    ]
    artifact_manifest = None
    for candidate in manifests:
        lowered = candidate.name.lower()
        if "artifact" in lowered or "manifest" in lowered:
            artifact_manifest = candidate
            break
    if artifact_manifest is None and manifests:
        artifact_manifest = manifests[0]

    return {
        "execution": execution,
        "profile_summary": profile,
        "artifact_manifest": artifact_manifest,
    }


def _csv_has_kernel_rows(path: Path) -> bool | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                return False
            for row in reader:
                kernel = row.get("Kernel Name") or row.get("Name") or row.get("kernel_name")
                if kernel and kernel.strip():
                    return True
    except OSError:
        return None
    return False


def _resolve_profile_artifact_path(raw_path: Any, profile_path: Path | None, evidence_dir: Path | None) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    roots = [profile_path.parent if profile_path else None, evidence_dir, REPO_ROOT]
    for root in roots:
        if root is None:
            continue
        resolved = (root / candidate).resolve()
        if resolved.exists():
            return resolved
    return (REPO_ROOT / candidate).resolve()


def _gpu_model(execution: dict[str, Any] | None, profile: dict[str, Any] | None) -> str | None:
    return _first_text(
        *(_values_for_key(execution, "gpu_model") if execution else []),
        *(_values_for_key(profile, "gpu_model") if profile else []),
        *(_values_for_key(execution, "device__attribute_display_name") if execution else []),
        *(_values_for_key(profile, "device__attribute_display_name") if profile else []),
    )


def _gpu_arch_target(execution: dict[str, Any] | None, profile: dict[str, Any] | None) -> str | None:
    targets = _gpu_arch_targets(execution, profile)
    return targets[0] if targets else None


def _gpu_arch_targets(execution: dict[str, Any] | None, profile: dict[str, Any] | None) -> list[str]:
    values = [
        *(_values_for_key(execution, "gpu_arch_target") if execution else []),
        *(_values_for_key(profile, "gpu_arch_target") if profile else []),
        *(_values_for_key(execution, "arch_target") if execution else []),
        *(_values_for_key(profile, "arch_target") if profile else []),
    ]
    targets: list[str] = []
    for value in values:
        text = _first_text(value)
        if text and text not in targets:
            targets.append(text)
    return targets


def _gpu_mem_gb(execution: dict[str, Any] | None, profile: dict[str, Any] | None) -> float | None:
    for value in (_values_for_key(execution, "gpu_mem_gb") if execution else []):
        parsed = _as_float(value)
        if parsed is not None:
            return parsed
    for value in (_values_for_key(profile, "gpu_mem_gb") if profile else []):
        parsed = _as_float(value)
        if parsed is not None:
            return parsed
    for value in (_values_for_key(profile, "device__attribute_total_memory") if profile else []):
        parsed = _as_float(value)
        if parsed is not None:
            return parsed / 1_000_000_000.0
    return None


def _qubit_count(*payloads: dict[str, Any] | None) -> int | None:
    for payload in payloads:
        if not payload:
            continue
        for key in ("qubit_count", "n_qubits"):
            for value in _values_for_key(payload, key):
                parsed = _as_float(value)
                if parsed is not None:
                    return int(parsed)
        for value in _values_for_key(payload, "bitstring"):
            if isinstance(value, str) and value:
                return len(value)
    return None


def _has_marker(payload: dict[str, Any] | None, markers: list[str]) -> bool:
    if not payload:
        return False
    lowered_markers = [marker.lower() for marker in markers]
    for _, value in _walk(payload):
        if isinstance(value, str):
            lowered = value.lower()
            if any(marker in lowered for marker in lowered_markers):
                return True
    return False


def _throughput_benchmark_true(*payloads: dict[str, Any] | None) -> bool:
    for payload in payloads:
        if not payload:
            continue
        for value in _values_for_key(payload, "throughput_benchmark"):
            if value is True:
                return True
    return False


def _check(name: str, status: str, message: str) -> dict[str, str]:
    return {"name": name, "status": status, "message": message}


def validate_candidate(
    *,
    gate: dict[str, Any],
    execution: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    artifact_manifest: dict[str, Any] | None,
    profile_path: Path | None = None,
    evidence_dir: Path | None = None,
    load_errors: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    load_errors = load_errors or {}
    checks: list[dict[str, str]] = []
    expected_device = gate.get("expected_device") or {}
    required_execution = gate.get("required_execution") or {}
    required_accuracy = gate.get("required_accuracy") or {}
    accepted_profile_sources = set(gate.get("accepted_profile_sources") or [])
    artifact_rules = gate.get("artifact_manifest") or {}
    interpretation_rules = gate.get("interpretation") or {}
    tiny_policy = gate.get("tiny_workload_policy") or {}

    for input_name in ("execution", "profile_summary", "artifact_manifest"):
        error = load_errors.get(input_name)
        if error:
            status = PENDING if "not provided" in error or "does not exist" in error else REJECTED
            checks.append(_check(f"{input_name}_input", status, error))

    run = _execution_run(execution)
    details = _failure_details(run)
    model = _gpu_model(execution, profile)
    expected_model = str(expected_device.get("gpu_model_contains") or "A100")
    if not model:
        checks.append(_check("gpu_model", PENDING, "GPU model is missing"))
    elif expected_model.lower() not in model.lower():
        checks.append(_check("gpu_model", REJECTED, f"GPU model is {model!r}, expected a model containing {expected_model!r}"))
    else:
        checks.append(_check("gpu_model", ACCEPTED, f"GPU model {model!r} contains {expected_model!r}"))

    expected_arch = str(expected_device.get("gpu_arch_target") or "sm80")
    arch_targets = _gpu_arch_targets(execution, profile)
    arch = ", ".join(arch_targets) if arch_targets else None
    wrong_arch_targets = [target for target in arch_targets if target != expected_arch]
    if not arch_targets:
        checks.append(_check("gpu_arch_target", PENDING, "GPU architecture target is missing"))
    elif wrong_arch_targets:
        checks.append(_check("gpu_arch_target", REJECTED, f"GPU architecture target includes {wrong_arch_targets}, expected only {expected_arch!r}"))
    else:
        checks.append(_check("gpu_arch_target", ACCEPTED, f"GPU architecture target is {expected_arch}"))

    min_mem_gb = float(expected_device.get("gpu_mem_gb_min") or 39.0)
    mem_gb = _gpu_mem_gb(execution, profile)
    if mem_gb is None:
        checks.append(_check("gpu_memory", PENDING, "GPU memory is missing"))
    elif mem_gb < min_mem_gb:
        checks.append(_check("gpu_memory", REJECTED, f"GPU memory is {mem_gb:.3g} GB, below required {min_mem_gb:.3g} GB"))
    else:
        checks.append(_check("gpu_memory", ACCEPTED, f"GPU memory is {mem_gb:.3g} GB"))

    expected_source = required_execution.get("execution_source")
    execution_source = _first_text(run.get("execution_source"), details.get("execution_source"))
    if not execution_source:
        checks.append(_check("execution_source", PENDING, "execution_source is missing"))
    elif execution_source != expected_source:
        checks.append(_check("execution_source", REJECTED, f"execution_source is {execution_source!r}, expected {expected_source!r}"))
    else:
        checks.append(_check("execution_source", ACCEPTED, f"execution_source is {expected_source}"))

    expected_status = required_execution.get("status")
    run_status = _first_text(run.get("status"))
    if not run_status:
        checks.append(_check("execution_status", PENDING, "execution status is missing"))
    elif run_status != expected_status:
        checks.append(_check("execution_status", REJECTED, f"execution status is {run_status!r}, expected {expected_status!r}"))
    else:
        checks.append(_check("execution_status", ACCEPTED, f"execution status is {expected_status}"))

    reason_code = _first_text(details.get("reason_code"))
    rejected_reason_codes = set(required_execution.get("rejected_reason_codes") or [])
    if reason_code:
        status = REJECTED if reason_code in rejected_reason_codes else REJECTED
        checks.append(_check("failure_reason_code", status, f"failure reason_code is present: {reason_code}"))
    else:
        checks.append(_check("failure_reason_code", ACCEPTED, "no failure reason_code present"))

    accuracy = execution.get("accuracy_eval") if execution else None
    accuracy_status = _first_text((accuracy or {}).get("status") if isinstance(accuracy, dict) else None)
    expected_accuracy = required_accuracy.get("status")
    if not accuracy_status:
        checks.append(_check("accuracy_eval", PENDING, "accuracy_eval.status is missing"))
    elif accuracy_status != expected_accuracy:
        checks.append(_check("accuracy_eval", REJECTED, f"accuracy_eval.status is {accuracy_status!r}, expected {expected_accuracy!r}"))
    else:
        checks.append(_check("accuracy_eval", ACCEPTED, f"accuracy_eval.status is {expected_accuracy}"))

    source = _profile_source(profile)
    if not profile:
        checks.append(_check("profile_summary", PENDING, "profile summary is missing"))
    elif source not in accepted_profile_sources:
        checks.append(_check("profile_source", REJECTED, f"profile source is {source!r}, expected one of {sorted(accepted_profile_sources)}"))
    else:
        checks.append(_check("profile_source", ACCEPTED, f"profile source is {source}"))

    profiler_kind = _first_text((profile or {}).get("profiler_kind"))
    derived = (profile or {}).get("derived_signals_json") if profile else None
    derived = derived if isinstance(derived, dict) else {}
    if profiler_kind == "ncu" or source == "real_ncu_profile":
        csv_nonempty = derived.get("csv_nonempty")
        csv_path = _resolve_profile_artifact_path(derived.get("ncu_csv_path"), profile_path, evidence_dir)
        csv_kernel_rows = _csv_has_kernel_rows(csv_path) if csv_path else None
        top_kernels = (profile or {}).get("top_kernels_json") if profile else None
        has_kernels = bool(top_kernels) or csv_kernel_rows is True
        if csv_nonempty is True or csv_kernel_rows is True:
            checks.append(_check("ncu_csv_nonempty", ACCEPTED, "NCU CSV is marked non-empty"))
        elif csv_nonempty is False or csv_kernel_rows is False:
            checks.append(_check("ncu_csv_nonempty", REJECTED, "NCU CSV is empty"))
        else:
            checks.append(_check("ncu_csv_nonempty", PENDING, "NCU CSV non-empty signal is missing"))
        if has_kernels:
            checks.append(_check("ncu_kernels_captured", ACCEPTED, "NCU kernels are captured"))
        else:
            checks.append(_check("ncu_kernels_captured", REJECTED if profile else PENDING, "NCU kernels are not captured"))

    artifact_paths = _artifact_path_values(artifact_manifest)
    wildcards = list(artifact_rules.get("forbidden_wildcards") or ["*", "?", "[", "]"])
    if not artifact_manifest:
        checks.append(_check("artifact_manifest", PENDING, "artifact manifest is missing"))
    elif not artifact_paths:
        checks.append(_check("artifact_paths", PENDING, "artifact manifest contains no concrete path fields"))
    else:
        wildcard_paths = [f"{key}={value}" for key, value in artifact_paths if _contains_wildcard(value, wildcards)]
        if wildcard_paths:
            checks.append(_check("artifact_paths", REJECTED, "artifact paths contain wildcards: " + "; ".join(wildcard_paths)))
        else:
            checks.append(_check("artifact_paths", ACCEPTED, f"{len(artifact_paths)} concrete artifact paths found"))

    interpretation_key = str(interpretation_rules.get("required_key") or "interpretation_class")
    interpretation_values = _values_for_key(artifact_manifest, interpretation_key) if artifact_manifest else []
    interpretation_class = _first_text(*interpretation_values)
    if not interpretation_class:
        checks.append(_check("interpretation_class", PENDING, "interpretation_class is missing"))
    else:
        checks.append(_check("interpretation_class", ACCEPTED, f"interpretation_class is {interpretation_class}"))

    max_qubits = int(tiny_policy.get("max_qubits") or 3)
    markers = list(tiny_policy.get("ghz_name_markers") or ["ghz3"])
    qubits = _qubit_count(execution, artifact_manifest)
    is_tiny = (qubits is not None and qubits <= max_qubits) or _has_marker(execution, markers) or _has_marker(artifact_manifest, markers)
    throughput_overclaim = _throughput_benchmark_true(execution, profile, artifact_manifest)
    if is_tiny and throughput_overclaim:
        checks.append(_check("tiny_workload_throughput_claim", REJECTED, "tiny GHZ workload is labeled throughput_benchmark=true"))
    elif is_tiny:
        checks.append(_check("tiny_workload_throughput_claim", ACCEPTED, "tiny workload is not labeled as a throughput benchmark"))
    else:
        checks.append(_check("tiny_workload_throughput_claim", ACCEPTED, "workload is not classified as tiny GHZ"))

    statuses = {check["status"] for check in checks}
    if REJECTED in statuses:
        status = REJECTED
        exit_code = int((gate.get("outcomes") or {}).get("rejected_exit_code") or 2)
    elif PENDING in statuses:
        status = PENDING
        exit_code = int((gate.get("outcomes") or {}).get("pending_exit_code") or 1)
    else:
        status = ACCEPTED
        exit_code = int((gate.get("outcomes") or {}).get("accepted_exit_code") or 0)

    return {
        "gate_name": gate.get("gate_name"),
        "gate_version": gate.get("api_version"),
        "status": status,
        "exit_code": exit_code,
        "run_id": run.get("run_id"),
        "gpu_model": model,
        "gpu_arch_target": arch,
        "gpu_mem_gb": None if mem_gb is None else round(mem_gb, 6),
        "execution_source": execution_source,
        "profiler_kind": profiler_kind,
        "profile_source": source,
        "interpretation_class": interpretation_class,
        "tiny_workload": bool(is_tiny),
        "throughput_benchmark": throughput_overclaim,
        "checks": checks,
        "rejections": [check for check in checks if check["status"] == REJECTED],
        "pending": [check for check in checks if check["status"] == PENDING],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a candidate GCP A100 artifact set offline")
    parser.add_argument("--execution", help="Execution payload JSON")
    parser.add_argument("--profile-summary", help="Reduced Nsight profile summary JSON")
    parser.add_argument("--artifact-manifest", help="Pinned artifact manifest JSON")
    parser.add_argument("--evidence-dir", help="Directory containing execution/profile/artifact JSON files")
    parser.add_argument("--gate", default=DEFAULT_GATE, help="Acceptance gate YAML")
    args = parser.parse_args()

    gate_path = _resolve_path(args.gate)
    assert gate_path is not None
    gate = load_yaml(gate_path)

    evidence_dir = _resolve_path(args.evidence_dir)
    discovered: dict[str, Path | None] = {}
    if evidence_dir is not None and evidence_dir.exists():
        discovered = _resolve_evidence_dir(evidence_dir)

    execution_path = _resolve_path(args.execution) or discovered.get("execution")
    profile_path = _resolve_path(args.profile_summary) or discovered.get("profile_summary")
    artifact_path = _resolve_path(args.artifact_manifest) or discovered.get("artifact_manifest")

    execution, execution_error = _load_json(execution_path)
    profile, profile_error = _load_json(profile_path)
    artifact_manifest, artifact_error = _load_json(artifact_path)

    result = validate_candidate(
        gate=gate,
        execution=execution,
        profile=profile,
        artifact_manifest=artifact_manifest,
        profile_path=profile_path,
        evidence_dir=evidence_dir,
        load_errors={
            "execution": execution_error,
            "profile_summary": profile_error,
            "artifact_manifest": artifact_error,
        },
    )
    result["inputs"] = {
        "gate": _repo_path(gate_path),
        "execution": _repo_path(execution_path),
        "profile_summary": _repo_path(profile_path),
        "artifact_manifest": _repo_path(artifact_path),
        "evidence_dir": _repo_path(evidence_dir),
    }

    print(json.dumps(result, indent=2, sort_keys=True))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
