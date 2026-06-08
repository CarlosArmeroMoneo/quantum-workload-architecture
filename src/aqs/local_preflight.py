from __future__ import annotations

from typing import Any


LOCAL_SYSTEM_NAME = "local_nvidia_laptop_6gb"
LOCAL_EVIDENCE_POLICY = "local_preflight_only"
LOCAL_ALLOWED_TIERS = ("Tier 0", "Tier 1")
PUBLIC_PERFORMANCE_GOALS = {"accepted_profile", "canonical_public_performance", "a100_acceptance"}
PREFLIGHT_GOALS = {"preflight", "environment_smoke", "manifest_validation", "tiny_real_execute"}


def is_local_preflight_host(system_manifest: dict[str, Any]) -> bool:
    return (
        system_manifest.get("system_name") == LOCAL_SYSTEM_NAME
        or system_manifest.get("evidence_policy") == LOCAL_EVIDENCE_POLICY
    )


def accepted_for_public_performance_claims(system_manifest: dict[str, Any]) -> bool:
    return bool(system_manifest.get("accepted_for_public_performance_claims"))


def can_satisfy_gcp_a100_acceptance(system_manifest: dict[str, Any]) -> bool:
    return bool(system_manifest.get("can_satisfy_gcp_a100_acceptance"))


def classify_local_preflight_use(system_manifest: dict[str, Any], evidence_goal: str) -> dict[str, Any]:
    """Return the conservative claim boundary for a local preflight host."""

    is_local = is_local_preflight_host(system_manifest)
    blocked = (
        is_local
        and (
            evidence_goal in PUBLIC_PERFORMANCE_GOALS
            or accepted_for_public_performance_claims(system_manifest)
            or can_satisfy_gcp_a100_acceptance(system_manifest)
        )
    )
    allowed = is_local and evidence_goal in PREFLIGHT_GOALS and not blocked
    return {
        "system_name": system_manifest.get("system_name"),
        "is_local_preflight_host": is_local,
        "evidence_goal": evidence_goal,
        "allowed": allowed,
        "blocked": blocked,
        "allowed_evidence_tiers": list(LOCAL_ALLOWED_TIERS) if is_local else [],
        "evidence_policy": system_manifest.get("evidence_policy"),
        "reason_codes": _reason_codes(is_local=is_local, allowed=allowed, blocked=blocked, evidence_goal=evidence_goal),
    }


def _reason_codes(*, is_local: bool, allowed: bool, blocked: bool, evidence_goal: str) -> list[str]:
    if not is_local:
        return ["not_local_preflight_host"]
    if blocked:
        return ["local_preflight_not_public_evidence", f"goal_blocked:{evidence_goal}"]
    if allowed:
        return ["local_preflight_allowed"]
    return ["local_preflight_scope_mismatch", f"goal_not_preflight:{evidence_goal}"]
