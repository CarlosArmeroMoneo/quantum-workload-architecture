# OVH Executor Overhead Investigation v1

## 1. How much of the bundle-hit penalty sits before inner execution timing?

A large share of the shifted cost sits before `execution_run.wall_s`.

On the canonical OVH host:

- `fresh` and `--plan-json` runs show `import_real_stack_s` around `0.005-0.009 ms` because the real probe path has already imported and warmed the stack before the real executor starts.
- `bundle_hit` runs pay that cost inside the execute path, with `import_real_stack_s` at:
  - `945.087 ms` on `01_real_dense_ring6_amplitude.yaml`
  - `916.901 ms` on `06_star_graph_phase_amplitude_heldout_low.yaml`
  - `991.064 ms` on `08_parity_iqp_batched_heldout_medium.yaml`

That is the clearest measured explanation for why bundle hits preserve the same plan identity but still feel cold.

## 2. How much of the shifted cost is import/context, network build, executor dispatch, or post-execution work?

The shifted-cost split is now explicit.

Dominant contributor on bundle hits:

- `import_real_stack_s`: roughly `0.92-0.99 s`

Secondary contributor on bundle hits:

- `network_build_s`: about `105-106 ms` on all three workloads

Smaller contributor:

- `post_execution_s`: about `1.4-1.6 ms`

Representative medians for the two low-repeat amplitude workloads:

| Workload | Mode | CLI Wall ms | Dispatch / Pre-T-Start ms | Import Stack ms | Network Build ms | Inner Wall ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `01_real_dense_ring6_amplitude.yaml` | `plan_json` | `2080.162` | `0.286` | `0.008` | `6.148` | `48.229` |
| `01_real_dense_ring6_amplitude.yaml` | `bundle_hit` | `2149.166` | `945.419` | `945.087` | `105.670` | `307.214` |
| `01_real_dense_ring6_amplitude.yaml` | `bundle_hit+import_context` | `2098.731` | `1096.653` | `937.345` | `106.819` | `153.970` |
| `01_real_dense_ring6_amplitude.yaml` | `bundle_hit+tiny_network` | `2186.774` | `1253.131` | `943.923` | `6.018` | `48.747` |
| `06_star_graph_phase_amplitude_heldout_low.yaml` | `plan_json` | `2117.132` | `0.306` | `0.009` | `6.376` | `51.597` |
| `06_star_graph_phase_amplitude_heldout_low.yaml` | `bundle_hit` | `2085.147` | `917.495` | `916.901` | `105.562` | `299.720` |
| `06_star_graph_phase_amplitude_heldout_low.yaml` | `bundle_hit+import_context` | `2051.305` | `1079.879` | `941.099` | `104.248` | `154.141` |
| `06_star_graph_phase_amplitude_heldout_low.yaml` | `bundle_hit+tiny_network` | `2219.080` | `1220.932` | `971.496` | `6.046` | `51.717` |

Interpretation:

- `tiny_network` proves that much of the inner penalty can be moved out of `real_execute_s`, because it collapses both `network_build_s` and `execution_run.wall_s` back toward `plan_json`.
- But it does so by adding a much larger explicit prewarm cost, so total CLI wall gets worse.

## 3. Does `--plan-json` retain the useful warmup effect that bundle-hit loses?

Yes.

`--plan-json` keeps the selected plan fixed while still running the real probe path, and that path appears to provide two important warmups:

- it imports the real stack before the real executor starts
- it leaves the subsequent real execute path with a small `network_build_s` and low inner wall

That is why `--plan-json` stays near `fresh` on `01` and `06`, while `bundle_hit` can become slower even though it skips candidate generation entirely.

## 4. Does either cheap prewarm recover most of that loss on `01` and `06`?

Partially, but not strongly enough to choose lightweight prewarm as the next branch.

`import_context`:

- `01_real_dense_ring6_amplitude.yaml`
  - bundle-hit gap vs `--plan-json`: `69.004 ms`
  - recovered by explicit prewarm: `50.436 ms`
  - recovery ratio: `0.730906`
- `06_star_graph_phase_amplitude_heldout_low.yaml`
  - bundle-hit was already `31.985 ms` faster than `--plan-json`
  - explicit prewarm improved bundle-hit a further `33.842 ms`
  - there was no positive `--plan-json` vs bundle-hit gap to recover

`tiny_network`:

- did not recover the low-repeat gap
- made total CLI wall worse on both `01` and `06`

So the answer is:

- `import_context` is directionally useful
- `tiny_network` is too expensive
- neither option eliminates the dominant import/bootstrap tax

## 5. Does the `08` control stay neutral enough to confirm the feature is targeting the right regime?

No. The control does not stay neutral.

- `08` bundle-hit vs `--plan-json` gap: `53.322 ms`
- `08` bundle-hit + `import_context` improved by `80.255 ms`
- `08` bundle-hit + `tiny_network` improved only `26.121 ms`

That means the strongest surviving signal is not “low-repeat amplitude only.”
It is broader execute-side bootstrap/session cost on this OVH host.

## 6. What is the next branch?

Recommended next branch:

- `stack/26-ovh-persistent-executor-investigation`

Why:

- ranking is still unchanged and still blocked
- Gate A and Gate B remain untouched
- the dominant shifted cost is the per-process real-stack import/bootstrap path
- `import_context` prewarm helps, but it does not remove the need to pay that bootstrap tax on every subprocess
- `tiny_network` confirms the mechanism but is too heavy to be the right v1 feature

## Matrix Artifacts

Import/context prewarm matrix:

- `artifacts/executor_overhead/ovh_executor_overhead_matrix_import_context_v1/ovh_executor_overhead_matrix_v1.json`
- `artifacts/executor_overhead/ovh_executor_overhead_matrix_import_context_v1/ovh_executor_overhead_matrix_v1.md`

Tiny-network prewarm matrix:

- `artifacts/executor_overhead/ovh_executor_overhead_matrix_tiny_network_v1/ovh_executor_overhead_matrix_v1.json`
- `artifacts/executor_overhead/ovh_executor_overhead_matrix_tiny_network_v1/ovh_executor_overhead_matrix_v1.md`

## Final Decision

- Stack/24 should stay merged as an opt-in performance feature.
- No ranking or calibration work should reopen from this branch.
- No Nsight Systems tie-breaker is needed yet, because the timing splits already localize the dominant cost well enough.
- The next useful engineering question is persistent executor/session lifetime, not another planner-facing change.
