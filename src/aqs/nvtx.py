from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

NVTX_DOMAIN = "aqs"
NVTX_PHASE_VERSION = "aqs.nvtx.v1"
NVTX_PHASES = (
    "load_circuit",
    "convert_to_einsum",
    "contract_path",
    "autotune",
    "contract_first",
    "graph_capture",
    "contract_warm",
    "graph_replay_warm",
    "graph_replay_steady",
    "postprocess",
)


def _nvtx_annotate():
    try:
        import nvtx
    except Exception:
        return None
    return nvtx.annotate


class _CuPyRange:
    def __init__(self, message: str):
        self._message = message
        self._pushed = False

    def __enter__(self) -> "_CuPyRange":
        try:
            import cupy
        except Exception:
            return self
        try:
            range_name = f"{NVTX_DOMAIN}@{self._message}"
            cupy.cuda.nvtx.RangePush(range_name)
            self._pushed = True
        except Exception:
            self._pushed = False
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._pushed:
            return None
        try:
            import cupy
            cupy.cuda.nvtx.RangePop()
        except Exception:
            return None
        return None


@contextmanager
def nvtx_range(name: str) -> Iterator[None]:
    if name not in NVTX_PHASES:
        raise ValueError(f"Unsupported NVTX phase name {name!r}")
    annotate = _nvtx_annotate()
    if annotate is not None:
        with annotate(message=name, domain=NVTX_DOMAIN):
            yield
        return
    with _CuPyRange(name):
        yield


__all__ = ["NVTX_DOMAIN", "NVTX_PHASE_VERSION", "NVTX_PHASES", "nvtx_range"]
