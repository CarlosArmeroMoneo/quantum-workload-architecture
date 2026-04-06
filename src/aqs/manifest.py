from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import yaml

from .capabilities import validate_implemented_workload, validate_real_workload
from .graph_modes import GRAPH_MODES
from .utils import canonical_json, sha256_text


WORKLOAD_COMMON_REQUIRED = {
    "api_version",
    "family_id",
    "family_version",
    "generator_name",
    "generator_version",
    "source_format",
    "semantic_target",
    "reference_tier",
    "split_tag",
    "repeat_count_hint",
    "parameters",
}

WORKLOAD_ENUMS = {
    "source_format": {"qiskit", "cirq", "stim", "cudaq", "normalized_ir"},
    "semantic_target": {"state", "amplitude", "batched_amplitudes", "expectation", "samples", "detectors", "syndrome_summary"},
    "reference_tier": {"smoke", "exact_ref", "boundary", "scale"},
    "split_tag": {"train", "val", "test", "heldout_family", "demo"},
}

SOURCE_LOADERS = {
    "qiskit": {"qasm2_file", "qasm2_inline"},
    "cirq": {"cirq_json_file", "cirq_json_inline"},
    "stim": {"stim_text_file", "stim_text_inline"},
    "cudaq": {"cudaq_python_file"},
    "normalized_ir": {"normalized_ir"},
}

PROBE_STRATEGIES = {"surrogate_only", "structural_real", "real_if_available", "cuquantum_if_available", "cuquantum_required"}
EXECUTION_INTENTS = {"optional_real", "prefer_real", "require_real"}

FAMILY_PARAM_RULES: dict[str, dict[str, tuple[type | tuple[type, ...], Any]]] = {
    "dense_universal": {
        "n_qubits": (int, lambda v: v > 0),
        "depth": (int, lambda v: v >= 0),
        "topology": (str, {"ring", "grid", "all_to_all"}),
        "two_qubit_density": (str, {"low", "medium", "high"}),
        "measurement_pattern": (str, {"terminal_all", "terminal_observable_only"}),
    },
    "qaoa_graph": {
        "n_qubits": (int, lambda v: v > 0),
        "graph_family": (str, {"ring", "2d_grid", "erdos_renyi", "random_regular", "barabasi"}),
        "graph_degree": (int, lambda v: v >= 0),
        "p": (int, lambda v: v > 0),
        "observable_count": (int, lambda v: v > 0),
    },
    "trotter_1d": {
        "n_qubits": (int, lambda v: v > 0),
        "steps": (int, lambda v: v > 0),
        "hamiltonian_pattern": (str, {"xxz", "transverse_field_ising"}),
        "boundary_condition": (str, {"open", "periodic"}),
        "observable_count": (int, lambda v: v > 0),
    },
    "grid_2d_shallow": {
        "rows": (int, lambda v: v > 0),
        "cols": (int, lambda v: v > 0),
        "layers": (int, lambda v: v > 0),
        "entangler_pattern": (str, {"brickwork", "checkerboard"}),
    },
    "star_graph_phase": {
        "n_qubits": (int, lambda v: v > 0),
        "hub_qubit": (int, lambda v: v >= 0),
        "spoke_count": (int, lambda v: v > 0),
        "phase_rounds": (int, lambda v: v > 0),
        "entangler_pattern": (str, {"star"}),
    },
    "ladder_brickwork": {
        "n_qubits": (int, lambda v: v > 0),
        "rows": (int, lambda v: v > 0),
        "cols": (int, lambda v: v > 0),
        "layers": (int, lambda v: v > 0),
        "boundary_condition": (str, {"open"}),
        "entangler_pattern": (str, {"ladder_brickwork"}),
    },
    "parity_iqp": {
        "n_qubits": (int, lambda v: v > 0),
        "parity_terms": (int, lambda v: v > 0),
        "phase_layers": (int, lambda v: v > 0),
        "connectivity": (str, {"offset_pairs", "ladder"}),
    },
    "spin_chain_phase": {
        "n_qubits": (int, lambda v: v > 0),
        "steps": (int, lambda v: v > 0),
        "coupling_pattern": (str, {"alternating", "staggered"}),
        "boundary_condition": (str, {"open"}),
    },
    "noisy_observable": {
        "n_qubits": (int, lambda v: v > 0),
        "depth": (int, lambda v: v > 0),
        "noise_model": (str, {"depolarizing", "amplitude_damping", "phase_flip"}),
        "noise_rate": ((int, float), lambda v: v >= 0),
        "observable_count": (int, lambda v: v > 0),
    },
    "qec_clifford": {
        "code_family": (str, {"repetition", "small_surface_like"}),
        "distance": (int, lambda v: v > 0),
        "cycles": (int, lambda v: v > 0),
        "detector_layout": (str, {"line", "surface_patch"}),
    },
    "repeated_sweep": {
        "base_family": (str, {"dense_universal", "qaoa_graph", "trotter_1d", "grid_2d_shallow"}),
        "repeat_count": (int, lambda v: v > 0),
        "parameter_kind": (str, {"angles", "fields", "observables"}),
    },
}

