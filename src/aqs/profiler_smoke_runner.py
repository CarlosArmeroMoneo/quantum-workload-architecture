from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .utils import sha256_text

SMOKE_DOMAIN = "aqs_smoke"
SMOKE_RANGE = "smoke_kernel"
SMOKE_VERSION = "aqs.profiler_smoke.v1"


def _push_smoke_range() -> bool:
    try:
        import cupy

        cupy.cuda.nvtx.RangePush(f"{SMOKE_DOMAIN}@{SMOKE_RANGE}")
        return True
    except Exception:
        return False


def _pop_smoke_range(pushed: bool) -> None:
    if not pushed:
        return
    try:
        import cupy

        cupy.cuda.nvtx.RangePop()
    except Exception:
        return


def run_smoke(size: int = 256) -> dict[str, object]:
    import cupy

    lhs = cupy.arange(size * size, dtype=cupy.float32).reshape(size, size)
    rhs = cupy.arange(size * size, dtype=cupy.float32).reshape(size, size)
    cupy.cuda.Stream.null.synchronize()
    t0 = time.perf_counter()
    pushed = _push_smoke_range()
    try:
        out = lhs @ rhs
        checksum = float(cupy.sum(out).item())
    finally:
        cupy.cuda.Stream.null.synchronize()
        _pop_smoke_range(pushed)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 6)
    return {
        "status": "success",
        "smoke_version": SMOKE_VERSION,
        "nvtx_domain": SMOKE_DOMAIN,
        "nvtx_range": SMOKE_RANGE,
        "size": size,
        "elapsed_ms": elapsed_ms,
        "output_digest": "smoke_" + sha256_text(f"{size}:{checksum}")[:16],
        "checksum": checksum,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m aqs.profiler_smoke_runner")
    parser.add_argument("--out", help="Optional JSON output path")
    parser.add_argument("--size", type=int, default=256)
    args = parser.parse_args(argv)
    payload = run_smoke(size=args.size)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
