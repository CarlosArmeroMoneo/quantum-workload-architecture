# Campaign Report: repeat_roi_v1

- Campaign ID: `camp_0e9e80e16faae716`
- Objective: `ttfr`
- Cell count: `360`
- Run count: `1080`
- Status counts: `{'success': 1080}`
- Planner policy hooks: `{'disable_autotune_below_repeat': 4, 'disable_reuse_cache_below_repeat': 8, 'notes': 'Dry-run foundation policy hooks for repeat ROI analysis. These thresholds are not measured evidence.'}`
- Recommended `nsys` follow-up cells: `['cell_c12599c07c0bf461', 'cell_1cb2e43f43d9a4b8', 'cell_00b17055fcb4fc7d', 'cell_004ef35f6227fd9e', 'cell_02e15d478b7100af', 'cell_0e44ec9b3b704e48', 'cell_09ac8ff526602d48', 'cell_115ee7223ccd4b85', 'cell_122fe7fb0fc0f5d9', 'cell_017ff5bfa7f8ecae', 'cell_1a7df49e7a628434', 'cell_05466b375a1233b9', 'cell_037963f97673218e', 'cell_058625208c01aaba', 'cell_04871028b5274598', 'cell_0489e0efe7cad8aa', 'cell_18843c5515968377', 'cell_17ccbcffac2da790', 'cell_32663b2fee8822e1', 'cell_11cc669064ce3ee4', 'cell_0e4772ad911de1be', 'cell_0a85efda1fea1f0a', 'cell_239283b48c2601b6', 'cell_22970887c4ba377b', 'cell_1530e675cc9421d8', 'cell_0224823c148ca3f9', 'cell_3c20fd5339f55b59', 'cell_098f0ef8e6c4e9f9', 'cell_096c038449a2d8a5', 'cell_04d735b0000a6989', 'cell_06f992dfc102eaa1', 'cell_06546f9ba42c95f8']`
- Recommended `ncu` follow-up cells: `['cell_c12599c07c0bf461', 'cell_1cb2e43f43d9a4b8', 'cell_00b17055fcb4fc7d', 'cell_004ef35f6227fd9e', 'cell_02e15d478b7100af', 'cell_0e44ec9b3b704e48', 'cell_09ac8ff526602d48', 'cell_115ee7223ccd4b85', 'cell_122fe7fb0fc0f5d9', 'cell_017ff5bfa7f8ecae', 'cell_1a7df49e7a628434', 'cell_05466b375a1233b9', 'cell_037963f97673218e', 'cell_058625208c01aaba', 'cell_04871028b5274598', 'cell_0489e0efe7cad8aa', 'cell_18843c5515968377', 'cell_17ccbcffac2da790', 'cell_32663b2fee8822e1', 'cell_11cc669064ce3ee4', 'cell_0e4772ad911de1be', 'cell_0a85efda1fea1f0a', 'cell_239283b48c2601b6', 'cell_22970887c4ba377b', 'cell_1530e675cc9421d8', 'cell_0224823c148ca3f9', 'cell_3c20fd5339f55b59', 'cell_098f0ef8e6c4e9f9', 'cell_096c038449a2d8a5', 'cell_04d735b0000a6989', 'cell_06f992dfc102eaa1', 'cell_06546f9ba42c95f8']`

## Workloads

