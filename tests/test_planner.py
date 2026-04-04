from aqs.features import extract_feature_snapshot
from aqs.manifest import load_yaml
from aqs.normalize import normalize_workload_manifest
from aqs.planner import PlanConfig, generate_plan_candidates, load_system_manifest, select_top_plan


def _stub_probe(*, probe_id: str, predicted_peak_gb: float, optimizer_cost: float, objective: str = "ttfr") -> dict[str, object]:
    return {
        "probe_id": probe_id,
        "mode": "exact_tn",
        "objective": objective,
        "precision": "complex128",
        "predicted_peak_gb": predicted_peak_gb,
        "predicted_error": 0.0,
        "optimizer_cost": optimizer_cost,
        "largest_intermediate": max(predicted_peak_gb * 1024.0, 1.0),
        "num_slices": 1,
    }


def test_planner_emits_ranked_candidates_and_distributed_option_for_x4_system():
    manifest = load_yaml('workloads/manifests/validation/grid_2d_shallow_val.yaml')
    system_manifest = load_system_manifest('configs/systems/h100_80gb_x4.yml')
    ir = normalize_workload_manifest(manifest)
    features = extract_feature_snapshot(manifest, ir)
    probe = _stub_probe(probe_id="probe_planner_x4", predicted_peak_gb=18.0, optimizer_cost=2.5e6)
    candidates = generate_plan_candidates(
        manifest,
        features,
        probe,
        system_manifest,
        config=PlanConfig(objective='ttfr', planner_budget='balanced', allow_distributed=True),
    )
    assert len(candidates) >= 3
    assert candidates[0]['recommendation_rank'] == 1
    assert any(candidate['mode'] == 'exact_tn_distributed' for candidate in candidates)
    top = select_top_plan(candidates, objective='ttfr')
    assert top is not None
    assert top['feasibility_label'] in {'feasible', 'uncertain'}


def test_planner_policy_overrides_can_disable_repeat_roi_knobs():
    manifest = load_yaml('workloads/manifests/measured/dense_universal_tiny.yaml')
    system_manifest = load_system_manifest('configs/systems/cpu_probe.yml')
    ir = normalize_workload_manifest(manifest)
    features = extract_feature_snapshot(manifest, ir)
    probe = _stub_probe(probe_id="probe_planner_policy", predicted_peak_gb=0.08, optimizer_cost=128.0)

    default_candidates = generate_plan_candidates(
        manifest,
        features,
        probe,
        system_manifest,
        config=PlanConfig(objective='ttfr', planner_budget='balanced', allow_distributed=False),
    )
    override_candidates = generate_plan_candidates(
        manifest,
        features,
        probe,
        system_manifest,
        config=PlanConfig(
            objective='ttfr',
            planner_budget='balanced',
            allow_distributed=False,
            policy_overrides={
                'disable_autotune_below_repeat': 64,
                'disable_reuse_cache_below_repeat': 64,
            },
        ),
    )

    assert any(candidate['autotune'] for candidate in default_candidates)
    assert all(not candidate['autotune'] for candidate in override_candidates)
    assert all(not candidate['reuse_cache'] for candidate in override_candidates)
    assert any('planner policy disables autotune' in reason for candidate in override_candidates for reason in candidate['explanation_json'])


def test_planner_observability_fields_do_not_change_fixture_ranking():
    manifest = load_yaml('workloads/manifests/measured/dense_universal_tiny.yaml')
    system_manifest = load_system_manifest('configs/systems/cpu_probe.yml')
    ir = normalize_workload_manifest(manifest)
    features = extract_feature_snapshot(manifest, ir)
    probe = _stub_probe(probe_id="probe_planner_observability", predicted_peak_gb=0.08, optimizer_cost=128.0)

    candidates = generate_plan_candidates(
        manifest,
        features,
        probe,
        system_manifest,
        config=PlanConfig(objective='ttfr', planner_budget='balanced', allow_distributed=False),
    )

    assert [candidate['template_name'] for candidate in candidates] == ['quick_turnaround', 'balanced', 'deep_search']
    for candidate in candidates:
        assert candidate['predicted_planning_s'] >= 0.0
        assert candidate['predicted_setup_s'] >= 0.0
        assert candidate['speed_factor_used'] > 0.0
        assert candidate['path_quality_factor'] > 0.0
        assert candidate['workspace_factor'] > 0.0
        assert candidate['repeat_count_used'] >= 1
        assert candidate['prediction_breakdown_json']['repeat_count_used'] == candidate['repeat_count_used']
