from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import math

import networkx as nx
import numpy as np
import opt_einsum as oe

from .exact_tn_targets import target_to_fixed_map
from .normalize import SyntheticGate, graph_from_family
from .source_adapters import CircuitSummary, load_circuit_summary, maybe_load_qiskit_circuit
from .utils import canonical_json, sha256_text


PROBE_VERSION = "aqs.tn_probe.v1"


@dataclass(frozen=True)
class ProbeConfig:
    objective: str = "ttfr"
    precision: str = "complex128"
    workspace_gb: float | None = None
    cache_workspace_gb: float | None = None
    hyper_samples: int | None = None
    autotune: bool | None = None
    reuse_cache: bool | None = None
    mpi_ranks: int | None = None
    gpu_arch_target: str | None = None
    probe_strategy: str = "surrogate_only"


def _dtype_from_precision(precision: str) -> np.dtype:
    mapping = {
        "fp32": np.float32,
        "fp64": np.float64,
        "complex64": np.complex64,
        "complex128": np.complex128,
    }
    if precision not in mapping:
        raise ValueError(f"Unsupported precision: {precision}")
    return np.dtype(mapping[precision])


def _fresh_label(counter: list[int]) -> int:
    label = counter[0]
    counter[0] += 1
    return label


def _build_matchings(graph: nx.Graph, seed: int = 0) -> list[list[tuple[int, int]]]:
    if graph.number_of_edges() == 0:
        return []
    line = nx.line_graph(graph)
    colors = nx.coloring.greedy_color(line, strategy="largest_first")
    groups: dict[int, list[tuple[int, int]]] = {}
    for edge, color in colors.items():
        groups.setdefault(int(color), []).append(tuple(sorted(edge)))
    return [sorted(groups[color]) for color in sorted(groups)]


def _dense_universal_schedule(params: dict[str, Any], seed: int = 0) -> list[list[SyntheticGate]]:
    n = int(params["n_qubits"])
    depth = int(params["depth"])
    topology = params["topology"]
    density = params["two_qubit_density"]
    graph = graph_from_family("dense_universal", params, seed=seed)
    layers: list[list[SyntheticGate]] = []
    if topology == "ring":
        even = [(i, (i + 1) % n) for i in range(0, n, 2)]
        odd = [(i, (i + 1) % n) for i in range(1, n, 2)]
        matchings = [even, odd]
    elif topology == "grid":
        matchings = _build_matchings(graph, seed=seed)
    else:
        rng = np.random.default_rng(seed)
        matchings = []
        for _ in range(max(1, depth)):
            perm = list(rng.permutation(n))
            pairs = [(int(perm[i]), int(perm[i + 1])) for i in range(0, len(perm) - 1, 2)]
            matchings.append(pairs)
    density_to_layers = {"low": 1, "medium": 2, "high": max(2, min(4, len(matchings) if matchings else 2))}
    entangler_layers = density_to_layers[density]
    for d in range(depth):
        layers.append([SyntheticGate("u1", (q,), len(layers)) for q in range(n)])
        for k in range(entangler_layers):
            if not matchings:
                break
            pairs = matchings[(d + k) % len(matchings)]
            if pairs:
                layers.append([SyntheticGate("u2", tuple(sorted(pair)), len(layers)) for pair in pairs])
    return layers


def _graph_round_schedule(graph: nx.Graph, rounds: int, include_single_qubit: bool, n_qubits: int) -> list[list[SyntheticGate]]:
    layers: list[list[SyntheticGate]] = []
    matchings = _build_matchings(graph)
    if not matchings:
        matchings = [[]]
    for _ in range(rounds):
        for pairs in matchings:
            if pairs:
                layers.append([SyntheticGate("u2", tuple(sorted(pair)), len(layers)) for pair in pairs])
        if include_single_qubit:
            layers.append([SyntheticGate("u1", (q,), len(layers)) for q in range(n_qubits)])
    return layers


def synthetic_circuit_schedule(workload_manifest: dict[str, Any]) -> list[list[SyntheticGate]]:
    family = workload_manifest["family_id"]
    params = workload_manifest["parameters"]
    seed = int(workload_manifest.get("seed") or 0)
    if family == "dense_universal":
        return _dense_universal_schedule(params, seed=seed)
    if family == "qaoa_graph":
        graph = graph_from_family(family, params, seed=seed)
        return _graph_round_schedule(graph, rounds=int(params["p"]), include_single_qubit=True, n_qubits=int(params["n_qubits"]))
    if family == "trotter_1d":
        graph = graph_from_family(family, params, seed=seed)
        return _graph_round_schedule(graph, rounds=int(params["steps"]), include_single_qubit=True, n_qubits=int(params["n_qubits"]))
    if family == "grid_2d_shallow":
        graph = graph_from_family(family, params, seed=seed)
        n_qubits = int(params["rows"]) * int(params["cols"])
        return _graph_round_schedule(graph, rounds=int(params["layers"]), include_single_qubit=True, n_qubits=n_qubits)
    raise NotImplementedError(f"Unsupported synthetic TN probe family: {family!r}")