- `cell_004ef35f6227fd9e`: workload `wkl_158088f87b588e6a`, params `{'autotune': False, 'measurement_repeats': 2, 'planner_budget': 'balanced', 'repeat_count_hint': 4, 'reuse_cache': False}`, plan `plan_e1a0a510ef63c3d2`
- `cell_00b17055fcb4fc7d`: workload `wkl_ba3875dd3ccf7480`, params `{'autotune': True, 'measurement_repeats': 2, 'planner_budget': 'deep', 'repeat_count_hint': 32, 'reuse_cache': True}`, plan `plan_f25cb4ffb2b4bca2`
- `cell_017ff5bfa7f8ecae`: workload `wkl_50dd86db6abd0bfa`, params `{'autotune': True, 'measurement_repeats': 2, 'planner_budget': 'deep', 'repeat_count_hint': 8, 'reuse_cache': True}`, plan `plan_bd4e9d6dbd56ba66`
- `cell_0224823c148ca3f9`: workload `wkl_d79599df853f9a2e`, params `{'autotune': False, 'measurement_repeats': 2, 'planner_budget': 'quick', 'repeat_count_hint': 16, 'reuse_cache': False}`, plan `plan_a325ab421e31c266`
- `cell_02e15d478b7100af`: workload `wkl_163dac6a7fcd636d`, params `{'autotune': True, 'measurement_repeats': 2, 'planner_budget': 'balanced', 'repeat_count_hint': 32, 'reuse_cache': False}`, plan `plan_3a75dad14045212e`
- `cell_037963f97673218e`: workload `wkl_75d3c6900c0116f4`, params `{'autotune': False, 'measurement_repeats': 2, 'planner_budget': 'quick', 'repeat_count_hint': 1, 'reuse_cache': True}`, plan `plan_a427750e76a31d40`
- `cell_03d2172a6e385349`: workload `wkl_75d3c6900c0116f4`, params `{'autotune': True, 'measurement_repeats': 2, 'planner_budget': 'quick', 'repeat_count_hint': 1, 'reuse_cache': False}`, plan `plan_11028611ffaaccec`
- `cell_04871028b5274598`: workload `wkl_864119d61a67efe5`, params `{'autotune': False, 'measurement_repeats': 2, 'planner_budget': 'balanced', 'repeat_count_hint': 16, 'reuse_cache': True}`, plan `plan_bdac083d8da1a143`
- `cell_0489e0efe7cad8aa`: workload `wkl_888bce118ad39b04`, params `{'autotune': True, 'measurement_repeats': 2, 'planner_budget': 'balanced', 'repeat_count_hint': 2, 'reuse_cache': True}`, plan `plan_bbceb2172241f5dd`
- `cell_04d735b0000a6989`: workload `wkl_e5f6794fb08543dd`, params `{'autotune': True, 'measurement_repeats': 2, 'planner_budget': 'quick', 'repeat_count_hint': 4, 'reuse_cache': True}`, plan `plan_d8eaaae883122b14`
- `cell_05466b375a1233b9`: workload `wkl_5361a0b920fc4e05`, params `{'autotune': True, 'measurement_repeats': 2, 'planner_budget': 'balanced', 'repeat_count_hint': 1, 'reuse_cache': True}`, plan `plan_19d5ba0a501d7820`
- `cell_058625208c01aaba`: workload `wkl_84140faee381a579`, params `{'autotune': False, 'measurement_repeats': 2, 'planner_budget': 'deep', 'repeat_count_hint': 2, 'reuse_cache': False}`, plan `plan_f985678a7ca683ad`

## Repeat ROI Foundation

- This report is a structural/local dry run unless the execution source is the real cuTensorNet GPU backend.
- Dry-run only: `False`
- Suggested planner policy overrides: `{'confidence': 'dry_run_structural_model_only', 'current_defaults': {'disable_autotune_below_repeat': 6, 'disable_reuse_cache_below_repeat': 8}, 'disable_autotune_below_repeat': 2, 'disable_reuse_cache_below_repeat': 2}`

### Top Findings

- `cell_004ef35f6227fd9e` repeat=4 autotune=False reuse_cache=False roi=baseline break_even_extra_repeats=None
- `cell_ae4f0aae5b91b23e` repeat=4 autotune=False reuse_cache=True roi=neutral break_even_extra_repeats=None
- `cell_9b8792f1446d2e3f` repeat=4 autotune=True reuse_cache=False roi=negative break_even_extra_repeats=None
- `cell_744ad6e48c8b4040` repeat=4 autotune=True reuse_cache=True roi=negative break_even_extra_repeats=None
- `cell_3ae45ce2147c3e1d` repeat=4 autotune=False reuse_cache=False roi=baseline break_even_extra_repeats=None
- `cell_c882205eaa023a74` repeat=4 autotune=False reuse_cache=True roi=negative break_even_extra_repeats=None
- `cell_3b861e131976c392` repeat=4 autotune=True reuse_cache=False roi=negative break_even_extra_repeats=None
- `cell_5e3f7261bf01920b` repeat=4 autotune=True reuse_cache=True roi=negative break_even_extra_repeats=None
- `cell_5761e613a39f1934` repeat=4 autotune=False reuse_cache=False roi=baseline break_even_extra_repeats=None
- `cell_be61050ce310972d` repeat=4 autotune=False reuse_cache=True roi=positive break_even_extra_repeats=0
- `cell_bb2b3fa05b0c659b` repeat=4 autotune=True reuse_cache=False roi=negative break_even_extra_repeats=3287
- `cell_f3d2e2000d8bfd00` repeat=4 autotune=True reuse_cache=True roi=negative break_even_extra_repeats=None
