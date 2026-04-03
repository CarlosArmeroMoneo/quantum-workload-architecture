from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from .paths import repo_root
from .utils import sha256_text


CUDAQ_PROGRAM_API_VERSION = "aqs.cudaq_program.v1"
CUDAQ_PROGRAM_EXPORT = "aqs_cudaq_program"


class CudaqAdapterError(RuntimeError):
    pass


def _resolve_path(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return repo_root() / path


def load_cudaq_program(path_like: str | Path) -> dict[str, Any]:
    path = _resolve_path(path_like)
    if not path.exists():
        raise CudaqAdapterError(f"CUDA-Q adapter file does not exist: {path}")

    module_name = f"aqs_cudaq_adapter_{sha256_text(str(path).replace(chr(92), '/'))[:16]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise CudaqAdapterError(f"Could not import CUDA-Q adapter module from {path}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise CudaqAdapterError(f"Failed to import CUDA-Q adapter module {path}: {exc}") from exc

    export = getattr(module, CUDAQ_PROGRAM_EXPORT, None)
    if not callable(export):
        raise CudaqAdapterError(f"CUDA-Q adapter module {path} must export {CUDAQ_PROGRAM_EXPORT}()")

    try:
        payload = export()
    except Exception as exc:
        raise CudaqAdapterError(f"{CUDAQ_PROGRAM_EXPORT}() failed for {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise CudaqAdapterError(f"{CUDAQ_PROGRAM_EXPORT}() must return a mapping, got {type(payload)!r}")

    api_version = str(payload.get("api_version") or CUDAQ_PROGRAM_API_VERSION)
    if api_version != CUDAQ_PROGRAM_API_VERSION:
        raise CudaqAdapterError(
            f"{CUDAQ_PROGRAM_EXPORT}() returned unsupported api_version {api_version!r}; expected {CUDAQ_PROGRAM_API_VERSION!r}"
        )

    openqasm2 = payload.get("openqasm2")
    if not isinstance(openqasm2, str) or not openqasm2.strip():
        raise CudaqAdapterError(f"{CUDAQ_PROGRAM_EXPORT}() must provide a non-empty 'openqasm2' string")

    program_name = payload.get("program_name")
    if program_name is not None and not isinstance(program_name, str):
        raise CudaqAdapterError(f"{CUDAQ_PROGRAM_EXPORT}().program_name must be a string when provided")

    source_kind = payload.get("source_kind")
    if source_kind is not None and not isinstance(source_kind, str):
        raise CudaqAdapterError(f"{CUDAQ_PROGRAM_EXPORT}().source_kind must be a string when provided")

    metadata = payload.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise CudaqAdapterError(f"{CUDAQ_PROGRAM_EXPORT}().metadata must be a mapping when provided")

    return {
        "api_version": api_version,
        "program_name": program_name or path.stem,
        "source_kind": source_kind or "cudaq_adapter",
        "openqasm2": openqasm2,
        "metadata": dict(metadata or {}),
        "path": str(path).replace("\\", "/"),
    }


__all__ = [
    "CUDAQ_PROGRAM_API_VERSION",
    "CUDAQ_PROGRAM_EXPORT",
    "CudaqAdapterError",
    "load_cudaq_program",
]
