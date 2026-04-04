# OVH Robustness And Overhead ROI v1 Readout

## 1. Was the `high_confidence_top1_accuracy` bug fixed and tested?

Yes.

- The current stack already contains the corrected `high_confidence_top1_accuracy` counting logic in `src/aqs/validation_confidence.py`.
- Regression coverage is already present in `tests/test_validation_confidence.py` for:
  - one high-confidence correct row plus one medium correct row
  - one high-confidence wrong row plus one medium correct row
  - zero high-confidence rows
- This milestone revalidated that coverage before freezing the OVH v2 expanded evaluation baseline.

## 2. What is the OVH TTFR null-pair noise floor?

Null-pair interleaved results:

- `01_real_dense_ring6_amplitude.yaml`
  - same frozen `quick_turnaround` plan on both sides
  - delta 95% CI half-width: `11.687 ms`
  - delta median: `-2.561 ms`
  - conclusion: `inconclusive_vs_variance`
- `08_parity_iqp_batched_heldout_medium.yaml`
  - same frozen `quick_turnaround` plan on both sides
  - delta 95% CI half-width: `48.093 ms`
  - delta median: `1.280 ms`
  - conclusion: `inconclusive_vs_variance`

Frozen noise-floor artifacts:

- `artifacts/ttfr_noise_floor/ovh_ttfr_noise_floor_v1.json`
- `artifacts/ttfr_noise_floor/ovh_ttfr_noise_floor_v1.md`
- `artifacts/ttfr_noise_floor/ovh_ttfr_noise_floor_v1.csv`

## 3. Is that noise floor small enough to certify the winner gaps we care about?

No.

- The low-repeat amplitude null CI half-width is already `11.687 ms`, which is larger than the low-single-digit gaps that dominated the ranking discussion.
- The medium-repeat control null CI half-width reaches `48.093 ms`, so even a positive-control same-plan run does not produce a tight certification band on this host.
- Under current OVH conditions, exact TTFR top-1 in the `1-5 ms` regime should remain descriptive-only.

This strengthens, rather than weakens, the current landing rule:

- no stable miss anchor
- no `selected_dominated_by_top2` workload
- no planner-retune branch yet

## 4. How large is `fresh_minus_frozen` TTFR on the low-repeat amplitude workloads?

Low-repeat amplitude workloads:

- `01_real_dense_ring6_amplitude.yaml`
  - fresh minus frozen call wall: `1399.759 ms`
  - fresh minus frozen calibrated TTFR median: `-0.604 ms`
  - fresh outer orchestration: `1905.008 ms`
  - frozen outer orchestration: `503.836 ms`
- `06_star_graph_phase_amplitude_heldout_low.yaml`
  - fresh minus frozen call wall: `126.702 ms`
  - fresh minus frozen calibrated TTFR median: `11.317 ms`
  - fresh outer orchestration: `629.313 ms`
  - frozen outer orchestration: `513.642 ms`

Control workload:

- `08_parity_iqp_batched_heldout_medium.yaml`
  - fresh minus frozen call wall: `20.500 ms`
  - fresh minus frozen calibrated TTFR median: `0.058 ms`
  - fresh outer orchestration: `461.285 ms`
  - frozen outer orchestration: `444.050 ms`

Frozen-plan ROI artifacts:

- `artifacts/overhead_roi/ovh_low_repeat_overhead_roi.json`
- `artifacts/overhead_roi/ovh_low_repeat_overhead_roi.md`

## 5. Does planning/setup amortization explain most of the observed low-repeat pain?

For end-to-end call wall, yes on the canonical low-repeat amplitude cases.

- `01` shows very large end-to-end savings when the selected plan is frozen instead of recomputed, but almost no inner calibrated TTFR gain.
- `06` shows both a meaningful call-wall gain and an inner TTFR gain, with about `67.97%` of that TTFR delta coming from planner+setup medians and almost none from first-contract time.
- `08` behaves like a control: the call-wall delta is modest and the inner TTFR delta is effectively zero.

Current best-supported interpretation:

- The strongest ROI is in outer orchestration overhead, not in proving a ranking mistake.
- The current `--plan-json` path is already enough to show that skipping fresh selection work can materially reduce end-to-end latency on the low-repeat amplitude path.
- The data do not show a stable executor-winner or ranking-winner story that would justify planner surgery.

## 6. What is the next branch?

Recommended next branch:

- `stack/24-ovh-plan-reuse-prototype`

Why:

- the OVH null-pair noise floor is too large to certify the close TTFR winner gaps that drove the retune question
- the expanded evaluation + anchor-discovery stack still has no usable retune anchor
- fresh-vs-frozen call-wall savings are large enough on `01` and `06` to justify explicit plan reuse / cache / amortization work
- this remains a performance branch, not a calibration or ranking branch

## Frozen baseline reference

The expanded OVH v2 evaluation baseline was frozen before these robustness studies:

- `docs/reports/ovh_v2_expanded_evaluation_baseline.md`
- tag: `ovh-v2-expanded-evaluation-baseline`

That baseline preserves:

- expanded Gate A and Gate B artifacts
- anchor-discovery negative result
- unchanged planner ranking behavior
