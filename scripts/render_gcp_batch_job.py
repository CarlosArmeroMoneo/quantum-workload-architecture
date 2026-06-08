from __future__ import annotations

import argparse
import json
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a GCP Batch GPU profiling job JSON without submitting it")
    parser.add_argument("--template", default="configs/gcp/batch_job_templates/gpu_profile_job.template.json")
    parser.add_argument("--out")
    parser.add_argument("--machine-type", default="a2-highgpu-1g")
    parser.add_argument("--accelerator-type", default="nvidia-tesla-a100")
    parser.add_argument("--accelerator-count", default="1")
    parser.add_argument("--boot-disk-gb", default="200")
    parser.add_argument("--system-manifest", default="configs/systems/gcp_a100_sxm4_40gb.yml")
    parser.add_argument("--workload-manifest", default="workloads/manifests/imported/real_ghz3_amplitude.yaml")
    parser.add_argument("--profile-mode", default="basic")
    parser.add_argument("--profile-outdir", default="artifacts/profiles/gcp_a100_sxm4_40gb/ncu")
    parser.add_argument("--max-run-duration", default="7200s")
    args = parser.parse_args()

    replacements = {
        "MACHINE_TYPE": args.machine_type,
        "ACCELERATOR_TYPE": args.accelerator_type,
        "ACCELERATOR_COUNT": args.accelerator_count,
        "BOOT_DISK_GB": args.boot_disk_gb,
        "SYSTEM_MANIFEST": args.system_manifest,
        "WORKLOAD_MANIFEST": args.workload_manifest,
        "PROFILE_MODE": args.profile_mode,
        "PROFILE_OUTDIR": args.profile_outdir,
        "MAX_RUN_DURATION": args.max_run_duration,
    }
    rendered = render_batch_job(REPO_ROOT / args.template, replacements)
    text = json.dumps(rendered, indent=2, sort_keys=True) + "\n"
    if args.out:
        output_path = REPO_ROOT / args.out
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
