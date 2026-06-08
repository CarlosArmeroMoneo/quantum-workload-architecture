from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aqs.manifest import load_yaml  # noqa: E402


RECOMMENDATIONS = {"local_preflight", "hyperstack_budget", "gcp_wait_for_quota", "do_not_run"}
LOCAL_NAMES = {"local_nvidia_laptop_6gb"}


def _resolve(path: str | None) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def _repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _load_yaml_path(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"path does not exist: {_repo_path(path)}")
    return load_yaml(path)


def _workload_level(path: Path, workload: dict[str, Any], policy: dict[str, Any]) -> str:
    overrides = policy.get("workload_overrides")
    if isinstance(overrides, dict):
        level = overrides.get(_repo_path(path))
        if isinstance(level, str):
            return level

    params = workload.get("parameters") if isinstance(workload.get("parameters"), dict) else {}
    n_qubits = params.get("n_qubits")
    if n_qubits is None and "rows" in params and "cols" in params:
        try:
            n_qubits = int(params["rows"]) * int(params["cols"])
        except (TypeError, ValueError):
            n_qubits = None
    repeat = int(workload.get("repeat_count_hint") or 1)
    if isinstance(n_qubits, int):
        if n_qubits <= 4:
            return "tiny"
        if n_qubits <= 8 and repeat < 16:
            return "small"
        if n_qubits <= 14:
            return "medium"
    if repeat >= 16:
        return "repeated"
    return "unknown"


def _target_class(args: argparse.Namespace, system: dict[str, Any] | None) -> str:
    if args.target_class:
        return str(args.target_class)
    if not system:
        return "unspecified"
    name = str(system.get("system_name") or "")
    provider = str(system.get("provider") or "")
    if name in LOCAL_NAMES or system.get("evidence_policy") == "local_preflight_only":
        return "local_6gb"
    if "gcp_a100" in name:
        return "gcp_a100"
    if provider == "hyperstack" or "hyperstack" in name:
        return "hyperstack"
    return "unspecified"


def _required_artifacts(policy: dict[str, Any], evidence_goal: str) -> list[str]:
    by_goal = policy.get("required_artifacts_by_goal")
    if isinstance(by_goal, dict):
        values = by_goal.get(evidence_goal)
        if isinstance(values, list):
            return [str(value) for value in values]
    return []


def _result(
    recommendation: str,
    *,
    reason_codes: list[str],
    estimated_risk: str,
    required_artifacts: list[str],
    stop_rules: list[str],
    workload_level: str,
    target_class: str,
) -> dict[str, Any]:
    assert recommendation in RECOMMENDATIONS
    return {
        "recommendation": recommendation,
        "reason_codes": reason_codes,
        "estimated_risk": estimated_risk,
        "required_artifacts": required_artifacts,
        "stop_rules": stop_rules,
        "workload_level": workload_level,
        "target_class": target_class,
    }


def triage(args: argparse.Namespace) -> dict[str, Any]:
    policy_path = _resolve(args.policy)
    assert policy_path is not None
    policy = _load_yaml_path(policy_path)

    workload_path = _resolve(args.workload)
    if workload_path is None:
        raise FileNotFoundError("workload path is required")
    workload = _load_yaml_path(workload_path)

    system = None
    system_path = _resolve(args.system_manifest)
    if system_path is not None:
        system = _load_yaml_path(system_path)

    workload_level = _workload_level(workload_path, workload, policy)
    target_class = _target_class(args, system)
    artifacts = _required_artifacts(policy, args.evidence_goal)
    budget = float(args.budget_cap_eur or 0.0)

    if target_class == "local_6gb":
        local_stop = list((policy.get("local_6gb") or {}).get("stop_rules") or [])
        if args.evidence_goal == "preflight" and workload_level == "tiny":
            return _result(
                "local_preflight",
                reason_codes=["local_6gb_tiny_preflight_allowed"],
                estimated_risk="low",
                required_artifacts=artifacts,
                stop_rules=local_stop,
                workload_level=workload_level,
                target_class=target_class,
            )
        return _result(
            "do_not_run",
            reason_codes=["local_6gb_preflight_only", "cloud_required_for_requested_goal"],
            estimated_risk="high",
            required_artifacts=artifacts,
            stop_rules=local_stop,
            workload_level=workload_level,
            target_class=target_class,
        )

    if args.evidence_goal == "accepted_profile" and target_class == "gcp_a100" and not args.gcp_quota_ready:
        return _result(
            "gcp_wait_for_quota",
            reason_codes=["gcp_a100_quota_not_ready", "acceptance_gate_required"],
            estimated_risk="medium",
            required_artifacts=artifacts,
            stop_rules=["wait for quota", "run offline acceptance gate before public claim"],
            workload_level=workload_level,
            target_class=target_class,
        )

    if args.evidence_goal == "calibration_campaign" and budget > 0.0:
        hyperstack = policy.get("hyperstack_budget") or {}
        max_budget = float(hyperstack.get("max_campaign_budget_eur") or 15.0)
        if budget <= max_budget and workload_level in {"small", "medium", "repeated"}:
            return _result(
                "hyperstack_budget",
                reason_codes=["budget_fits_hyperstack_mini_campaign", "offline_artifacts_defined"],
                estimated_risk="medium",
                required_artifacts=artifacts,
                stop_rules=list(hyperstack.get("stop_rules") or []),
                workload_level=workload_level,
                target_class=target_class,
            )

    if args.evidence_goal in {"real_execution", "profiler_smoke"} and budget > 0.0:
        return _result(
            "hyperstack_budget",
            reason_codes=["cloud_smoke_budget_available"],
            estimated_risk="medium",
            required_artifacts=artifacts,
            stop_rules=list((policy.get("hyperstack_budget") or {}).get("stop_rules") or []),
            workload_level=workload_level,
            target_class=target_class,
        )

    return _result(
        "do_not_run",
        reason_codes=["artifact_acceptance_or_budget_not_ready"],
        estimated_risk="high",
        required_artifacts=artifacts,
        stop_rules=["define artifact acceptance requirements before running"],
        workload_level=workload_level,
        target_class=target_class,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Recommend an offline run target without launching cloud or GPU work")
    parser.add_argument("--workload", required=True, help="Workload manifest path")
    parser.add_argument("--system-manifest", help="System manifest path")
    parser.add_argument("--target-class", choices=["local_6gb", "hyperstack", "gcp_a100"], help="Target class override")
    parser.add_argument(
        "--evidence-goal",
        required=True,
        choices=["preflight", "real_execution", "profiler_smoke", "accepted_profile", "calibration_campaign"],
    )
    parser.add_argument("--budget-cap-eur", type=float, default=0.0)
    parser.add_argument("--gpu-mem-gb", type=float)
    parser.add_argument("--gcp-quota-ready", action="store_true")
    parser.add_argument("--policy", default="configs/experiments/run_triage_policy.yaml")
    args = parser.parse_args()

    try:
        result = triage(args)
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc)}, indent=2, sort_keys=True))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
