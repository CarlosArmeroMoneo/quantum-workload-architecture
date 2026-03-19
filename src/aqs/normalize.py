from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import math

import networkx as nx

from .source_adapters import load_circuit_summary, summary_to_ir_fields
from .utils import canonical_json, sha256_text


IR_SCHEMA_VERSION = "aqs.normalized_ir.v0"


@dataclass(frozen=True)
class SyntheticGate:
    kind: str
    qubits: tuple[int, ...]
    layer: int


def _round_density(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(max(0.0, min(1.0, numerator / denominator)), 6)


def _hash_ir(payload: dict[str, Any]) -> str:
    return "ir_" + sha256_text(canonical_json(payload))[:16]


def _edge_list(graph: nx.Graph) -> list[list[int]]:
    return [[int(u), int(v)] for u, v in sorted(graph.edges())]


def _graph_summary(graph: nx.Graph, kind: str, max_edges_inline: int = 128) -> dict[str, Any]:
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    degrees = [deg for _, deg in graph.degree()] if node_count else []
    avg_degree = round(sum(degrees) / node_count, 6) if node_count else 0.0
    density = nx.density(graph) if node_count > 1 else 0.0
    summary: dict[str, Any] = {
        "kind": kind,
        "node_count": node_count,
        "edge_count": edge_count,
        "avg_degree": round(avg_degree, 6),
        "max_degree": max(degrees) if degrees else 0,
        "density": round(float(density), 6),
    }
    if edge_count <= max_edges_inline:
        summary["edges"] = _edge_list(graph)
    return summary


def graph_from_family(family_id: str, params: dict[str, Any], seed: int | None = None) -> nx.Graph:
    if family_id == "dense_universal":
        n = int(params["n_qubits"])
        topology = params["topology"]
        if topology == "ring":
            return nx.cycle_graph(n)
        if topology == "all_to_all":
            return nx.complete_graph(n)
        if topology == "grid":
            rows = max(1, int(math.floor(math.sqrt(n))))
            cols = int(math.ceil(n / rows))
            grid = nx.grid_2d_graph(rows, cols)
            mapping = {node: idx for idx, node in enumerate(sorted(grid.nodes()))}
            g = nx.relabel_nodes(grid, mapping)
            # trim unused nodes for non-square embeddings
            if g.number_of_nodes() > n:
                g.remove_nodes_from([i for i in range(n, g.number_of_nodes())])
            return g
        raise ValueError(f"Unsupported topology: {topology}")

    if family_id == "qaoa_graph":
        n = int(params["n_qubits"])
        graph_family = params["graph_family"]
        degree = int(params["graph_degree"])
        if graph_family == "ring":
            return nx.cycle_graph(n)
        if graph_family == "2d_grid":
            rows = max(1, int(math.floor(math.sqrt(n))))
            cols = int(math.ceil(n / rows))
            grid = nx.grid_2d_graph(rows, cols)
            mapping = {node: idx for idx, node in enumerate(sorted(grid.nodes()))}
            g = nx.relabel_nodes(grid, mapping)
            if g.number_of_nodes() > n:
                g.remove_nodes_from([i for i in range(n, g.number_of_nodes())])
            return g
        if graph_family == "erdos_renyi":
            p = min(1.0, max(0.0, degree / max(1, n - 1)))
            return nx.erdos_renyi_graph(n, p, seed=seed)
        if graph_family == "random_regular":
            degree = min(degree, n - 1)
            if (n * degree) % 2 == 1:
                degree = max(0, degree - 1)
            return nx.random_regular_graph(degree, n, seed=seed)
        if graph_family == "barabasi":
            m = max(1, min(degree, n - 1))
            return nx.barabasi_albert_graph(n, m, seed=seed)
        raise ValueError(f"Unsupported graph_family: {graph_family}")

    if family_id == "trotter_1d":
        n = int(params["n_qubits"])
        boundary = params["boundary_condition"]
        graph = nx.path_graph(n)
        if boundary == "periodic" and n > 2:
            graph.add_edge(0, n - 1)
        return graph

    if family_id == "grid_2d_shallow":
        rows = int(params["rows"])
        cols = int(params["cols"])
        grid = nx.grid_2d_graph(rows, cols)
        mapping = {node: idx for idx, node in enumerate(sorted(grid.nodes()))}
        return nx.relabel_nodes(grid, mapping)

    if family_id == "noisy_observable":
        n = int(params["n_qubits"])
        return nx.cycle_graph(n)

    if family_id == "qec_clifford":
        distance = int(params["distance"])
        data = distance * distance
        anc = max(1, distance - 1) * distance
        total = data + anc
        graph = nx.grid_2d_graph(distance, distance)
        mapping = {node: idx for idx, node in enumerate(sorted(graph.nodes()))}
        g = nx.relabel_nodes(graph, mapping)
        next_idx = g.number_of_nodes()
        for q in range(data):
            if next_idx >= total:
                break
            g.add_node(next_idx)
            g.add_edge(q, next_idx)
            next_idx += 1
        while g.number_of_nodes() < total:
            g.add_node(g.number_of_nodes())
        return g

    if family_id == "repeated_sweep":
        base = params["base_family"]
        nested = params.get("base_parameters", {})
        return graph_from_family(base, nested, seed=seed)

    raise ValueError(f"Unsupported family_id: {family_id}")


def _dense_universal_ir(manifest: dict[str, Any]) -> dict[str, Any]:
    params = manifest["parameters"]
    n = int(params["n_qubits"])
    depth = int(params["depth"])
    graph = graph_from_family("dense_universal", params, seed=manifest.get("seed"))
    density_factor = {"low": 0.35, "medium": 0.65, "high": 1.0}[params["two_qubit_density"]]
    twoq_per_layer = max(1, int(round(graph.number_of_edges() * density_factor))) if graph.number_of_edges() else 0
    twoq_count = twoq_per_layer * depth
    oneq_count = n * depth
    measurement_count = n if params["measurement_pattern"] == "terminal_all" else 0
    return {
        "schema_version": IR_SCHEMA_VERSION,
        "n_qubits": n,
        "depth": depth,
        "moments": depth,
        "gate_hist_json": {
            "u1q": oneq_count,
            "u2q": twoq_count,
            "measure": measurement_count,
        },
        "two_qubit_density": _round_density(twoq_count, max(1, oneq_count + twoq_count)),
        "non_clifford_fraction": 0.7,
        "clifford_valid": False,
        "measurement_count": measurement_count,
        "reset_count": 0,
        "noise_json": None,
        "observable_json": {
            "observable_count": 1 if manifest["semantic_target"] == "expectation" else 0,
            "target": manifest["semantic_target"],
        },
        "execution_target_json": manifest.get("execution_target"),
        "interaction_graph_json": _graph_summary(graph, kind=params["topology"]),
    }


def _qaoa_ir(manifest: dict[str, Any]) -> dict[str, Any]:
    params = manifest["parameters"]
    n = int(params["n_qubits"])
    rounds = int(params["p"])
    graph = graph_from_family("qaoa_graph", params, seed=manifest.get("seed"))
    edge_colors = nx.coloring.greedy_color(nx.line_graph(graph), strategy="largest_first") if graph.number_of_edges() else {}
    edge_layers = max(edge_colors.values(), default=-1) + 1 if edge_colors else 1
    twoq_count = graph.number_of_edges() * rounds
    oneq_count = n * rounds
    return {
        "schema_version": IR_SCHEMA_VERSION,
        "n_qubits": n,
        "depth": rounds * (edge_layers + 1),
        "moments": rounds * (edge_layers + 1),
        "gate_hist_json": {
            "cost_zz": twoq_count,
            "mixer_rx": oneq_count,
            "measure": 0,
        },
        "two_qubit_density": _round_density(twoq_count, max(1, oneq_count + twoq_count)),
        "non_clifford_fraction": 0.95,
        "clifford_valid": False,
        "measurement_count": 0,
        "reset_count": 0,
        "noise_json": None,
        "observable_json": {
            "observable_count": int(params["observable_count"]),
            "target": manifest["semantic_target"],
        },
        "execution_target_json": manifest.get("execution_target"),
        "interaction_graph_json": _graph_summary(graph, kind=params["graph_family"]),
    }


def _trotter_ir(manifest: dict[str, Any]) -> dict[str, Any]:
    params = manifest["parameters"]
    n = int(params["n_qubits"])
    steps = int(params["steps"])
    graph = graph_from_family("trotter_1d", params, seed=manifest.get("seed"))
    edge_colorings = nx.coloring.greedy_color(nx.line_graph(graph), strategy="largest_first") if graph.number_of_edges() else {}
    edge_layers = max(edge_colorings.values(), default=-1) + 1 if edge_colorings else 1
    twoq_count = graph.number_of_edges() * steps
    oneq_count = n * steps
    return {
        "schema_version": IR_SCHEMA_VERSION,
        "n_qubits": n,
        "depth": steps * (edge_layers + 1),
        "moments": steps * (edge_layers + 1),
        "gate_hist_json": {
            "local_field": oneq_count,
            "pair_term": twoq_count,
            "measure": 0,
        },
        "two_qubit_density": _round_density(twoq_count, max(1, oneq_count + twoq_count)),
        "non_clifford_fraction": 0.85,
        "clifford_valid": False,
        "measurement_count": 0,
        "reset_count": 0,
        "noise_json": None,
        "observable_json": {
            "observable_count": int(params["observable_count"]),
            "target": manifest["semantic_target"],
        },
        "execution_target_json": manifest.get("execution_target"),
        "interaction_graph_json": _graph_summary(graph, kind=f"1d_{params['boundary_condition']}"),
    }


def _grid_2d_ir(manifest: dict[str, Any]) -> dict[str, Any]:
    params = manifest["parameters"]
    rows = int(params["rows"])
    cols = int(params["cols"])
    layers = int(params["layers"])
    graph = graph_from_family("grid_2d_shallow", params, seed=manifest.get("seed"))
    n = rows * cols
    twoq_count = graph.number_of_edges() * layers
    oneq_count = n * layers
    return {
        "schema_version": IR_SCHEMA_VERSION,
        "n_qubits": n,
        "depth": layers * 2,
        "moments": layers * 2,
        "gate_hist_json": {
            "u1q": oneq_count,
            "entangler": twoq_count,
            "measure": 0,
        },
        "two_qubit_density": _round_density(twoq_count, max(1, oneq_count + twoq_count)),
        "non_clifford_fraction": 0.6,
        "clifford_valid": False,
        "measurement_count": 0,
        "reset_count": 0,
        "noise_json": None,
        "observable_json": {"observable_count": 1, "target": manifest["semantic_target"]},
        "execution_target_json": manifest.get("execution_target"),
        "interaction_graph_json": _graph_summary(graph, kind=params["entangler_pattern"]),
    }


def _noisy_observable_ir(manifest: dict[str, Any]) -> dict[str, Any]:
    params = manifest["parameters"]
    n = int(params["n_qubits"])
    depth = int(params["depth"])
    graph = graph_from_family("noisy_observable", params, seed=manifest.get("seed"))
    twoq_count = graph.number_of_edges() * depth
    oneq_count = n * depth
    return {
        "schema_version": IR_SCHEMA_VERSION,
        "n_qubits": n,
        "depth": depth,
        "moments": depth,
        "gate_hist_json": {
            "u1q": oneq_count,
            "u2q": twoq_count,
            "measure": 0,
        },
        "two_qubit_density": _round_density(twoq_count, max(1, oneq_count + twoq_count)),
        "non_clifford_fraction": 0.6,
        "clifford_valid": False,
        "measurement_count": 0,
        "reset_count": 0,
        "noise_json": {
            "model": params["noise_model"],
            "rate": float(params["noise_rate"]),
        },
        "observable_json": {
            "observable_count": int(params["observable_count"]),
            "target": manifest["semantic_target"],
        },
        "execution_target_json": manifest.get("execution_target"),
        "interaction_graph_json": _graph_summary(graph, kind="ring"),
    }


def _qec_ir(manifest: dict[str, Any]) -> dict[str, Any]:
    params = manifest["parameters"]
    distance = int(params["distance"])
    cycles = int(params["cycles"])
    graph = graph_from_family("qec_clifford", params, seed=manifest.get("seed"))
    n = graph.number_of_nodes()
    data_qubits = distance * distance
    ancilla_qubits = n - data_qubits
    twoq_count = graph.number_of_edges() * cycles
    oneq_count = ancilla_qubits * cycles
    detector_count = ancilla_qubits * cycles
    return {
        "schema_version": IR_SCHEMA_VERSION,
        "n_qubits": n,
        "depth": cycles * 3,
        "moments": cycles * 3,
        "gate_hist_json": {
            "clifford_1q": oneq_count,
            "clifford_2q": twoq_count,
            "measure": detector_count,
        },
        "two_qubit_density": _round_density(twoq_count, max(1, oneq_count + twoq_count)),
        "non_clifford_fraction": 0.0,
        "clifford_valid": True,
        "measurement_count": detector_count,
        "reset_count": detector_count,
        "noise_json": None,
        "observable_json": {
            "observable_count": detector_count,
            "target": manifest["semantic_target"],
        },
        "execution_target_json": manifest.get("execution_target"),
        "interaction_graph_json": _graph_summary(graph, kind=params["code_family"]),
    }


def normalize_workload_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    family_id = manifest["family_id"]

    if manifest.get("source_format") != "normalized_ir":
        summary = load_circuit_summary(manifest)
        if summary is None:
            raise ValueError(f"No source adapter could be loaded for source_format={manifest.get('source_format')!r}")
        ir = summary_to_ir_fields(summary, manifest)
    elif family_id == "dense_universal":
        ir = _dense_universal_ir(manifest)
    elif family_id == "qaoa_graph":
        ir = _qaoa_ir(manifest)
    elif family_id == "trotter_1d":
        ir = _trotter_ir(manifest)
    elif family_id == "grid_2d_shallow":
        ir = _grid_2d_ir(manifest)
    elif family_id == "noisy_observable":
        ir = _noisy_observable_ir(manifest)
    elif family_id == "qec_clifford":
        ir = _qec_ir(manifest)
    elif family_id == "repeated_sweep":
        raise NotImplementedError("repeated_sweep should be materialized from a concrete base-family workload in a later phase")
    else:
        raise ValueError(f"Unsupported family: {family_id}")

    payload = {key: ir[key] for key in sorted(ir.keys()) if key != "ir_hash"}
    ir["ir_hash"] = _hash_ir(payload)
    return ir


__all__ = [
    "IR_SCHEMA_VERSION",
    "SyntheticGate",
    "graph_from_family",
    "normalize_workload_manifest",
]
