from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "render_gcp_batch_job.py"
TEMPLATE = "configs/gcp/batch_job_templates/gpu_profile_job.template.json"
WORKLOAD = "workloads/manifests/imported/real_dense_ring6_batched.yaml"
SYSTEM = "configs/systems/gcp_a100_sxm4_40gb.yml"


def _render(*extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--template",
            TEMPLATE,
            "--workload",
            WORKLOAD,
            "--system",
            SYSTEM,
            "--profiler",
            "ncu",
            "--output-prefix",
            "gs://bucket/qwa/runs/example",
            "--job-name",
            "qwa-a100-batched-ncu",
            *extra_args,
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_renderer_produces_valid_batch_json_to_stdout():
    completed = _render("--label", "case=canonical")

    assert completed.returncode == 0
    assert completed.stderr == ""
    payload = json.loads(completed.stdout)

    assert payload["name"] == "qwa-a100-batched-ncu"
    assert payload["labels"]["dry_run"] == "true"
    assert payload["labels"]["profiler"] == "ncu"
    assert payload["labels"]["case"] == "canonical"

    task_spec = payload["taskGroups"][0]["taskSpec"]
    runnable = task_spec["runnables"][0]["container"]
    assert runnable["imageUri"].startswith("nvcr.io/nvidia/cuquantum-appliance")
    command = runnable["commands"][2]
    assert "python -m aqs profile ncu" in command
    assert f"--manifest {WORKLOAD}" in command
    assert f"--system-manifest {SYSTEM}" in command
    assert "--profile-mode basic" in command
    assert "gcloud" not in command.lower()

    env = task_spec["environment"]["variables"]
    assert env["QWA_DRY_RUN"] == "true"
    assert env["QWA_OUTPUT_GCS_PREFIX"] == "gs://bucket/qwa/runs/example"
    assert env["QWA_WORKLOAD_MANIFEST"] == WORKLOAD

    policy = payload["allocationPolicy"]["instances"][0]["policy"]
    assert policy["machineType"] == "a2-highgpu-1g"
    assert policy["accelerators"][0] == {"type": "nvidia-tesla-a100", "count": 1}
    assert task_spec["maxRunDuration"] == "7200s"


def test_renderer_writes_output_file(tmp_path: Path):
    output_path = tmp_path / "qwa_batch_job.json"
    completed = _render("--out", str(output_path))

    assert completed.returncode == 0
    assert completed.stdout == ""
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["name"] == "qwa-a100-batched-ncu"


def test_missing_workload_path_errors_clearly():
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--template",
            TEMPLATE,
            "--workload",
            "workloads/manifests/imported/does_not_exist.yaml",
            "--system",
            SYSTEM,
            "--profiler",
            "ncu",
            "--output-prefix",
            "gs://bucket/qwa/runs/example",
            "--job-name",
            "qwa-a100-batched-ncu",
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "workload path does not exist" in completed.stderr


def test_rendered_output_has_no_placeholder_project_id():
    completed = _render()
    project_id = "PROJECT" + "_ID"

    assert completed.returncode == 0
    assert f"<{project_id}>" not in completed.stdout
    assert "{{" + project_id + "}}" not in completed.stdout


def test_renderer_source_makes_no_live_gcp_call():
    source = SCRIPT.read_text(encoding="utf-8")

    forbidden = ["google.cloud", "googleapiclient", "gcloud ", "batch_v1", "requests."]
    for term in forbidden:
        assert term not in source
