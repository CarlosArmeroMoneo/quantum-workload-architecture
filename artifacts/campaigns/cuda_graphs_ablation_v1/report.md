# Campaign Report: cuda_graphs_ablation_v1

- Campaign ID: `camp_f8d4f8227f3c256c`
- Objective: `steady_state`
- Cell count: `12`
- Run count: `36`
- Status counts: `{'runtime_error': 24, 'success': 12}`
- Planner policy hooks: `{}`
- Recommended `nsys` follow-up cells: `['cell_f51c2dd181706085', 'cell_fe364189bc9b7dd4', 'cell_bc7b0ee31f86c44f', 'cell_e9141e68c85a4530']`
- Recommended `ncu` follow-up cells: `['cell_f51c2dd181706085', 'cell_fe364189bc9b7dd4', 'cell_bc7b0ee31f86c44f', 'cell_e9141e68c85a4530']`

## Workloads

- `cell_05f27b1515620b3a`: workload `wkl_aba637ae8beeb019`, params `{'autotune': True, 'graph_mode': 'steady_state', 'measurement_repeats': 3, 'planner_budget': 'balanced', 'repeat_count_hint': 32, 'reuse_cache': True}`, plan `plan_d2cfcc96266ef4f6`
- `cell_16f0318c918fe244`: workload `wkl_34730574a768505b`, params `{'autotune': True, 'graph_mode': 'warm_only', 'measurement_repeats': 3, 'planner_budget': 'balanced', 'repeat_count_hint': 8, 'reuse_cache': True}`, plan `plan_b0462b35ef16f24f`
- `cell_32f6b97487218473`: workload `wkl_aba637ae8beeb019`, params `{'autotune': True, 'graph_mode': 'warm_only', 'measurement_repeats': 3, 'planner_budget': 'balanced', 'repeat_count_hint': 32, 'reuse_cache': True}`, plan `plan_7a6537a53794213d`
- `cell_68749ea440dbb01c`: workload `wkl_977f16a92f06596a`, params `{'autotune': True, 'graph_mode': 'steady_state', 'measurement_repeats': 3, 'planner_budget': 'balanced', 'repeat_count_hint': 32, 'reuse_cache': True}`, plan `plan_a17afbf84ae537e7`
- `cell_6c2fe6b56cad1e5e`: workload `wkl_977f16a92f06596a`, params `{'autotune': True, 'graph_mode': 'warm_only', 'measurement_repeats': 3, 'planner_budget': 'balanced', 'repeat_count_hint': 32, 'reuse_cache': True}`, plan `plan_03b84711f6974834`
- `cell_ad725a685d33c616`: workload `wkl_34730574a768505b`, params `{'autotune': True, 'graph_mode': 'steady_state', 'measurement_repeats': 3, 'planner_budget': 'balanced', 'repeat_count_hint': 8, 'reuse_cache': True}`, plan `plan_ff6be35fef925b40`
- `cell_bc7b0ee31f86c44f`: workload `wkl_34730574a768505b`, params `{'autotune': True, 'graph_mode': 'off', 'measurement_repeats': 3, 'planner_budget': 'balanced', 'repeat_count_hint': 8, 'reuse_cache': True}`, plan `plan_49616549e767c21b`
- `cell_ceea3d2edf761575`: workload `wkl_50dd86db6abd0bfa`, params `{'autotune': True, 'graph_mode': 'steady_state', 'measurement_repeats': 3, 'planner_budget': 'balanced', 'repeat_count_hint': 8, 'reuse_cache': True}`, plan `plan_b97efcf74c6f1ba3`
- `cell_dac6b50d611e8399`: workload `wkl_50dd86db6abd0bfa`, params `{'autotune': True, 'graph_mode': 'warm_only', 'measurement_repeats': 3, 'planner_budget': 'balanced', 'repeat_count_hint': 8, 'reuse_cache': True}`, plan `plan_098bd6312fb74e89`
- `cell_e9141e68c85a4530`: workload `wkl_50dd86db6abd0bfa`, params `{'autotune': True, 'graph_mode': 'off', 'measurement_repeats': 3, 'planner_budget': 'balanced', 'repeat_count_hint': 8, 'reuse_cache': True}`, plan `plan_4e0bc6d06357760f`
- `cell_f51c2dd181706085`: workload `wkl_aba637ae8beeb019`, params `{'autotune': True, 'graph_mode': 'off', 'measurement_repeats': 3, 'planner_budget': 'balanced', 'repeat_count_hint': 32, 'reuse_cache': True}`, plan `plan_d6b9c66ca003beb0`
- `cell_fe364189bc9b7dd4`: workload `wkl_977f16a92f06596a`, params `{'autotune': True, 'graph_mode': 'off', 'measurement_repeats': 3, 'planner_budget': 'balanced', 'repeat_count_hint': 32, 'reuse_cache': True}`, plan `plan_fe31e27fa7f4ef9a`

## Repeat ROI Foundation

- This report is a structural/local dry run unless the execution source is the real cuTensorNet GPU backend.
- Dry-run only: `False`
- Suggested planner policy overrides: `{'confidence': 'dry_run_structural_model_only', 'current_defaults': {'disable_autotune_below_repeat': 6, 'disable_reuse_cache_below_repeat': 8}}`

### Top Findings

- `cell_16f0318c918fe244` repeat=8 autotune=True reuse_cache=True roi=baseline break_even_extra_repeats=None
- `cell_ad725a685d33c616` repeat=8 autotune=True reuse_cache=True roi=baseline break_even_extra_repeats=None
- `cell_bc7b0ee31f86c44f` repeat=8 autotune=True reuse_cache=True roi=baseline break_even_extra_repeats=None
- `cell_ceea3d2edf761575` repeat=8 autotune=True reuse_cache=True roi=baseline break_even_extra_repeats=None
- `cell_dac6b50d611e8399` repeat=8 autotune=True reuse_cache=True roi=baseline break_even_extra_repeats=None
- `cell_e9141e68c85a4530` repeat=8 autotune=True reuse_cache=True roi=baseline break_even_extra_repeats=None
- `cell_68749ea440dbb01c` repeat=32 autotune=True reuse_cache=True roi=baseline break_even_extra_repeats=None
- `cell_6c2fe6b56cad1e5e` repeat=32 autotune=True reuse_cache=True roi=baseline break_even_extra_repeats=None
- `cell_fe364189bc9b7dd4` repeat=32 autotune=True reuse_cache=True roi=baseline break_even_extra_repeats=None
- `cell_05f27b1515620b3a` repeat=32 autotune=True reuse_cache=True roi=baseline break_even_extra_repeats=None
- `cell_32f6b97487218473` repeat=32 autotune=True reuse_cache=True roi=baseline break_even_extra_repeats=None
- `cell_f51c2dd181706085` repeat=32 autotune=True reuse_cache=True roi=baseline break_even_extra_repeats=None
