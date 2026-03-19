from __future__ import annotations

from copy import deepcopy
from typing import Any

from .manifest import finalize_workload_manifest

GENERATOR_VERSION = "0.1.0"
FAMILY_VERSION = "0.1.0"


PRESETS: dict[str, dict[str, dict[str, Any]]] = {
    "dense_universal": {
        "smoke": {
            "source_format": "normalized_ir",
            "semantic_target": "amplitude",
            "reference_tier": "smoke",
            "split_tag": "demo",
            "repeat_count_hint": 1,
            "parameters": {
                "n_qubits": 12,
                "depth": 4,
                "topology": "ring",
                "two_qubit_density": "medium",
                "measurement_pattern": "terminal_all",
            },
        },
        "boundary": {
            "source_format": "normalized_ir",
            "semantic_target": "expectation",
            "reference_tier": "boundary",
            "split_tag": "train",
            "repeat_count_hint": 8,
            "parameters": {
                "n_qubits": 24,
                "depth": 16,
                "topology": "grid",
                "two_qubit_density": "high",
                "measurement_pattern": "terminal_observable_only",
            },
        },
    },
    "qaoa_graph": {
        "smoke": {
            "source_format": "normalized_ir",
            "semantic_target": "expectation",
            "reference_tier": "smoke",
            "split_tag": "demo",
            "repeat_count_hint": 4,
            "parameters": {
                "n_qubits": 12,
                "graph_family": "ring",
                "graph_degree": 2,
                "p": 1,
                "observable_count": 1,
            },
        },
        "heldout_family": {
            "source_format": "normalized_ir",
            "semantic_target": "expectation",
            "reference_tier": "boundary",
            "split_tag": "heldout_family",
            "repeat_count_hint": 16,
            "parameters": {
                "n_qubits": 24,
                "graph_family": "barabasi",
                "graph_degree": 3,
                "p": 3,
                "observable_count": 8,
            },
        },
    },
    "trotter_1d": {
        "smoke": {
            "source_format": "normalized_ir",
            "semantic_target": "expectation",
            "reference_tier": "smoke",
            "split_tag": "demo",
            "repeat_count_hint": 10,
            "parameters": {
                "n_qubits": 16,
                "steps": 4,
                "hamiltonian_pattern": "xxz",
                "boundary_condition": "open",
                "observable_count": 2,
            },
        },
        "mps_favorable": {
            "source_format": "normalized_ir",
            "semantic_target": "expectation",
            "reference_tier": "boundary",
            "split_tag": "train",
            "repeat_count_hint": 64,
            "parameters": {
                "n_qubits": 64,
                "steps": 16,
                "hamiltonian_pattern": "transverse_field_ising",
                "boundary_condition": "open",
                "observable_count": 8,
            },
        },
    },
}


def generate_workload_manifest(family: str, preset: str, seed: int, notes: str | None = None) -> dict[str, Any]:
    if family not in PRESETS:
        raise ValueError(f"Unknown family: {family}")
    if preset not in PRESETS[family]:
        raise ValueError(f"Unknown preset '{preset}' for family '{family}'")

    template = deepcopy(PRESETS[family][preset])
    manifest: dict[str, Any] = {
        "api_version": "aqs.workload.v1",
        "family_id": family,
        "family_version": FAMILY_VERSION,
        "generator_name": family,
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        **template,
    }
    if notes:
        manifest["notes"] = notes
    return finalize_workload_manifest(manifest)
