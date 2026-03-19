from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .normalize import SyntheticGate
from .source_adapters import CircuitSummary


@dataclass(frozen=True)
class ExecutionTargetSpec:
    kind: str
    bitstring: str | None = None
    fixed_qubits: dict[int, int] | None = None


class ExecutionTargetError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _fresh_label(counter: list[int]) -> int:
    label = counter[0]
    counter[0] += 1
    return label


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


def canonical_execution_target(manifest: dict[str, Any]) -> dict[str, Any]:
    target = manifest.get("execution_target")
    if not isinstance(target, dict):
        raise ExecutionTargetError("missing_execution_target", "execution_target is required for this execution path")
    kind = str(target.get("kind") or "")
    if kind == "amplitude":
        bitstring = target.get("bitstring")
        if not isinstance(bitstring, str) or not bitstring:
            raise ExecutionTargetError("invalid_execution_target", "execution_target.bitstring must be provided for amplitude targets")
        return {"kind": "amplitude", "bitstring": bitstring}
    if kind == "batched_amplitudes":
        fixed_qubits = target.get("fixed_qubits")
        if not isinstance(fixed_qubits, dict):
            raise ExecutionTargetError("invalid_execution_target", "execution_target.fixed_qubits must be provided for batched_amplitudes")
        canonical = {int(key): int(value) for key, value in sorted(fixed_qubits.items(), key=lambda item: int(item[0]))}
        return {"kind": "batched_amplitudes", "fixed_qubits": canonical}
    raise ExecutionTargetError("invalid_execution_target", f"unsupported execution_target.kind {kind!r}")


def execution_target_spec(manifest: dict[str, Any]) -> ExecutionTargetSpec:
    target = canonical_execution_target(manifest)
    return ExecutionTargetSpec(
        kind=target["kind"],
        bitstring=target.get("bitstring"),
        fixed_qubits=target.get("fixed_qubits"),
    )


def target_to_fixed_map(manifest: dict[str, Any], *, n_qubits: int) -> dict[int, int]:
    spec = execution_target_spec(manifest)
    if spec.kind == "amplitude":
        if spec.bitstring is None:
            raise ExecutionTargetError("invalid_execution_target", "amplitude target is missing a bitstring")
        if len(spec.bitstring) != n_qubits:
            raise ExecutionTargetError("invalid_execution_target", "execution_target.bitstring length does not match qubit count")
        return {idx: int(bit) for idx, bit in enumerate(spec.bitstring)}
    fixed_qubits = spec.fixed_qubits or {}
    for qubit, bit in fixed_qubits.items():
        if qubit < 0 or qubit >= n_qubits:
            raise ExecutionTargetError("invalid_execution_target", f"execution_target.fixed_qubits[{qubit}] is out of range")
        if bit not in {0, 1}:
            raise ExecutionTargetError("invalid_execution_target", f"execution_target.fixed_qubits[{qubit}] must be 0 or 1")
    return dict(sorted(fixed_qubits.items()))


def build_reference_interleaved_from_summary(summary: CircuitSummary, manifest: dict[str, Any], dtype: np.dtype) -> tuple[list[Any], dict[str, Any]]:
    schedule = _schedule_from_circuit_summary(summary)
    operands, labels, current = _build_forward_network(schedule, summary.n_qubits, dtype)
    fixed_map = target_to_fixed_map(manifest, n_qubits=summary.n_qubits)

    output_labels: list[int] = []
    for qubit in range(summary.n_qubits):
        if qubit in fixed_map:
            basis = np.zeros((2,), dtype=dtype)
            basis[int(fixed_map[qubit])] = 1
            operands.append(basis)
            labels.append([current[qubit]])
        else:
            output_labels.append(current[qubit])

    interleaved: list[Any] = []
    for operand, modes in zip(operands, labels):
        interleaved.extend([operand, modes])
    interleaved.append(output_labels)
    return interleaved, {
        "tensor_count": len(operands),
        "output_rank": len(output_labels),
        "fixed_qubits": fixed_map,
        "target_kind": manifest.get("execution_target", {}).get("kind"),
    }


__all__ = [
    "ExecutionTargetError",
    "ExecutionTargetSpec",
    "build_reference_interleaved_from_summary",
    "canonical_execution_target",
    "execution_target_spec",
    "target_to_fixed_map",
]