SYSTEM_REQUIRED = {
    "api_version",
    "system_name",
    "gpu_count",
    "gpu_mem_gb",
}

BENCHMARK_REQUIRED = {
    "api_version",
    "project",
    "dataset_name",
    "version_tag",
    "objective",
    "system_manifest",
    "workload_glob",
    "allowed_modes",
}

CAMPAIGN_REQUIRED = {
    "api_version",
    "campaign_name",
    "objective",
    "system_manifest",
    "outdir",
    "workloads",
    "plan_source",
    "matrix",
    "replicates",
    "execution_intent",
    "probe_strategy",
}

SESSION_REQUIRED = {
    "api_version",
    "project",
    "mode",
    "system_manifest",
    "objective",
    "probe_strategy",
    "planner_budget",
    "measurement_repeats",
    "execution_intent",
    "graph_mode",
    "allow_distributed",
    "requests",
}

SESSION_PLAN_BUNDLE_VERSION = "aqs.plan_bundle.v1"
SESSION_MODES = {"persistent_execute_sequence"}
PLANNER_BUDGETS = {"quick", "balanced", "deep"}


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping at {path}")
    return data


def dump_yaml(data: dict[str, Any], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def finalize_workload_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    manifest = deepcopy(manifest)
    payload = {
        key: manifest[key]
        for key in sorted(manifest.keys())
        if key not in {"ids"}
    }
    source_hash = sha256_text(canonical_json(payload))
    workload_id = "wkl_" + source_hash[:16]
    manifest["ids"] = {
        "workload_id": workload_id,
        "source_hash": source_hash,
    }
    return manifest


def _check_typed_rule(name: str, value: Any, type_spec: Any, constraint: Any) -> str | None:
    if not isinstance(value, type_spec):
        return f"parameter '{name}' should be of type {type_spec}, got {type(value)}"
    if callable(constraint) and not constraint(value):
        return f"parameter '{name}' failed its value constraint"
    if isinstance(constraint, set) and value not in constraint:
        return f"parameter '{name}' must be one of {sorted(constraint)}, got {value!r}"
    return None


def _validate_source_descriptor(source_format: str, source: Any) -> list[str]:
    errors: list[str] = []
    if source_format == "normalized_ir":
        if source and source.get("loader") not in {None, "normalized_ir"}:
            errors.append("normalized_ir workloads should not declare an external source loader")
        return errors

    if not isinstance(source, dict):
        return [f"source is required and must be a mapping for source_format={source_format!r}"]
    loader = source.get("loader")
    allowed_loaders = SOURCE_LOADERS.get(source_format, set())
    if loader not in allowed_loaders:
        errors.append(f"source.loader must be one of {sorted(allowed_loaders)} for source_format={source_format!r}")
        return errors

    if loader.endswith("_file") and not isinstance(source.get("path"), str):
        errors.append(f"source.path is required for loader={loader!r}")
    if loader.endswith("_inline") and not isinstance(source.get("text"), str):
        errors.append(f"source.text is required for loader={loader!r}")
    return errors


def _validate_execution_target(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    target = manifest.get("execution_target")
    semantic_target = manifest.get("semantic_target")
    source_format = manifest.get("source_format")
    if semantic_target not in {"amplitude", "batched_amplitudes"}:
        if target is not None and not isinstance(target, dict):
            errors.append("execution_target must be a mapping when provided")
        return errors

    requires_target = source_format == "qiskit"
    if target is None:
        if requires_target:
            errors.append("execution_target is required for imported qiskit amplitude/batched_amplitudes workloads")
        return errors
    if not isinstance(target, dict):
        errors.append("execution_target must be a mapping")
        return errors

    kind = target.get("kind")
    if kind != semantic_target:
        errors.append(f"execution_target.kind must match semantic_target {semantic_target!r}")
        return errors

    if kind == "amplitude":
        bitstring = target.get("bitstring")
        n_qubits = manifest.get("parameters", {}).get("n_qubits")
        if not isinstance(bitstring, str) or not bitstring or any(ch not in {"0", "1"} for ch in bitstring):
            errors.append("execution_target.bitstring must be a non-empty bitstring")
        elif isinstance(n_qubits, int) and len(bitstring) != n_qubits:
            errors.append("execution_target.bitstring length must match parameters.n_qubits")
    elif kind == "batched_amplitudes":
        fixed_qubits = target.get("fixed_qubits")
        n_qubits = manifest.get("parameters", {}).get("n_qubits")
        if not isinstance(fixed_qubits, dict):
            errors.append("execution_target.fixed_qubits must be a mapping of qubit index to 0 or 1")
        else:
            seen: set[int] = set()
            for key, value in fixed_qubits.items():
                try:
                    qubit = int(key)
                except Exception:
                    errors.append(f"execution_target.fixed_qubits key {key!r} is not an integer")
                    continue
                if qubit < 0:
                    errors.append(f"execution_target.fixed_qubits key {key!r} must be >= 0")
                if isinstance(n_qubits, int) and qubit >= n_qubits:
                    errors.append(f"execution_target.fixed_qubits key {key!r} must be < parameters.n_qubits")
                if qubit in seen:
                    errors.append(f"execution_target.fixed_qubits key {key!r} is duplicated")
                seen.add(qubit)
                if value not in {0, 1, "0", "1"}:
                    errors.append(f"execution_target.fixed_qubits[{key!r}] must be 0 or 1")
    return errors


def validate_workload_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(WORKLOAD_COMMON_REQUIRED - set(manifest.keys()))
    if missing:
        errors.append(f"missing required fields: {missing}")
        return errors
    if manifest.get("api_version") != "aqs.workload.v1":
        errors.append("api_version must be 'aqs.workload.v1'")
    family_id = manifest.get("family_id")
    if family_id not in FAMILY_PARAM_RULES:
        errors.append(f"unsupported family_id: {family_id!r}")
        return errors
    for key, allowed in WORKLOAD_ENUMS.items():
        if manifest.get(key) not in allowed:
            errors.append(f"field '{key}' must be one of {sorted(allowed)}, got {manifest.get(key)!r}")
    repeat_count_hint = manifest.get("repeat_count_hint")
    if not isinstance(repeat_count_hint, int) or repeat_count_hint < 1:
        errors.append("repeat_count_hint must be an integer >= 1")
    params = manifest.get("parameters")
    if not isinstance(params, dict):
        errors.append("parameters must be a mapping")
        return errors
    rules = FAMILY_PARAM_RULES[family_id]
    for field_name, (type_spec, constraint) in rules.items():
        if field_name not in params:
            errors.append(f"missing parameter '{field_name}' for family '{family_id}'")
            continue
        maybe_error = _check_typed_rule(field_name, params[field_name], type_spec, constraint)
        if maybe_error:
            errors.append(maybe_error)

    errors.extend(_validate_source_descriptor(str(manifest.get("source_format")), manifest.get("source")))
    errors.extend(_validate_execution_target(manifest))

    finalized = finalize_workload_manifest(manifest)
    ids = manifest.get("ids")
    if ids:
        if ids.get("workload_id") != finalized["ids"]["workload_id"]:
            errors.append("ids.workload_id does not match the canonical hash-derived workload ID")
        if ids.get("source_hash") != finalized["ids"]["source_hash"]:
            errors.append("ids.source_hash does not match the canonical source hash")
    return errors


def validate_system_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(SYSTEM_REQUIRED - set(manifest.keys()))
    if missing:
        errors.append(f"missing required fields: {missing}")
        return errors
    if manifest.get("api_version") != "aqs.system.v1":
        errors.append("api_version must be 'aqs.system.v1'")
    if not isinstance(manifest.get("gpu_count"), int) or manifest["gpu_count"] < 0:
        errors.append("gpu_count must be an integer >= 0")
    if not isinstance(manifest.get("gpu_mem_gb"), (int, float)) or manifest["gpu_mem_gb"] < 0:
        errors.append("gpu_mem_gb must be numeric and >= 0")
    return errors


def validate_benchmark_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(BENCHMARK_REQUIRED - set(manifest.keys()))
    if missing:
        errors.append(f"missing required fields: {missing}")
        return errors
    if manifest.get("api_version") != "aqs.benchmark.v1":
        errors.append("api_version must be 'aqs.benchmark.v1'")
    if manifest.get("project") not in {"foundation", "atlas", "tnep", "arch"}:
        errors.append("project must be one of foundation/atlas/tnep/arch")
    if manifest.get("objective") not in {"ttfr", "steady_state", "gpu_seconds"}:
        errors.append("objective must be one of ttfr/steady_state/gpu_seconds")
    allowed_modes = manifest.get("allowed_modes")
    if not isinstance(allowed_modes, list) or not allowed_modes:
        errors.append("allowed_modes must be a non-empty list")
    probe_strategy = manifest.get("probe_strategy")
    if probe_strategy is not None and probe_strategy not in PROBE_STRATEGIES:
        errors.append(f"probe_strategy must be one of {sorted(PROBE_STRATEGIES)}")
    execution_intent = manifest.get("execution_intent")
    if execution_intent is not None and execution_intent not in EXECUTION_INTENTS:
        errors.append(f"execution_intent must be one of {sorted(EXECUTION_INTENTS)}")
    ttfr_repeats = manifest.get("ttfr_repeats")
    if ttfr_repeats is not None and (not isinstance(ttfr_repeats, int) or ttfr_repeats < 1):
        errors.append("ttfr_repeats must be an integer >= 1 when provided")
    max_workloads = manifest.get("max_workloads")
    if max_workloads is not None and (not isinstance(max_workloads, int) or max_workloads < 1):
        errors.append("max_workloads must be an integer >= 1 when provided")
    return errors


def validate_campaign_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(CAMPAIGN_REQUIRED - set(manifest.keys()))
    if missing:
        errors.append(f"missing required fields: {missing}")
        return errors
    if manifest.get("api_version") != "aqs.campaign.v1":
        errors.append("api_version must be 'aqs.campaign.v1'")
    if not isinstance(manifest.get("campaign_name"), str) or not str(manifest.get("campaign_name")).strip():
        errors.append("campaign_name must be a non-empty string")
    if manifest.get("objective") not in {"ttfr", "steady_state", "gpu_seconds"}:
        errors.append("objective must be one of ttfr/steady_state/gpu_seconds")
    if not isinstance(manifest.get("system_manifest"), str) or not manifest.get("system_manifest"):
        errors.append("system_manifest must be a non-empty path string")
    if not isinstance(manifest.get("outdir"), str) or not manifest.get("outdir"):
        errors.append("outdir must be a non-empty path string")

    workloads = manifest.get("workloads")
    if not isinstance(workloads, list) or not workloads or not all(isinstance(path, str) and path for path in workloads):
        errors.append("workloads must be a non-empty list of manifest path strings")

    plan_source = manifest.get("plan_source")
    if not isinstance(plan_source, dict):
        errors.append("plan_source must be a mapping")
    else:
        kind = plan_source.get("kind")
        if kind not in {"planner_templates", "explicit_matrix"}:
            errors.append("plan_source.kind must be one of planner_templates/explicit_matrix")
        policy_path = plan_source.get("policy_path")
        if policy_path is not None and not isinstance(policy_path, str):
            errors.append("plan_source.policy_path must be a path string when provided")
        policy_overrides = plan_source.get("policy_overrides")
        if policy_overrides is not None and not isinstance(policy_overrides, dict):
            errors.append("plan_source.policy_overrides must be a mapping when provided")

    matrix = manifest.get("matrix")
    allowed_matrix_keys = {
        "planner_budget",
        "repeat_count_hint",
        "autotune",
        "reuse_cache",
        "workspace_gb",
        "cache_workspace_gb",
        "hyper_samples",
        "precision",
        "mode",
        "measurement_repeats",
        "plan_json",
        "graph_mode",
    }
    if not isinstance(matrix, dict) or not matrix:
        errors.append("matrix must be a non-empty mapping of parameter name to value list")
    else:
        for key, values in matrix.items():
            if key not in allowed_matrix_keys:
                errors.append(f"matrix contains unsupported key {key!r}")
                continue
            if not isinstance(values, list) or not values:
                errors.append(f"matrix.{key} must be a non-empty list")
                continue
            if key == "graph_mode":
                invalid = [value for value in values if value not in GRAPH_MODES]
                if invalid:
                    errors.append(f"matrix.graph_mode values must be drawn from {list(GRAPH_MODES)}, got {invalid!r}")

    replicates = manifest.get("replicates")
    if not isinstance(replicates, int) or replicates < 1:
        errors.append("replicates must be an integer >= 1")

    if manifest.get("execution_intent") not in EXECUTION_INTENTS:
        errors.append(f"execution_intent must be one of {sorted(EXECUTION_INTENTS)}")
    if manifest.get("probe_strategy") not in PROBE_STRATEGIES:
        errors.append(f"probe_strategy must be one of {sorted(PROBE_STRATEGIES)}")

    profile_policy = manifest.get("profile_policy")
    if profile_policy is not None:
        if not isinstance(profile_policy, dict):
            errors.append("profile_policy must be a mapping when provided")
        else:
            allowed_policy = {"never", "representative_only", "all"}
            for key in ("nsys", "ncu"):
                value = profile_policy.get(key)
                if value is not None and value not in allowed_policy:
                    errors.append(f"profile_policy.{key} must be one of {sorted(allowed_policy)}")
    return errors


def _validate_session_plan_bundle(path: str | Path) -> list[str]:
    bundle_path = Path(path).expanduser()
    if not bundle_path.exists():
        return [f"plan_bundle path does not exist: {bundle_path}"]
    try:
        payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"plan_bundle at {bundle_path} could not be decoded as JSON: {exc}"]
    if not isinstance(payload, dict):
        return [f"plan_bundle at {bundle_path} must decode to a JSON object"]
    errors: list[str] = []
    if payload.get("api_version") != SESSION_PLAN_BUNDLE_VERSION:
        errors.append(
            f"plan_bundle at {bundle_path} must declare api_version={SESSION_PLAN_BUNDLE_VERSION!r}, "
            f"got {payload.get('api_version')!r}"
        )
    if payload.get("bundle_schema_version") != SESSION_PLAN_BUNDLE_VERSION:
        errors.append(
            f"plan_bundle at {bundle_path} must declare bundle_schema_version={SESSION_PLAN_BUNDLE_VERSION!r}, "
            f"got {payload.get('bundle_schema_version')!r}"
        )
    if not isinstance(payload.get("bundle_scope"), dict):
        errors.append(f"plan_bundle at {bundle_path} must include a bundle_scope object")
    if not isinstance(payload.get("selected_plan"), dict):
        errors.append(f"plan_bundle at {bundle_path} must include a selected_plan object")
    return errors


def validate_session_manifest(manifest: dict[str, Any], *, mode: str = "schema") -> list[str]:
    errors: list[str] = []
    missing = sorted(SESSION_REQUIRED - set(manifest.keys()))
    if missing:
        errors.append(f"missing required fields: {missing}")
        return errors
    if manifest.get("api_version") != "aqs.session.v1":
        errors.append("api_version must be 'aqs.session.v1'")
    if manifest.get("project") != "tnep":
        errors.append("project must be 'tnep' in session manifests")
    if manifest.get("mode") not in SESSION_MODES:
        errors.append(f"mode must be one of {sorted(SESSION_MODES)}")
    if manifest.get("objective") not in {"ttfr", "steady_state", "gpu_seconds"}:
        errors.append("objective must be one of ttfr/steady_state/gpu_seconds")
    if manifest.get("probe_strategy") not in PROBE_STRATEGIES:
        errors.append(f"probe_strategy must be one of {sorted(PROBE_STRATEGIES)}")
    if manifest.get("planner_budget") not in PLANNER_BUDGETS:
        errors.append(f"planner_budget must be one of {sorted(PLANNER_BUDGETS)}")
    if not isinstance(manifest.get("measurement_repeats"), int) or int(manifest["measurement_repeats"]) < 1:
        errors.append("measurement_repeats must be an integer >= 1")
    if manifest.get("execution_intent") not in EXECUTION_INTENTS:
        errors.append(f"execution_intent must be one of {sorted(EXECUTION_INTENTS)}")
    if manifest.get("graph_mode") not in GRAPH_MODES:
        errors.append(f"graph_mode must be one of {list(GRAPH_MODES)}")
    if not isinstance(manifest.get("allow_distributed"), bool):
        errors.append("allow_distributed must be a boolean")

    system_manifest_path = manifest.get("system_manifest")
    if not isinstance(system_manifest_path, str) or not system_manifest_path:
        errors.append("system_manifest must be a non-empty path string")
    else:
        try:
            system_payload = load_yaml(system_manifest_path)
        except Exception as exc:
            errors.append(f"system_manifest could not be loaded from {system_manifest_path}: {exc}")
        else:
            for error in validate_manifest(system_payload, mode="schema"):
                errors.append(f"system_manifest {system_manifest_path}: {error}")

    requests = manifest.get("requests")
    if not isinstance(requests, list) or not requests:
        errors.append("requests must be a non-empty list")
        return errors

    seen_ids: set[str] = set()
    for index, request in enumerate(requests):
        prefix = f"requests[{index}]"
        if not isinstance(request, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        request_id = request.get("id")
        if not isinstance(request_id, str) or not request_id.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        elif request_id in seen_ids:
            errors.append(f"{prefix}.id duplicates an earlier request id: {request_id!r}")
        else:
            seen_ids.add(request_id)
        workload_manifest_path = request.get("workload_manifest")
        if not isinstance(workload_manifest_path, str) or not workload_manifest_path:
            errors.append(f"{prefix}.workload_manifest must be a non-empty path string")
        else:
            try:
                workload_payload = load_yaml(workload_manifest_path)
            except Exception as exc:
                errors.append(f"{prefix}.workload_manifest could not be loaded from {workload_manifest_path}: {exc}")
            else:
                for error in validate_manifest(workload_payload, mode=mode):
                    errors.append(f"{prefix}.workload_manifest {workload_manifest_path}: {error}")
        bundle_path = request.get("plan_bundle")
        if not isinstance(bundle_path, str) or not bundle_path:
            errors.append(f"{prefix}.plan_bundle must be a non-empty path string")
        else:
            for error in _validate_session_plan_bundle(bundle_path):
                errors.append(f"{prefix}.plan_bundle {error}")
    return errors


def validate_manifest(manifest: dict[str, Any], *, mode: str = "schema") -> list[str]:
    if mode not in {"schema", "implemented", "real"}:
        return [f"unsupported validation mode: {mode!r}"]

    api_version = manifest.get("api_version")
    if api_version == "aqs.workload.v1":
        errors = validate_workload_manifest(manifest)
        if errors or mode == "schema":
            return errors
        if mode == "implemented":
            return validate_implemented_workload(manifest)
        return validate_real_workload(manifest)
    if api_version == "aqs.system.v1":
        return validate_system_manifest(manifest)
    if api_version == "aqs.benchmark.v1":
        return validate_benchmark_manifest(manifest)
    if api_version == "aqs.campaign.v1":
        return validate_campaign_manifest(manifest)
    if api_version == "aqs.session.v1":
        return validate_session_manifest(manifest, mode=mode)
    return [f"unsupported api_version: {api_version!r}"]
