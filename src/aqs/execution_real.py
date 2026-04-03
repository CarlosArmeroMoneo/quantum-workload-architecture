from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
import inspect
import statistics
import time
from typing import Any

import numpy as np

from .accuracy import build_accuracy_eval
from .doctor import collect_system_profile
from .exact_tn_targets import (
    ExecutionTargetError,
    canonical_execution_target,
)
from .graph_modes import normalize_graph_mode
from .nvtx import NVTX_PHASE_VERSION
from .profiling import PhaseRecorder
from .source_adapters import load_circuit_summary, maybe_load_qiskit_circuit
from .utils import canonical_json, sha256_text

REAL_EXECUTION_SOURCE = "cuquantum_tensornet_gpu"
REAL_EXECUTION_VERSION = "aqs.execution.real.v2"

REAL_RECOVERABLE_CODES = {
    "missing_gpu",
    "missing_cupy",
    "missing_cuquantum",
    "missing_qiskit",
    "unsupported_source_format",
    "unsupported_semantic_target",
    "missing_execution_target",
    "invalid_execution_target",
    "reset_present",
    "intermediate_measurement_present",
    "unsupported_gate_arity",
    "graph_capture_unavailable",
    "graph_capture_failed",
    "graph_launch_failed",
}


class RealExecutionError(RuntimeError):
    def __init__(self, code: str, message: str, *, status: str = "runtime_error", recoverable: bool | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.recoverable = code in REAL_RECOVERABLE_CODES if recoverable is None else recoverable


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_output_digest(result: Any) -> str:
    if hasattr(result, "get"):
        try:
            result = result.get()
        except Exception:
            pass
    if hasattr(result, "tobytes"):
        try:
            payload = result.tobytes()[:256]
            return "out_" + sha256_text(payload.hex())[:16]
        except Exception:
            pass
    return "out_" + sha256_text(repr(result))[:16]


def _require_real_capability(system_profile: dict[str, Any], module_name: str, code: str, message: str) -> None:
    if not system_profile.get(module_name):
        raise RealExecutionError(code, message)


def validate_real_execution_request(manifest: dict[str, Any], *, system_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    system_profile = system_profile or collect_system_profile()
    if manifest.get("source_format") != "qiskit":
        raise RealExecutionError("unsupported_source_format", "real cuTensorNet execution currently supports source_format='qiskit' only")
    if manifest.get("semantic_target") not in {"amplitude", "batched_amplitudes"}:
        raise RealExecutionError(
            "unsupported_semantic_target",
            "real cuTensorNet execution currently supports semantic_target in {'amplitude', 'batched_amplitudes'} only",
        )
    if not system_profile.get("gpu_present"):
        raise RealExecutionError("missing_gpu", "real cuTensorNet execution requires a visible GPU")
    _require_real_capability(system_profile, "cupy_present", "missing_cupy", "real cuTensorNet execution requires CuPy")
    _require_real_capability(system_profile, "cuquantum_present", "missing_cuquantum", "real cuTensorNet execution requires cuQuantum Python")
    _require_real_capability(system_profile, "qiskit_present", "missing_qiskit", "real cuTensorNet execution requires Qiskit for OpenQASM2 import")

    summary = load_circuit_summary(manifest)
    if summary is None:
        raise RealExecutionError("unsupported_source_format", "could not materialize the imported circuit summary")
    if summary.reset_count:
        raise RealExecutionError("reset_present", "reset operations are not supported for real exact-TN execution")

    max_unitary_layer = max((op.layer for op in summary.operations if op.name not in {"measure", "reset"}), default=-1)
    for op in summary.operations:
        if op.name == "measure" and op.layer < max_unitary_layer:
            raise RealExecutionError("intermediate_measurement_present", "intermediate measurements are not supported for real exact-TN execution")
        if op.name not in {"measure", "reset"} and len(op.qubits) not in {1, 2}:
            raise RealExecutionError(
                "unsupported_gate_arity",
                f"unsupported imported gate arity {len(op.qubits)} for gate {op.name!r} in real exact-TN execution",
            )

    try:
        execution_target = canonical_execution_target(manifest)
    except ExecutionTargetError as exc:
        raise RealExecutionError(exc.code, exc.message) from exc

    return {
        "summary": summary,
        "execution_target": execution_target,
        "system_profile": system_profile,
    }


def _import_real_stack() -> tuple[Any, Any, Any]:
    import cupy
    try:
        from cuquantum.tensornet import CircuitToEinsum, Network
    except ImportError:  # pragma: no cover - compatibility with older cuQuantum wheels
        from cuquantum import Network
        from cuquantum.tensornet import CircuitToEinsum

    return cupy, Network, CircuitToEinsum


def _sync_cupy(cupy: Any) -> None:
    stream = getattr(cupy.cuda, "get_current_stream", None)
    if callable(stream):
        stream().synchronize()
        return
    null_stream = getattr(getattr(cupy.cuda, "Stream", None), "null", None)
    if null_stream is not None:
        null_stream.synchronize()


def _current_cupy_stream(cupy: Any) -> Any:
    stream_getter = getattr(cupy.cuda, "get_current_stream", None)
    if callable(stream_getter):
        stream = stream_getter()
        if stream is not None:
            return stream
    null_stream = getattr(getattr(cupy.cuda, "Stream", None), "null", None)
    if null_stream is not None:
        return null_stream
    raise RealExecutionError("graph_capture_unavailable", "CUDA Graph capture requires a CuPy stream implementation with capture support")


def _begin_graph_capture(stream: Any, cupy: Any) -> None:
    try:
        stream.begin_capture()
        return
    except TypeError:
        capture_mode = getattr(getattr(cupy.cuda, "stream", None), "CaptureMode", None)
        for candidate in ("RELAXED", "GLOBAL"):
            mode = getattr(capture_mode, candidate, None)
            if mode is None:
                continue
            stream.begin_capture(mode)
            return
    except AttributeError as exc:
        raise RealExecutionError("graph_capture_unavailable", "CUDA Graph capture requested but this CuPy runtime does not expose stream capture APIs") from exc
    raise RealExecutionError("graph_capture_unavailable", "CUDA Graph capture requested but no compatible stream capture mode was found")


def _instantiate_captured_graph(graph: Any) -> Any:
    instantiate = getattr(graph, "instantiate", None)
    if callable(instantiate):
        return instantiate()
    return graph


def _capture_contract_graph(cupy: Any, contract_call: Any) -> tuple[Any, Any]:
    try:
        stream = _current_cupy_stream(cupy)
        _begin_graph_capture(stream, cupy)
        capture_result = contract_call(release_workspace=False)
        graph = stream.end_capture()
        _sync_cupy(cupy)
        return _instantiate_captured_graph(graph), capture_result
    except RealExecutionError:
        raise
    except AttributeError as exc:
        raise RealExecutionError("graph_capture_unavailable", "CUDA Graph capture requested but the current CuPy stream does not support begin/end capture") from exc
    except Exception as exc:
        raise RealExecutionError("graph_capture_failed", f"CUDA Graph capture failed: {exc}") from exc


def _launch_captured_graph(cupy: Any, captured_graph: Any) -> Any:
    launch_method = None
    for candidate in ("launch", "replay", "run"):
        maybe_method = getattr(captured_graph, candidate, None)
        if callable(maybe_method):
            launch_method = maybe_method
            break
    if launch_method is None:
        raise RealExecutionError("graph_launch_failed", "captured CUDA Graph does not expose a callable launch/replay entrypoint")

    stream = _current_cupy_stream(cupy)
    launch_attempts = [
        ((), {}),
        ((stream,), {}),
        ((), {"stream": stream}),
    ]
    last_error: Exception | None = None
    for args, kwargs in launch_attempts:
        try:
            result = launch_method(*args, **kwargs)
            _sync_cupy(cupy)
            return result
        except TypeError as exc:
            last_error = exc
        except Exception as exc:
            raise RealExecutionError("graph_launch_failed", f"captured CUDA Graph replay failed: {exc}") from exc
    raise RealExecutionError("graph_launch_failed", f"captured CUDA Graph replay could not match the runtime launch signature: {last_error}") from last_error


def _network_options_candidates(plan: dict[str, Any]) -> list[dict[str, Any]]:
    workspace_gb = float(plan.get("workspace_gb") or 0.0)
    options: list[dict[str, Any]] = []
    if workspace_gb <= 0.0:
        return [{"device_id": 0}]
    workspace_bytes = int(workspace_gb * (1024 ** 3))
    options.extend(
        [
            {"device_id": 0, "memory_limit": workspace_bytes},
            {"device_id": 0, "memory_limit": f"{workspace_gb:.6f} GiB"},
            {"device_id": 0, "memory_limit": workspace_gb},
            {"device_id": 0},
        ]
    )
    return options


def _construct_network(Network: Any, expr: Any, operands: list[Any], plan: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    last_error: Exception | None = None
    for options in _network_options_candidates(plan):
        try:
            return Network(expr, *operands, options=options), options
        except TypeError as exc:
            last_error = exc
            try:
                return Network(expr, *operands), {"device_id": 0}
            except Exception as inner_exc:  # pragma: no cover - defensive
                last_error = inner_exc
        except Exception as exc:  # pragma: no cover - defensive
            last_error = exc
    raise RealExecutionError("runtime_error", f"failed to construct cuQuantum Network: {last_error}") from last_error


def _call_network_method(method: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return method(*args, **kwargs)
    except TypeError:
        signature = inspect.signature(method)
        filtered_kwargs = {key: value for key, value in kwargs.items() if key in signature.parameters}
        return method(*args, **filtered_kwargs)


def _network_context(network: Any) -> Any:
    return network if hasattr(network, "__enter__") and hasattr(network, "__exit__") else nullcontext(network)


def _to_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "get"):
        value = value.get()
    return np.asarray(value)


def _converter_fixed_qubits(circuit: Any, execution_target: dict[str, Any]) -> dict[Any, str]:
    fixed_qubits = execution_target.get("fixed_qubits") or {}
    qubits = list(getattr(circuit, "qubits", []))
    if not qubits:
        return {qubit_idx: str(int(bit)) for qubit_idx, bit in fixed_qubits.items()}
    converted: dict[Any, str] = {}
    for qubit_idx, bit in fixed_qubits.items():
        index = int(qubit_idx)
        if index < 0 or index >= len(qubits):
            raise RealExecutionError("invalid_execution_target", f"execution_target.fixed_qubits[{index}] is out of range")
        converted[qubits[index]] = str(int(bit))
    return converted


def _reference_result_from_qiskit_circuit(circuit: Any, execution_target: dict[str, Any]) -> np.ndarray:
    from qiskit.quantum_info import Statevector

    state = np.asarray(Statevector.from_instruction(circuit).data, dtype=np.complex128)
    n_qubits = len(getattr(circuit, "qubits", []))
    tensor = state.reshape((2,) * n_qubits).transpose(tuple(reversed(range(n_qubits)))) if n_qubits else state

    if execution_target["kind"] == "amplitude":
        bitstring = str(execution_target["bitstring"])
        if len(bitstring) != n_qubits:
            raise RealExecutionError("invalid_execution_target", "execution_target.bitstring length does not match qubit count")
        return np.asarray(tensor[tuple(int(bit) for bit in bitstring)], dtype=np.complex128)

    fixed_qubits = execution_target.get("fixed_qubits") or {}
    selectors: list[Any] = [slice(None)] * n_qubits
    for qubit_idx, bit in fixed_qubits.items():
        index = int(qubit_idx)
        if index < 0 or index >= n_qubits:
            raise RealExecutionError("invalid_execution_target", f"execution_target.fixed_qubits[{index}] is out of range")
        selectors[index] = int(bit)
    return np.asarray(tensor[tuple(selectors)], dtype=np.complex128)


def execute_real_plan_candidate(
    workload_manifest: dict[str, Any],
    plan: dict[str, Any],
    *,
    system_profile: dict[str, Any] | None = None,
    config: Any,
) -> dict[str, Any]:
    system_profile = system_profile or collect_system_profile()
    preflight = validate_real_execution_request(workload_manifest, system_profile=system_profile)
    execution_target = preflight["execution_target"]
    cupy, Network, CircuitToEinsum = _import_real_stack()

    precision = str(getattr(config, "precision", "complex128"))
    if precision not in {"fp64", "complex128"}:
        raise RealExecutionError("unsupported_semantic_target", f"real cuTensorNet execution currently supports fp64/complex128 only, got {precision!r}")
    try:
        graph_mode = normalize_graph_mode(getattr(config, "graph_mode", None), default="off")
    except ValueError as exc:
        raise RealExecutionError("runtime_error", str(exc), recoverable=False) from exc

    warm_repeats = min(5, max(2, int(getattr(config, "measurement_repeats", 3))))
    profiler = PhaseRecorder()
    started_at = _utc_now_iso()
    t_start = time.perf_counter()

    with profiler.phase("load_circuit", emit_nvtx=True):
        circuit = maybe_load_qiskit_circuit(workload_manifest)
    if circuit is None:
        raise RealExecutionError("missing_qiskit", "Qiskit circuit import failed for the requested OpenQASM2 source")

    with profiler.phase("convert_to_einsum", emit_nvtx=True):
        converter = CircuitToEinsum(circuit, dtype="complex128", backend="cupy")
        if execution_target["kind"] == "amplitude":
            expr, operands = converter.amplitude(execution_target["bitstring"])
        else:
            expr, operands = converter.batched_amplitudes(_converter_fixed_qubits(circuit, execution_target))
    operands = list(operands)
    network, network_options = _construct_network(Network, expr, operands, plan)

    raw_details: dict[str, Any] = {
        "execution_source": REAL_EXECUTION_SOURCE,
        "execution_version": REAL_EXECUTION_VERSION,
        "nvtx_phase_version": NVTX_PHASE_VERSION,
        "execution_target": execution_target,
        "network_options": network_options,
        "probe_strategy": getattr(config, "probe_strategy", None),
        "graph_mode": graph_mode,
        "capabilities": {
            "gpu_present": bool(system_profile.get("gpu_present")),
            "cupy_present": bool(system_profile.get("cupy_present")),
            "cuquantum_present": bool(system_profile.get("cuquantum_present")),
            "qiskit_present": bool(system_profile.get("qiskit_present")),
            "nsys_present": bool(system_profile.get("nsys_present")),
            "ncu_present": bool(system_profile.get("ncu_present")),
        },
    }

    with _network_context(network) as managed_network:
        with profiler.phase("contract_path", emit_nvtx=True):
            t0 = time.perf_counter()
            path_payload = _call_network_method(
                managed_network.contract_path,
                optimize={"samples": max(1, int(plan.get("hyper_samples") or 1))},
            )
            _sync_cupy(cupy)
            raw_details["path_search_time_s"] = round(max(time.perf_counter() - t0, 0.0), 9)
        path_info = path_payload[1] if isinstance(path_payload, tuple) and len(path_payload) >= 2 else path_payload
        raw_details["path_info"] = {
            "largest_intermediate": getattr(path_info, "largest_intermediate", None),
            "opt_cost": getattr(path_info, "opt_cost", None),
            "num_slices": getattr(path_info, "num_slices", None),
        }

        if bool(plan.get("autotune")):
            with profiler.phase("autotune", emit_nvtx=True):
                t0 = time.perf_counter()
                _call_network_method(managed_network.autotune, iterations=5, release_workspace=False)
                _sync_cupy(cupy)
                raw_details["autotune_time_s"] = round(max(time.perf_counter() - t0, 0.0), 9)
        else:
            raw_details["autotune_time_s"] = 0.0

        with profiler.phase("contract_first", emit_nvtx=True):
            t0 = time.perf_counter()
            first_result = _call_network_method(managed_network.contract, release_workspace=False)
            _sync_cupy(cupy)
            raw_details["first_contract_time_s"] = round(max(time.perf_counter() - t0, 0.0), 9)
        first_result_at = time.perf_counter()

        warm_samples_ms: list[float] = []
        warm_result = first_result
        raw_details["graph_capture_status"] = "disabled"
        raw_details["graph_capture_time_s"] = 0.0
        raw_details["graph_replay_phase"] = None
        raw_details["graph_replay_launch_count"] = 0

        if graph_mode == "off":
            for _ in range(warm_repeats):
                with profiler.phase("contract_warm", emit_nvtx=True):
                    t0 = time.perf_counter()
                    warm_result = _call_network_method(managed_network.contract, release_workspace=False)
                    _sync_cupy(cupy)
                    warm_samples_ms.append(round(max(time.perf_counter() - t0, 0.0) * 1000.0, 6))
        else:
            if graph_mode == "warm_only":
                with profiler.phase("contract_warm", emit_nvtx=True):
                    t0 = time.perf_counter()
                    warm_result = _call_network_method(managed_network.contract, release_workspace=False)
                    _sync_cupy(cupy)
                    warm_samples_ms.append(round(max(time.perf_counter() - t0, 0.0) * 1000.0, 6))
                replay_phase = "graph_replay_warm"
                replay_count = max(1, warm_repeats - 1)
            else:
                replay_phase = "graph_replay_steady"
                replay_count = warm_repeats

            with profiler.phase("graph_capture", emit_nvtx=True):
                t0 = time.perf_counter()
                captured_graph, capture_result = _capture_contract_graph(
                    cupy,
                    lambda release_workspace=False: _call_network_method(
                        managed_network.contract,
                        release_workspace=release_workspace,
                    ),
                )
                raw_details["graph_capture_time_s"] = round(max(time.perf_counter() - t0, 0.0), 9)
            raw_details["graph_capture_status"] = "captured"
            raw_details["graph_replay_phase"] = replay_phase
            raw_details["graph_replay_launch_count"] = replay_count

            warm_result = capture_result
            for _ in range(replay_count):
                with profiler.phase(replay_phase, emit_nvtx=True):
                    t0 = time.perf_counter()
                    replay_result = _launch_captured_graph(cupy, captured_graph)
                    warm_result = capture_result if replay_result is None else replay_result
                    warm_samples_ms.append(round(max(time.perf_counter() - t0, 0.0) * 1000.0, 6))
        t0 = time.perf_counter()
        _ = _call_network_method(managed_network.contract, release_workspace=True)
        _sync_cupy(cupy)
        raw_details["release_workspace_contract_time_s"] = round(max(time.perf_counter() - t0, 0.0), 9)

    with profiler.phase("postprocess", emit_nvtx=True):
        output_digest = _safe_output_digest(first_result)
        try:
            peak_mem_gb = round(float(cupy.get_default_memory_pool().used_bytes()) / (1024 ** 3), 9)
        except Exception:
            peak_mem_gb = None

    finished_at = _utc_now_iso()
    total_wall_s = round(max(time.perf_counter() - t_start, 0.0), 9)
    ttfr_s = round(max(first_result_at - t_start, 0.0), 9)
    steady_iter_ms = round(statistics.median(warm_samples_ms) if warm_samples_ms else raw_details["first_contract_time_s"] * 1000.0, 6)

    payload = {
        "plan_id": plan["plan_id"],
        "workload_id": workload_manifest["ids"]["workload_id"],
        "system_id": system_profile["system_id"],
        "replicate_idx": int(getattr(config, "replicate_idx", 0)),
        "graph_mode": graph_mode,
        "status": "success",
        "started_at": started_at,
        "finished_at": finished_at,
        "wall_s": total_wall_s,
        "ttfr_s": ttfr_s,
        "steady_iter_ms": steady_iter_ms,
        "gpu_seconds": total_wall_s,
        "peak_mem_gb": peak_mem_gb,
        "peak_workspace_gb": round(float(plan.get("workspace_gb") or 0.0), 9),
        "output_digest": output_digest,
        "execution_source": REAL_EXECUTION_SOURCE,
        "failure_detail_json": {
            **raw_details,
            "warm_contract_times_ms": warm_samples_ms,
            "phase_times": profiler.phase_times,
        },
    }
    payload["run_id"] = "run_" + sha256_text(
        canonical_json(
            {
                "plan_id": payload["plan_id"],
                "system_id": payload["system_id"],
                "replicate_idx": payload["replicate_idx"],
                "graph_mode": payload.get("graph_mode") or "off",
                "status": payload["status"],
                "execution_source": payload["execution_source"],
            }
        )
    )[:16]

    reference_result = _reference_result_from_qiskit_circuit(circuit, execution_target)
    accuracy_eval = build_accuracy_eval(payload["run_id"], execution_target, _to_numpy(first_result), reference_result)
    raw_details["reference_contract"] = {
        "reference_source": "qiskit_statevector",
        "target_kind": execution_target["kind"],
    }
    payload["failure_detail_json"] = {
        **payload["failure_detail_json"],
        "execution_target": execution_target,
    }
    return {
        "execution_run": payload,
        "accuracy_eval": accuracy_eval,
        "profile_summary": None,
        "result": first_result,
        "warm_result": warm_result,
        "phase_times": profiler.phase_times,
    }


__all__ = [
    "REAL_EXECUTION_SOURCE",
    "REAL_EXECUTION_VERSION",
    "REAL_RECOVERABLE_CODES",
    "RealExecutionError",
    "execute_real_plan_candidate",
    "validate_real_execution_request",
]
