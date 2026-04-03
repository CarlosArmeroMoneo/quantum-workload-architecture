from aqs.doctor import collect_doctor_report, collect_system_profile


def test_doctor_collects_core_keys():
    profile = collect_system_profile()
    required = {
        "system_id",
        "hostname_hash",
        "gpu_count",
        "os_release",
        "container_runtime",
        "gpu_present",
        "cupy_present",
        "cuquantum_present",
        "qiskit_present",
        "nsys_present",
        "ncu_present",
        "repo_metadata",
    }
    assert required.issubset(profile.keys())
    assert profile["system_id"].startswith("sys_")
    assert profile["repo_metadata"]["package_version"]


def test_doctor_profiling_report_wraps_system_profile(monkeypatch):
    monkeypatch.setattr(
        "aqs.profiler_tools.collect_profiling_readiness",
        lambda system_profile, outdir=None, run_smoke=True, db_path=None: {
            "profiling_readiness_version": "aqs.profiling_readiness.v1",
            "system_id": system_profile["system_id"],
            "profiling_ready": False,
        },
    )
    report = collect_doctor_report(profiling=True, run_smoke=False)
    assert "system_profile" in report
    assert "profiling_readiness" in report
    assert "repo_metadata" in report
    assert report["profiling_readiness"]["system_id"] == report["system_profile"]["system_id"]
    assert report["repo_metadata"]["package_version"] == report["system_profile"]["repo_metadata"]["package_version"]
