from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def _coerce_scalar(value: str) -> Any:
    if value.isdigit():
        return int(value)
    try:
        return float(value)
    except ValueError:
        return value


def _render_value(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        rendered = value
        for key, replacement in replacements.items():
            rendered = rendered.replace("{{" + key + "}}", replacement)
        if rendered != value and rendered.strip() == rendered:
            return _coerce_scalar(rendered)
        return rendered
    if isinstance(value, list):
        return [_render_value(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _render_value(item, replacements) for key, item in value.items()}
    return value


def render_batch_job(template_path: str | Path, replacements: dict[str, str]) -> dict[str, Any]:
    template = json.loads(Path(template_path).read_text(encoding="utf-8"))
    return _render_value(template, replacements)


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _require_existing_file(path: Path, label: str) -> None:
    if not path.exists():
        raise ValueError(f"{label} path does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"{label} path is not a file: {path}")


def _validate_output_prefix(prefix: str) -> None:
    if not prefix.startswith("gs://"):
        raise ValueError("--output-prefix must start with gs://")
    project_id = "PROJECT" + "_ID"
    if any(marker in prefix for marker in [f"<{project_id}>", "{{" + project_id + "}}", "${" + project_id + "}"]):
        raise ValueError("--output-prefix must not contain a placeholder project ID")


def _profile_command(args: argparse.Namespace) -> str:
    if args.startup_command:
        return args.startup_command

    parts = [
        "python",
        "-m",
        "aqs",
        "profile",
        args.profiler,
        "--manifest",
        args.workload,
        "--system-manifest",
        args.system,
        "--measurement-repeats",
        str(args.measurement_repeats),
        "--execution-intent",
        "require_real",
        "--planner-budget",
        args.planner_budget,
        "--plan-rank",
        str(args.plan_rank),
        "--no-allow-distributed",
    ]
    if args.profiler == "ncu":
        parts.extend(["--profile-mode", args.profile_mode])
    parts.extend(["--outdir", args.profile_outdir])
    return "set -euo pipefail\n" + " ".join(shlex.quote(part) for part in parts)


def _parse_label(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("labels must use key=value syntax")
    key, label_value = value.split("=", 1)
    if not key or not label_value:
        raise argparse.ArgumentTypeError("labels must use non-empty key=value syntax")
    return key, label_value


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a GCP Batch GPU profiling job JSON without submitting it")
    parser.add_argument("--template", default="configs/gcp/batch_job_templates/gpu_profile_job.template.json")
    parser.add_argument("--workload", "--workload-manifest", dest="workload", required=True, help="Workload manifest path")
    parser.add_argument("--system", "--system-manifest", dest="system", required=True, help="System manifest path")
    parser.add_argument("--profiler", choices=["nsys", "ncu"], required=True)
    parser.add_argument("--output-prefix", required=True, help="GCS prefix for future artifact sync, for example gs://bucket/qwa/runs/example")
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--out")
    parser.add_argument("--container-image", default="nvcr.io/nvidia/cuquantum-appliance:25.11-x86_64")
    parser.add_argument("--startup-command", help="Override the generated container startup command")
    parser.add_argument("--machine-type", default="a2-highgpu-1g")
    parser.add_argument("--accelerator-type", default="nvidia-tesla-a100")
    parser.add_argument("--accelerator-count", default="1")
    parser.add_argument("--boot-disk-gb", default="200")
    parser.add_argument("--cpu-milli", default="4000")
    parser.add_argument("--memory-mib", default="16384")
    parser.add_argument("--measurement-repeats", default="1")
    parser.add_argument("--planner-budget", default="balanced")
    parser.add_argument("--plan-rank", default="1")
    parser.add_argument("--profile-mode", default="basic")
    parser.add_argument("--profile-outdir", default="artifacts/profiles/gcp_batch_dry_run")
    parser.add_argument("--max-run-duration", default="7200s")
    parser.add_argument("--label", action="append", default=[], type=_parse_label, help="Additional rendered label as key=value")
    args = parser.parse_args()

    try:
        template_path = _repo_path(args.template)
        _require_existing_file(template_path, "template")
        _require_existing_file(_repo_path(args.workload), "workload")
        _require_existing_file(_repo_path(args.system), "system")
        _validate_output_prefix(args.output_prefix)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    replacements = {
        "JOB_NAME": args.job_name,
        "CONTAINER_IMAGE": args.container_image,
        "STARTUP_COMMAND": _profile_command(args),
        "PROFILER_KIND": args.profiler,
        "OUTPUT_GCS_PREFIX": args.output_prefix,
        "MACHINE_TYPE": args.machine_type,
        "ACCELERATOR_TYPE": args.accelerator_type,
        "ACCELERATOR_COUNT": args.accelerator_count,
        "BOOT_DISK_GB": args.boot_disk_gb,
        "CPU_MILLI": args.cpu_milli,
        "MEMORY_MIB": args.memory_mib,
        "SYSTEM_MANIFEST": args.system,
        "WORKLOAD_MANIFEST": args.workload,
        "PROFILE_MODE": args.profile_mode,
        "PROFILE_OUTDIR": args.profile_outdir,
        "MAX_RUN_DURATION": args.max_run_duration,
    }
    rendered = render_batch_job(template_path, replacements)
    labels = rendered.setdefault("labels", {})
    if not isinstance(labels, dict):
        print("rendered template labels must be an object", file=sys.stderr)
        return 2
    for key, value in args.label:
        labels[key] = value

    text = json.dumps(rendered, indent=2, sort_keys=True) + "\n"
    if args.out:
        output_path = _repo_path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
