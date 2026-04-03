from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import re

import networkx as nx

from .cudaq_adapter import CudaqAdapterError, load_cudaq_program
from .paths import repo_root


@dataclass(frozen=True)
class CircuitOp:
    name: str
    qubits: tuple[int, ...]
    layer: int
    parameterized: bool = False
    raw_params: tuple[str, ...] = ()


@dataclass(frozen=True)
class CircuitSummary:
    source_kind: str
    loader: str
    n_qubits: int
    depth: int
    operations: tuple[CircuitOp, ...]
    measurement_count: int
    reset_count: int
    graph_kind: str = "imported"
    metadata: dict[str, Any] | None = None


_QREG_RE = re.compile(r"^qreg\s+([A-Za-z_][\w]*)\[(\d+)\]\s*;$")
_CREG_RE = re.compile(r"^creg\s+([A-Za-z_][\w]*)\[(\d+)\]\s*;$")
_MEASURE_RE = re.compile(r"^measure\s+([^\-]+)->\s*(.+);$")
_RESET_RE = re.compile(r"^reset\s+(.+);$")
_BARRIER_RE = re.compile(r"^barrier\s+(.+);$")
_GATE_RE = re.compile(r"^([A-Za-z_][\w]*)\s*(\(([^)]*)\))?\s+(.+);$")
_QARG_RE = re.compile(r"^([A-Za-z_][\w]*)\[(\d+)\]$")

_CLIFFORD_GATES = {
    "id", "i", "x", "y", "z", "h", "s", "sdg", "cx", "cy", "cz", "swap", "sx", "sxdg"
}


class SourceLoadError(RuntimeError):
    pass


