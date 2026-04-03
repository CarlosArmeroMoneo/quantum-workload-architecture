from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .exact_tn_targets import ExecutionTargetError, canonical_execution_target
from .source_adapters import SourceLoadError, load_circuit_summary


IMPLEMENTED_WORKFLOW_FAMILIES = {
    "dense_universal",
    "qaoa_graph",
    "trotter_1d",
    "grid_2d_shallow",
}

IMPLEMENTED_SOURCE_FORMATS = {"qiskit", "normalized_ir"}
IMPLEMENTED_SEMANTIC_TARGETS = {"state", "amplitude", "batched_amplitudes", "expectation"}
REAL_SOURCE_FORMATS = {"qiskit"}
REAL_SEMANTIC_TARGETS = {"amplitude", "batched_amplitudes"}

IMPLEMENTED_SUPPORT = {
    "manifest_ontology": {
        "source_formats": {"qiskit", "cirq", "stim", "cudaq", "normalized_ir"},
        "semantic_targets": {
            "state",
            "amplitude",
            "batched_amplitudes",
            "expectation",
            "samples",
            "detectors",
            "syndrome_summary",
        },
        "families": {
            "dense_universal",
            "qaoa_graph",
            "trotter_1d",
            "grid_2d_shallow",
            "noisy_observable",
            "qec_clifford",
            "repeated_sweep",
        },
    },
    "normalization": {
        "source_formats": IMPLEMENTED_SOURCE_FORMATS,
    },
    "structural_probe": {
        "source_formats": IMPLEMENTED_SOURCE_FORMATS,
        "semantic_targets": IMPLEMENTED_SEMANTIC_TARGETS,
        "normalized_ir_families": IMPLEMENTED_WORKFLOW_FAMILIES,
    },
    "real_execution": {
        "source_formats": REAL_SOURCE_FORMATS,
        "semantic_targets": REAL_SEMANTIC_TARGETS,
        "modes": {"exact_tn"},
        "distribution": "single_gpu_only",
    },
    "profiler_reduction": {
        "nsys": "implemented",
        "ncu": "implemented_but_metrics_thin",
    },
    "architecture_nomination": {
        "families": {"launch_overhead", "memory_bandwidth", "planner_roi", "reuse_cache", "communication", "memory_capacity"},
        "real_profiler_backed": True,
    },
}

CAPABILITY_PROOF_PATHS = {
    "truth_pass": "docs/reports/current_state_truth_pass.md",
    "real_execution": "docs/reports/first_real_profiler_slice_index.md",
    "canonical_nsys": "evidence/first_real_profiler_slice/real_ghz3_amplitude.nsys.f6bc40e76bb947a6.execution.json",
    "canonical_ncu": "evidence/first_real_profiler_slice/real_dense_ring6_batched.ncu.0e70e7aabe3342c1.profile_summary.json",
}


@dataclass(frozen=True)
class CapabilityRow:
    area: str
    schema_allows: str
    implemented: str
    measured_evidence: str
    proof_path: str
    readme_claim: str


CAPABILITY_MATRIX: tuple[CapabilityRow, ...] = (
    CapabilityRow(
        area="Manifest ontology",
        schema_allows="`qiskit`, `cirq`, `stim`, `cudaq`, `normalized_ir`; broad semantic targets",
        implemented="Broad schema only; executable implementation is narrower",
        measured_evidence="N/A",
        proof_path=CAPABILITY_PROOF_PATHS["truth_pass"],
        readme_claim="Describe breadth as schema vocabulary, not working backend support.",
    ),
    CapabilityRow(
        area="Normalize + features",
        schema_allows="All workload manifests",
        implemented="`qiskit` OpenQASM2 imports and family-backed `normalized_ir` manifests",
        measured_evidence="Yes",
        proof_path=CAPABILITY_PROOF_PATHS["real_execution"],
        readme_claim="Claim deterministic normalization for the implemented source paths only.",
    ),
    CapabilityRow(
        area="Structural probe + planner",
        schema_allows="Any benchmark/workload combination",
        implemented="`qiskit` or supported `normalized_ir` families with `state`, `amplitude`, `batched_amplitudes`, `expectation`",
        measured_evidence="Yes",
        proof_path=CAPABILITY_PROOF_PATHS["real_execution"],
        readme_claim="Claim exact-TN planning for the implemented subset only.",
    ),
    CapabilityRow(
        area="Real cuTensorNet execution",
        schema_allows="Any manifest can declare real intent",
        implemented="Single-GPU `qiskit` workloads for `amplitude` and `batched_amplitudes` only",
        measured_evidence="Yes",
        proof_path=CAPABILITY_PROOF_PATHS["canonical_nsys"],
        readme_claim="Claim real measured execution only for the single-GPU Qiskit/OpenQASM2 path.",
    ),
    CapabilityRow(
        area="Profiler reduction",
        schema_allows="Profiler metadata can be attached to runs",
        implemented="Nsight Systems reduction is mature; Nsight Compute reduction exists but remains metrics-thin",
        measured_evidence="Yes",
        proof_path=CAPABILITY_PROOF_PATHS["canonical_ncu"],
        readme_claim="Claim real profiler-backed summaries; note NCU depth limits explicitly.",
    ),
    CapabilityRow(
        area="Architecture nominations",
        schema_allows="Any profiled run can be analyzed",
        implemented="Profiler-backed nominations for launch/setup, memory bandwidth, reuse, planner ROI, capacity, and communication",
        measured_evidence="Yes",
        proof_path=CAPABILITY_PROOF_PATHS["real_execution"],
        readme_claim="Claim measured nomination reasoning, not exhaustive architecture diagnosis.",
    ),
)