def _observable_support(workload_manifest: dict[str, Any], n_qubits: int) -> set[int]:
    semantic = workload_manifest["semantic_target"]
    if semantic != "expectation":
        return set()
    family = workload_manifest["family_id"]
    params = workload_manifest["parameters"]
    if family == "qaoa_graph":
        count = min(n_qubits, int(params.get("observable_count", 1)))
        return set(range(count))
    if family == "trotter_1d":
        count = min(n_qubits, int(params.get("observable_count", 1)))
        center = n_qubits // 2
        return set(range(max(0, center - count // 2), min(n_qubits, center + math.ceil(count / 2))))
    return {0}


def _build_forward_network(schedule: list[list[SyntheticGate]], n_qubits: int, dtype: np.dtype) -> tuple[list[np.ndarray], list[list[int]], list[int]]:
    operands: list[np.ndarray] = []
    labels: list[list[int]] = []
    next_label = [0]
    current = [_fresh_label(next_label) for _ in range(n_qubits)]

    init_vec = np.zeros((2,), dtype=dtype)
    init_vec[0] = 1
    for q in range(n_qubits):
        operands.append(init_vec.copy())
        labels.append([current[q]])

    for layer in schedule:
        for gate in layer:
            if gate.kind == "u1":
                q = gate.qubits[0]
                out = _fresh_label(next_label)
                operands.append(np.zeros((2, 2), dtype=dtype))
                labels.append([current[q], out])
                current[q] = out
            elif gate.kind == "u2":
                q0, q1 = gate.qubits
                out0 = _fresh_label(next_label)
                out1 = _fresh_label(next_label)
                operands.append(np.zeros((2, 2, 2, 2), dtype=dtype))
                labels.append([current[q0], current[q1], out0, out1])
                current[q0], current[q1] = out0, out1
            else:
                raise ValueError(f"Unsupported gate kind: {gate.kind}")
    return operands, labels, current


def _schedule_from_circuit_summary(summary: CircuitSummary) -> list[list[SyntheticGate]]:
    if summary.reset_count:
        raise ValueError("Reset operations are not supported in the exact-TN structural probe path")
    layers: dict[int, list[SyntheticGate]] = {}
    max_unitary_layer = max((op.layer for op in summary.operations if op.name not in {"measure", "reset"}), default=-1)
    for op in summary.operations:
        if op.name == "reset":
            raise ValueError("Reset operations are not supported in the exact-TN structural probe path")
        if op.name == "measure":
            if op.layer < max_unitary_layer:
                raise ValueError("Intermediate measurement is not supported in the exact-TN structural probe path")
            continue
        if len(op.qubits) == 1:
            gate = SyntheticGate("u1", op.qubits, op.layer)
        elif len(op.qubits) == 2:
            gate = SyntheticGate("u2", tuple(sorted(op.qubits)), op.layer)
        else:
            raise ValueError(f"Unsupported imported gate arity {len(op.qubits)} for gate {op.name!r}")
        layers.setdefault(op.layer, []).append(gate)
    return [layers[layer] for layer in sorted(layers)]


def _build_interleaved_from_schedule(
    schedule: list[list[SyntheticGate]],
    *,
    n_qubits: int,
    dtype: np.dtype,
    semantic: str,
    observable_support: list[int],
    raw: dict[str, Any],
    fixed_map: dict[int, int] | None = None,
) -> tuple[list[Any], dict[str, Any]]:
    if not schedule:
        raise ValueError("Tensor-network schedule is empty")
    operands, labels, current = _build_forward_network(schedule, n_qubits, dtype)
    output_labels: list[int]
    fixed_map = fixed_map or {}

    if semantic == "state":
        output_labels = list(current)
    elif semantic == "expectation":
        bra_operands, bra_labels, bra_current = _build_forward_network(list(reversed(schedule)), n_qubits, dtype)
        operands.extend(bra_operands)
        labels.extend(bra_labels)
        for q in range(n_qubits):
            operands.append(np.zeros((2, 2), dtype=dtype))
            labels.append([current[q], bra_current[q]])
        output_labels = []
    else:
        output_labels = []
        for q in range(n_qubits):
            if q in fixed_map:
                basis = np.zeros((2,), dtype=dtype)
                basis[int(fixed_map[q])] = 1
                operands.append(basis)
                labels.append([current[q]])
            else:
                output_labels.append(current[q])

    interleaved: list[Any] = []
    for operand, modes in zip(operands, labels):
        interleaved.extend([operand, modes])
    interleaved.append(output_labels)

    raw.update({
        "n_qubits": n_qubits,
        "layer_count": len(schedule),
        "tensor_count": len(operands),
        "observable_support": observable_support,
        "execution_target": fixed_map,
    })
    return interleaved, raw


def _build_interleaved_network(workload_manifest: dict[str, Any], dtype: np.dtype) -> tuple[list[Any], dict[str, Any]]:
    schedule = synthetic_circuit_schedule(workload_manifest)
    params = workload_manifest["parameters"]
    n_qubits = int(params.get("n_qubits") or (int(params["rows"]) * int(params["cols"])))
    semantic = workload_manifest["semantic_target"]
    observable_support = sorted(_observable_support(workload_manifest, n_qubits))
    raw = {
        "surrogate_kind": "synthetic_circuit_tn",
        "family_id": workload_manifest["family_id"],
        "semantic_target": semantic,
        "probe_input_kind": "interleaved",
        "probe_source": "surrogate_family_schedule",
    }
    fixed_map = None
    if semantic in {"amplitude", "batched_amplitudes"} and workload_manifest.get("execution_target"):
        fixed_map = target_to_fixed_map(workload_manifest, n_qubits=n_qubits)
    elif semantic == "amplitude":
        fixed_map = {q: 0 for q in range(n_qubits)}
    return _build_interleaved_from_schedule(schedule, n_qubits=n_qubits, dtype=dtype, semantic=semantic, observable_support=observable_support, raw=raw, fixed_map=fixed_map)


def _build_interleaved_from_summary(summary: CircuitSummary, workload_manifest: dict[str, Any], dtype: np.dtype) -> tuple[list[Any], dict[str, Any]]:
    schedule = _schedule_from_circuit_summary(summary)
    semantic = workload_manifest["semantic_target"]
    fixed_map = None
    if semantic in {"amplitude", "batched_amplitudes"} and workload_manifest.get("execution_target"):
        fixed_map = target_to_fixed_map(workload_manifest, n_qubits=summary.n_qubits)
    elif semantic == "amplitude":
        fixed_map = {q: 0 for q in range(summary.n_qubits)}
    raw = {
        "family_id": workload_manifest["family_id"],
        "semantic_target": semantic,
        "probe_input_kind": "interleaved",
        "probe_source": "structural_real_circuit",
        "source_kind": summary.source_kind,
        "loader": summary.loader,
        "imported_operation_count": len(summary.operations),
        "ignored_measurements": summary.measurement_count,
    }
    return _build_interleaved_from_schedule(
        schedule,
        n_qubits=summary.n_qubits,
        dtype=dtype,
        semantic=semantic,
        observable_support=[],
        raw=raw,
        fixed_map=fixed_map,
    )


def _build_circuit_to_einsum_probe_input(workload_manifest: dict[str, Any], config: ProbeConfig) -> tuple[list[Any], dict[str, Any]] | None:
    if workload_manifest.get("source_format") != "qiskit":
        return None
    circuit = maybe_load_qiskit_circuit(workload_manifest)
    if circuit is None:
        return None
    try:
        from cuquantum import CircuitToEinsum
    except Exception:
        return None

    converter = CircuitToEinsum(circuit, dtype=config.precision, backend="numpy")
    semantic = workload_manifest["semantic_target"]
    fixed_map: dict[int, int] = {}
    if semantic in {"amplitude", "batched_amplitudes"} and workload_manifest.get("execution_target"):
        fixed_map = target_to_fixed_map(workload_manifest, n_qubits=len(circuit.qubits))
    elif semantic == "amplitude":
        fixed_map = {q: 0 for q in range(len(circuit.qubits))}
    if semantic == "state":
        expression, operands = converter.state_vector()
    elif semantic == "amplitude":
        expression, operands = converter.amplitude("".join(str(fixed_map[q]) for q in range(len(circuit.qubits))))
    elif semantic == "batched_amplitudes":
        expression, operands = converter.batched_amplitudes(fixed_map)
    elif semantic == "expectation":
        pauli = "Z" + ("I" * max(0, len(circuit.qubits) - 1))
        expression, operands = converter.expectation(pauli)
    else:
        return None

    raw = {
        "family_id": workload_manifest["family_id"],
        "semantic_target": semantic,
        "probe_input_kind": "einsum_expression",
        "probe_source": "cuquantum_circuit_to_einsum",
        "source_kind": "qiskit",
        "loader": "qasm2",
        "qubit_count": len(circuit.qubits),
        "operand_count": len(operands),
    }
    return [expression, *operands], raw


def _select_probe_input(workload_manifest: dict[str, Any], config: ProbeConfig, dtype: np.dtype) -> tuple[list[Any], dict[str, Any]]:
    strategy = config.probe_strategy

    if strategy in {"cuquantum_if_available", "real_if_available", "cuquantum_required"}:
        maybe = _build_circuit_to_einsum_probe_input(workload_manifest, config)
        if maybe is not None:
            return maybe
        if strategy == "cuquantum_required":
            raise ValueError("cuQuantum/Qiskit-backed real circuit conversion was requested but is not available")

    if workload_manifest.get("source_format") != "normalized_ir" and strategy in {"structural_real", "real_if_available", "cuquantum_if_available"}:
        summary = load_circuit_summary(workload_manifest)
        if summary is not None:
            return _build_interleaved_from_summary(summary, workload_manifest, dtype)

    if strategy == "structural_real" and workload_manifest.get("source_format") == "normalized_ir":
        raise ValueError("structural_real probe strategy requires an imported circuit source")

    return _build_interleaved_network(workload_manifest, dtype)


def _probe_with_cuquantum(args: list[Any], config: ProbeConfig) -> tuple[list[Any], Any]:
    from cuquantum import contract_path

    optimize: dict[str, Any] = {}
    if config.hyper_samples is not None:
        optimize["samples"] = config.hyper_samples
    if config.gpu_arch_target:
        optimize["gpu_arch"] = config.gpu_arch_target
    return contract_path(*args, optimize=optimize or None)


def _probe_with_opt_einsum(args: list[Any]) -> tuple[list[Any], Any]:
    return oe.contract_path(*args, optimize="greedy")


def run_exact_tn_probe(workload_manifest: dict[str, Any], config: ProbeConfig | None = None) -> dict[str, Any]:
    config = config or ProbeConfig()
    dtype = _dtype_from_precision(config.precision)

    backend = "opt_einsum"
    status = "success"
    error_message = None
    path = None
    info: Any = None
    raw: dict[str, Any] = {}

    try:
        args, raw = _select_probe_input(workload_manifest, config, dtype)
        try:
            path, info = _probe_with_cuquantum(args, config)
            backend = "cuquantum"
        except Exception:
            path, info = _probe_with_opt_einsum(args)
            backend = "opt_einsum"
    except ValueError as exc:
        status = "unsupported"
        error_message = str(exc)
    except Exception as exc:
        status = "probe_fail"
        error_message = str(exc)

    largest_intermediate = None
    optimizer_cost = None
    num_slices = None
    path_length = None
    if status == "success":
        largest_intermediate = float(getattr(info, "largest_intermediate", 0.0)) if info is not None else None
        optimizer_cost = float(getattr(info, "opt_cost", 0.0)) if info is not None else None
        num_slices = int(getattr(info, "num_slices", 1)) if info is not None and hasattr(info, "num_slices") else 1
        path_length = len(path) if path is not None else None

    probe_payload = {
        "probe_kind": "tn_contract_path",
        "mode": "exact_tn",
        "objective": config.objective,
        "precision": config.precision,
        "workspace_gb": config.workspace_gb,
        "cache_workspace_gb": config.cache_workspace_gb,
        "hyper_samples": config.hyper_samples,
        "autotune": config.autotune,
        "reuse_cache": config.reuse_cache,
        "mpi_ranks": config.mpi_ranks,
        "gpu_arch_target": config.gpu_arch_target,
        "probe_strategy": config.probe_strategy,
        "predicted_peak_gb": round((largest_intermediate or 0.0) * np.dtype(dtype).itemsize / (1024 ** 3), 9) if largest_intermediate else None,
        "predicted_error": 0.0,
        "optimizer_cost": optimizer_cost,
        "largest_intermediate": largest_intermediate,
        "num_slices": num_slices,
        "raw_info_json": {
            **raw,
            "backend": backend,
            "path_length": path_length,
            "error_message": error_message,
            "probe_version": PROBE_VERSION,
        },
        "status": status,
    }
    probe_payload["probe_id"] = "probe_" + sha256_text(canonical_json({
        "workload_id": workload_manifest["ids"]["workload_id"],
        "probe": probe_payload,
    }))[:16]
    return probe_payload


__all__ = ["PROBE_VERSION", "ProbeConfig", "run_exact_tn_probe"]
