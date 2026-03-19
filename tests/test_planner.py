from aqs.features import extract_feature_snapshot
from aqs.manifest import load_yaml
from aqs.normalize import normalize_workload_manifest
from aqs.planner import PlanConfig, generate_plan_candidates, load_system_manifest, select_top_plan
from aqs.tnprobe import ProbeConfig, run_exact_tn_probe


def test_planner_emits_ranked_candidates_and_distributed_option_for_x4_system():
    manifest = load_yaml('workloads/manifests/validation/grid_2d_shallow_val.yaml')
    system_manifest = load_system_manifest('configs/systems/h100_80gb_x4.yml')
    ir = normalize_workload_manifest(manifest)
    features = extract_feature_snapshot(manifest, ir)
    probe = run_exact_tn_probe(manifest, ProbeConfig(objective='ttfr'))
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