def capability_matrix_rows() -> list[dict[str, str]]:
    return [
        {
            "area": row.area,
            "schema_allows": row.schema_allows,
            "implemented": row.implemented,
            "measured_evidence": row.measured_evidence,
            "proof_path": row.proof_path,
            "readme_claim": row.readme_claim,
        }
        for row in CAPABILITY_MATRIX
    ]


def validate_implemented_workload(manifest: dict[str, Any]) -> list[str]:
    if manifest.get("api_version") != "aqs.workload.v1":
        return []

    errors: list[str] = []
    source_format = str(manifest.get("source_format") or "")
    semantic_target = str(manifest.get("semantic_target") or "")
    family_id = str(manifest.get("family_id") or "")

    if source_format not in IMPLEMENTED_SOURCE_FORMATS:
        errors.append(
            f"implemented mode supports source_format in {sorted(IMPLEMENTED_SOURCE_FORMATS)}, got {source_format!r}"
        )
        return errors

    if semantic_target not in IMPLEMENTED_SEMANTIC_TARGETS:
        errors.append(
            f"implemented mode supports semantic_target in {sorted(IMPLEMENTED_SEMANTIC_TARGETS)}, got {semantic_target!r}"
        )

    if source_format == "normalized_ir" and family_id not in IMPLEMENTED_WORKFLOW_FAMILIES:
        errors.append(
            "implemented mode supports normalized_ir execution for family_id in "
            f"{sorted(IMPLEMENTED_WORKFLOW_FAMILIES)}, got {family_id!r}"
        )

    if source_format == "qiskit":
        try:
            load_circuit_summary(manifest)
        except SourceLoadError as exc:
            errors.append(f"implemented mode could not load the qiskit/OpenQASM2 source: {exc}")

    return errors


def validate_real_workload(manifest: dict[str, Any]) -> list[str]:
    if manifest.get("api_version") != "aqs.workload.v1":
        return []

    errors: list[str] = []
    source_format = str(manifest.get("source_format") or "")
    semantic_target = str(manifest.get("semantic_target") or "")

    if source_format not in REAL_SOURCE_FORMATS:
        errors.append(f"real mode supports source_format in {sorted(REAL_SOURCE_FORMATS)}, got {source_format!r}")
        return errors

    if semantic_target not in REAL_SEMANTIC_TARGETS:
        errors.append(
            f"real mode supports semantic_target in {sorted(REAL_SEMANTIC_TARGETS)}, got {semantic_target!r}"
        )
        return errors

    try:
        summary = load_circuit_summary(manifest)
    except SourceLoadError as exc:
        errors.append(f"real mode could not load the qiskit/OpenQASM2 source: {exc}")
        return errors

    if summary is None:
        errors.append("real mode requires an imported circuit source")
        return errors

    try:
        canonical_execution_target(manifest)
    except ExecutionTargetError as exc:
        errors.append(exc.message)

    if summary.reset_count:
        errors.append("real mode does not support reset operations")

    max_unitary_layer = max((op.layer for op in summary.operations if op.name not in {"measure", "reset"}), default=-1)
    for op in summary.operations:
        if op.name == "measure" and op.layer < max_unitary_layer:
            errors.append("real mode does not support intermediate measurements")
            break
    for op in summary.operations:
        if op.name in {"measure", "reset"}:
            continue
        if len(op.qubits) not in {1, 2}:
            errors.append(f"real mode does not support imported gate arity {len(op.qubits)} for gate {op.name!r}")
            break

    return errors


__all__ = [
    "CAPABILITY_MATRIX",
    "CAPABILITY_PROOF_PATHS",
    "IMPLEMENTED_SEMANTIC_TARGETS",
    "IMPLEMENTED_SOURCE_FORMATS",
    "IMPLEMENTED_SUPPORT",
    "IMPLEMENTED_WORKFLOW_FAMILIES",
    "REAL_SEMANTIC_TARGETS",
    "REAL_SOURCE_FORMATS",
    "CapabilityRow",
    "capability_matrix_rows",
    "validate_implemented_workload",
    "validate_real_workload",
]
