from __future__ import annotations

from typing import Any

import math
import networkx as nx

from .utils import canonical_json, sha256_text


FEATURE_EXTRACTOR_VERSION = "aqs.features.v0"


def _statevec_memory_bytes(n_qubits: int, bytes_per_amplitude: int) -> int:
    return int((2 ** n_qubits) * bytes_per_amplitude)


def _graph_from_json(summary: dict[str, Any]) -> nx.Graph:
    graph = nx.Graph()
    node_count = int(summary.get("node_count", 0))
    graph.add_nodes_from(range(node_count))
    for edge in summary.get("edges", []):
        if len(edge) == 2:
            graph.add_edge(int(edge[0]), int(edge[1]))
    return graph


def _graph_features(summary: dict[str, Any]) -> dict[str, Any]:
    graph = _graph_from_json(summary)
    if graph.number_of_nodes() == 0:
        return {
            "node_count": 0,
            "edge_count": 0,
            "avg_degree": 0.0,
            "max_degree": 0,
            "density": 0.0,
            "component_count": 0,
            "cutwidth_proxy": 0,
            "treewidth_proxy": None,
        }

    density = nx.density(graph) if graph.number_of_nodes() > 1 else 0.0
    component_count = nx.number_connected_components(graph)
    ordering = list(range(graph.number_of_nodes()))
    cutwidth_proxy = 0
    position = {node: idx for idx, node in enumerate(ordering)}
    for split in range(graph.number_of_nodes() - 1):
        left = {node for node, idx in position.items() if idx <= split}
        crossing = sum(1 for u, v in graph.edges() if (u in left) != (v in left))
        cutwidth_proxy = max(cutwidth_proxy, crossing)
    try:
        tw, _ = nx.approximation.treewidth_min_fill_in(graph)
    except Exception:
        tw = None
    degrees = [deg for _, deg in graph.degree()]
    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "avg_degree": round(sum(degrees) / len(degrees), 6) if degrees else 0.0,
        "max_degree": max(degrees) if degrees else 0,
        "density": round(float(density), 6),
        "component_count": component_count,
        "cutwidth_proxy": cutwidth_proxy,
        "treewidth_proxy": tw,
    }


def extract_feature_snapshot(workload_manifest: dict[str, Any], normalized_ir: dict[str, Any]) -> dict[str, Any]:
    gate_hist = normalized_ir["gate_hist_json"]
    total_gates = sum(int(v) for k, v in gate_hist.items() if k != "measure")
    static_features = {
        "family_id": workload_manifest["family_id"],
        "semantic_target": workload_manifest["semantic_target"],
        "reference_tier": workload_manifest["reference_tier"],
        "split_tag": workload_manifest["split_tag"],
        "repeat_count_hint": workload_manifest["repeat_count_hint"],
        "n_qubits": normalized_ir["n_qubits"],
        "depth": normalized_ir["depth"],
        "moments": normalized_ir["moments"],
        "measurement_count": normalized_ir["measurement_count"],
        "reset_count": normalized_ir["reset_count"],
        "two_qubit_density": normalized_ir["two_qubit_density"],
        "non_clifford_fraction": normalized_ir["non_clifford_fraction"],
        "clifford_valid": normalized_ir["clifford_valid"],
        "total_gate_count": total_gates,
        "gate_hist": gate_hist,
        "observable_count": int((normalized_ir.get("observable_json") or {}).get("observable_count", 0)),
        "noise_present": normalized_ir.get("noise_json") is not None,
    }
    graph_features = _graph_features(normalized_ir.get("interaction_graph_json") or {})
    payload = {
        "workload_id": workload_manifest["ids"]["workload_id"],
        "extractor_version": FEATURE_EXTRACTOR_VERSION,
        "static_features": static_features,
        "graph_features": graph_features,
        "statevec_mem_est_fp32_bytes": _statevec_memory_bytes(normalized_ir["n_qubits"], 8),
        "statevec_mem_est_fp64_bytes": _statevec_memory_bytes(normalized_ir["n_qubits"], 16),
        "family_label": workload_manifest["family_id"],
    }
    payload["feature_id"] = "feat_" + sha256_text(canonical_json(payload))[:16]
    return payload


__all__ = ["FEATURE_EXTRACTOR_VERSION", "extract_feature_snapshot"]
