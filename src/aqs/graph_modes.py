from __future__ import annotations

GRAPH_MODES = ("off", "warm_only", "steady_state")


def normalize_graph_mode(graph_mode: str | None, *, default: str = "off") -> str:
    mode = default if graph_mode is None else str(graph_mode).strip() or default
    if mode not in GRAPH_MODES:
        raise ValueError(f"unsupported graph mode {mode!r}; expected one of {list(GRAPH_MODES)}")
    return mode


__all__ = ["GRAPH_MODES", "normalize_graph_mode"]