def _resolve_path(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return repo_root() / path


def _clean_qasm_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        lines.append(line)
    return lines


def _parse_qarg(token: str, qreg_offsets: dict[str, int], qreg_sizes: dict[str, int]) -> int:
    token = token.strip()
    match = _QARG_RE.match(token)
    if not match:
        raise SourceLoadError(f"Unsupported qubit token: {token!r}")
    reg, index_text = match.groups()
    if reg not in qreg_offsets:
        raise SourceLoadError(f"Unknown qreg {reg!r}")
    index = int(index_text)
    if index < 0 or index >= qreg_sizes[reg]:
        raise SourceLoadError(f"Qubit index out of range for register {reg!r}: {index}")
    return qreg_offsets[reg] + index


def _schedule_layer(qubits: tuple[int, ...], last_layer: dict[int, int]) -> int:
    base = 0
    for q in qubits:
        base = max(base, last_layer.get(q, -1) + 1)
    for q in qubits:
        last_layer[q] = base
    return base


def parse_openqasm2_summary(text: str, *, source_kind: str = "qiskit") -> CircuitSummary:
    qreg_sizes: dict[str, int] = {}
    qreg_offsets: dict[str, int] = {}
    _creg_sizes: dict[str, int] = {}
    ops: list[CircuitOp] = []
    last_layer: dict[int, int] = {}
    total_qubits = 0
    saw_header = False

    for line in _clean_qasm_lines(text):
        if line.startswith("OPENQASM") or line.startswith("include "):
            saw_header = True
            continue

        qreg_match = _QREG_RE.match(line)
        if qreg_match:
            reg, size_text = qreg_match.groups()
            size = int(size_text)
            qreg_offsets[reg] = total_qubits
            qreg_sizes[reg] = size
            total_qubits += size
            continue

        creg_match = _CREG_RE.match(line)
        if creg_match:
            reg, size_text = creg_match.groups()
            _creg_sizes[reg] = int(size_text)
            continue

        barrier_match = _BARRIER_RE.match(line)
        if barrier_match:
            if total_qubits:
                barrier_qubits = [
                    _parse_qarg(token, qreg_offsets, qreg_sizes)
                    for token in barrier_match.group(1).split(",")
                ]
                synchronized = max((last_layer.get(q, -1) for q in barrier_qubits), default=-1)
                for q in barrier_qubits:
                    last_layer[q] = synchronized
            continue

        measure_match = _MEASURE_RE.match(line)
        if measure_match:
            qubit_token = measure_match.group(1).strip()
            q = _parse_qarg(qubit_token, qreg_offsets, qreg_sizes)
            layer = _schedule_layer((q,), last_layer)
            ops.append(CircuitOp(name="measure", qubits=(q,), layer=layer))
            continue

        reset_match = _RESET_RE.match(line)
        if reset_match:
            q = _parse_qarg(reset_match.group(1).strip(), qreg_offsets, qreg_sizes)
            layer = _schedule_layer((q,), last_layer)
            ops.append(CircuitOp(name="reset", qubits=(q,), layer=layer))
            continue

        gate_match = _GATE_RE.match(line)
        if gate_match:
            gate_name, _, params_text, args_text = gate_match.groups()
            arg_tokens = [token.strip() for token in args_text.split(",") if token.strip()]
            qubits = tuple(_parse_qarg(token, qreg_offsets, qreg_sizes) for token in arg_tokens)
            if not qubits:
                continue
            params = tuple(s.strip() for s in params_text.split(",")) if params_text else ()
            layer = _schedule_layer(qubits, last_layer)
            ops.append(CircuitOp(name=gate_name.lower(), qubits=qubits, layer=layer, parameterized=bool(params), raw_params=params))
            continue

        raise SourceLoadError(f"Unsupported or unparsable OpenQASM 2 statement: {line!r}")

    if total_qubits <= 0:
        raise SourceLoadError("No qreg declarations found in OpenQASM 2 source")

    depth = max((op.layer for op in ops), default=-1) + 1
    metadata = {
        "saw_header": saw_header,
        "operation_count": len(ops),
    }
    return CircuitSummary(
        source_kind=source_kind,
        loader="openqasm2",
        n_qubits=total_qubits,
        depth=depth,
        operations=tuple(ops),
        measurement_count=sum(1 for op in ops if op.name == "measure"),
        reset_count=sum(1 for op in ops if op.name == "reset"),
        graph_kind="imported_openqasm2",
        metadata=metadata,
    )


def _load_openqasm2_text(source: dict[str, Any]) -> str:
    loader = source.get("loader")
    if loader == "qasm2_file":
        if not source.get("path"):
            raise SourceLoadError("source.path is required for loader=qasm2_file")
        return _resolve_path(source["path"]).read_text(encoding="utf-8")
    if loader == "qasm2_inline":
        text = source.get("text")
        if not isinstance(text, str) or not text.strip():
            raise SourceLoadError("source.text is required for loader=qasm2_inline")
        return text
    raise SourceLoadError(f"Unsupported qiskit source loader: {loader!r}")


def _load_cudaq_summary(source: dict[str, Any]) -> CircuitSummary:
    loader = source.get("loader")
    if loader != "cudaq_python_file":
        raise SourceLoadError(f"Unsupported cudaq source loader: {loader!r}")
    if not source.get("path"):
        raise SourceLoadError("source.path is required for loader=cudaq_python_file")
    try:
        adapter_payload = load_cudaq_program(source["path"])
    except CudaqAdapterError as exc:
        raise SourceLoadError(str(exc)) from exc
    summary = parse_openqasm2_summary(adapter_payload["openqasm2"], source_kind=str(adapter_payload["source_kind"]))
    return replace(
        summary,
        loader="cudaq_python_file",
        graph_kind="imported_cudaq_adapter",
        metadata={
            **(summary.metadata or {}),
            "adapter_api_version": adapter_payload["api_version"],
            "adapter_program_name": adapter_payload["program_name"],
            "adapter_source_path": adapter_payload["path"],
            "adapter_metadata": adapter_payload["metadata"],
        },
    )


def load_circuit_summary(manifest: dict[str, Any]) -> CircuitSummary | None:
    source_format = manifest.get("source_format")
    if source_format == "normalized_ir":
        return None

    source = manifest.get("source") or {}
    if source_format == "qiskit":
        text = _load_openqasm2_text(source)
        return parse_openqasm2_summary(text, source_kind="qiskit")
    if source_format == "cudaq":
        return _load_cudaq_summary(source)

    raise SourceLoadError(f"Source format {source_format!r} is not implemented in this scaffold")


def maybe_load_qiskit_circuit(manifest: dict[str, Any]) -> Any | None:
    if manifest.get("source_format") != "qiskit":
        return None
    source = manifest.get("source") or {}
    loader = source.get("loader")
    try:
        import qiskit.qasm2 as qasm2
    except Exception:
        return None

    if loader == "qasm2_file" and source.get("path"):
        return qasm2.load(str(_resolve_path(source["path"])))
    if loader == "qasm2_inline" and source.get("text"):
        return qasm2.loads(str(source["text"]))
    return None


def interaction_graph_from_summary(summary: CircuitSummary) -> nx.Graph:
    graph: nx.Graph = nx.Graph()
    graph.add_nodes_from(range(summary.n_qubits))
    for op in summary.operations:
        if len(op.qubits) == 2:
            graph.add_edge(*op.qubits)
    return graph


def gate_hist_from_summary(summary: CircuitSummary) -> dict[str, int]:
    hist: dict[str, int] = {}
    for op in summary.operations:
        hist[op.name] = hist.get(op.name, 0) + 1
    return dict(sorted(hist.items()))


def _unitary_ops(summary: CircuitSummary) -> list[CircuitOp]:
    return [op for op in summary.operations if op.name not in {"measure", "reset", "barrier"}]


def non_clifford_fraction_from_summary(summary: CircuitSummary) -> float:
    unitary_ops = _unitary_ops(summary)
    if not unitary_ops:
        return 0.0
    non_clifford = 0
    for op in unitary_ops:
        if op.parameterized:
            non_clifford += 1
            continue
        if op.name not in _CLIFFORD_GATES:
            non_clifford += 1
    return round(non_clifford / len(unitary_ops), 6)


def clifford_valid_from_summary(summary: CircuitSummary) -> bool:
    if summary.reset_count:
        return False
    for op in _unitary_ops(summary):
        if op.parameterized or op.name not in _CLIFFORD_GATES:
            return False
    return True


def two_qubit_density_from_summary(summary: CircuitSummary) -> float:
    unitary_ops = _unitary_ops(summary)
    if not unitary_ops:
        return 0.0
    twoq = sum(1 for op in unitary_ops if len(op.qubits) == 2)
    return round(twoq / len(unitary_ops), 6)


def graph_summary_from_summary(summary: CircuitSummary, max_edges_inline: int = 128) -> dict[str, Any]:
    graph = interaction_graph_from_summary(summary)
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    degrees = [deg for _, deg in graph.degree()] if node_count else []
    avg_degree = round(sum(degrees) / node_count, 6) if node_count else 0.0
    density = nx.density(graph) if node_count > 1 else 0.0
    payload: dict[str, Any] = {
        "kind": summary.graph_kind,
        "node_count": node_count,
        "edge_count": edge_count,
        "avg_degree": round(avg_degree, 6),
        "max_degree": max(degrees) if degrees else 0,
        "density": round(float(density), 6),
    }
    if edge_count <= max_edges_inline:
        payload["edges"] = [[int(u), int(v)] for u, v in sorted(graph.edges())]
    return payload


def observable_json_for_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    params = manifest.get("parameters", {})
    target = manifest.get("semantic_target")
    observable_count = int(params.get("observable_count", 1 if target == "expectation" else 0))
    return {
        "observable_count": observable_count,
        "target": target,
    }


def summary_to_ir_fields(summary: CircuitSummary, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "aqs.normalized_ir.v0",
        "n_qubits": summary.n_qubits,
        "depth": summary.depth,
        "moments": summary.depth,
        "gate_hist_json": gate_hist_from_summary(summary),
        "two_qubit_density": two_qubit_density_from_summary(summary),
        "non_clifford_fraction": non_clifford_fraction_from_summary(summary),
        "clifford_valid": clifford_valid_from_summary(summary),
        "measurement_count": summary.measurement_count,
        "reset_count": summary.reset_count,
        "noise_json": manifest.get("noise_json"),
        "observable_json": observable_json_for_manifest(manifest),
        "execution_target_json": manifest.get("execution_target"),
        "interaction_graph_json": graph_summary_from_summary(summary),
        "source_summary_json": {
            "source_kind": summary.source_kind,
            "loader": summary.loader,
            "metadata": summary.metadata or {},
        },
    }


__all__ = [
    "CircuitOp",
    "CircuitSummary",
    "SourceLoadError",
    "clifford_valid_from_summary",
    "graph_summary_from_summary",
    "interaction_graph_from_summary",
    "load_circuit_summary",
    "maybe_load_qiskit_circuit",
    "non_clifford_fraction_from_summary",
    "observable_json_for_manifest",
    "parse_openqasm2_summary",
    "summary_to_ir_fields",
    "two_qubit_density_from_summary",
]
