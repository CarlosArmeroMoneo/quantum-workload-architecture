from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


UNKNOWN_KERNEL_FAMILY = "unknown"
UNKNOWN_KERNEL_CATEGORY = "unknown"


def _clean_name(name: str | None) -> str:
    return str(name or "").strip()


def classify_kernel_name(name: str | None) -> dict[str, str]:
    raw_name = _clean_name(name)
    lowered = raw_name.lower()

    if not lowered:
        return {"kernel_family": UNKNOWN_KERNEL_FAMILY, "kernel_category": UNKNOWN_KERNEL_CATEGORY}

    if "cutensor" in lowered and "contraction_tiny_mnk_kernel" in lowered:
        return {"kernel_family": "cutensor_contraction_tiny_mnk", "kernel_category": "contraction"}
    if ("cutensor" in lowered or "cutensornet" in lowered or "cuquantum" in lowered) and "contraction" in lowered:
        return {"kernel_family": "cutensor_contraction", "kernel_category": "contraction"}
    if ("cutensornet" in lowered or "cuquantum" in lowered) and "contract" in lowered:
        return {"kernel_family": "cuquantum_tensornet_contract", "kernel_category": "contraction"}
    if "contract" in lowered and "kernel" in lowered:
        return {"kernel_family": "generic_contraction", "kernel_category": "contraction"}

    if "memcpy" in lowered or "mem copy" in lowered or "copy_kernel" in lowered:
        return {"kernel_family": "memory_copy", "kernel_category": "memory_copy"}
    if "memset" in lowered or "set_memory" in lowered:
        return {"kernel_family": "memory_set", "kernel_category": "memory_copy"}

    if "reduction" in lowered or "reduce" in lowered:
        return {"kernel_family": "reduction", "kernel_category": "reduction"}

    if "arange" in lowered:
        return {"kernel_family": "array_arange_init", "kernel_category": "arange_init"}
    if "fill" in lowered or "init" in lowered or "initialize" in lowered:
        return {"kernel_family": "array_init", "kernel_category": "arange_init"}

    if "cupy" in lowered or "elementwise" in lowered or "pointwise" in lowered or "thrust" in lowered:
        return {"kernel_family": "framework_overhead", "kernel_category": "framework_overhead"}

    return {"kernel_family": UNKNOWN_KERNEL_FAMILY, "kernel_category": UNKNOWN_KERNEL_CATEGORY}


def enrich_kernel_entry(entry: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(entry)
    classification = classify_kernel_name(str(entry.get("name") or ""))
    enriched.setdefault("kernel_family", classification["kernel_family"])
    enriched.setdefault("kernel_category", classification["kernel_category"])
    return enriched


def occupancy_band(occupancy_pct: float | int | None) -> str:
    if occupancy_pct is None:
        return "unknown"
    value = float(occupancy_pct)
    if value < 35.0:
        return "low"
    if value < 70.0:
        return "medium"
    return "high"


def summarize_kernel_families(kernels: list[dict[str, Any]], *, occupancy_pct: float | int | None = None) -> dict[str, Any]:
    family_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    family_times: defaultdict[str, float] = defaultdict(float)

    for raw_entry in kernels:
        entry = enrich_kernel_entry(raw_entry)
        family = str(entry.get("kernel_family") or UNKNOWN_KERNEL_FAMILY)
        category = str(entry.get("kernel_category") or UNKNOWN_KERNEL_CATEGORY)
        family_counts[family] += 1
        category_counts[category] += 1
        if entry.get("time_s") is not None:
            family_times[family] += float(entry["time_s"])

    total_time = sum(family_times.values())
    top_families = []
    for family, count in sorted(family_counts.items(), key=lambda item: (-item[1], item[0])):
        row: dict[str, Any] = {"kernel_family": family, "count": count}
        if family_times.get(family):
            row["time_s"] = round(float(family_times[family]), 9)
            if total_time > 0.0:
                row["time_pct"] = round((float(family_times[family]) / total_time) * 100.0, 6)
        top_families.append(row)

    return {
        "kernel_family_counts": dict(sorted(family_counts.items())),
        "kernel_category_counts": dict(sorted(category_counts.items())),
        "top_kernel_families": top_families,
        "occupancy_band": occupancy_band(occupancy_pct),
    }


__all__ = [
    "classify_kernel_name",
    "enrich_kernel_entry",
    "occupancy_band",
    "summarize_kernel_families",
]
