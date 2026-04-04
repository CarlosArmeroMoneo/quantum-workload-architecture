# OVH Heldout Input Inventory

This inventory tracks the new real-host-compatible imported source inputs added ahead of `OVH Heldout Expansion v1`.

## Intake Rules

- `source_format: qiskit`
- OpenQASM 2 source files under `workloads/sources/openqasm/`
- exact-TN executable on the current single-GPU OVH validation host
- conservative qubit counts and gate counts
- enough family diversity to support four new `heldout_family` manifests without reusing the current training family IDs

## Intake Table

| Intake manifest | Source path | Family ID | Workload type | Repeat regime | Expected execution target | Split eligibility |
| --- | --- | --- | --- | --- | --- | --- |
| `workloads/manifests/imported/ovh_inputs/star_graph_phase_amplitude_low.yaml` | `workloads/sources/openqasm/star_graph5.qasm` | `star_graph_phase` | amplitude | low (`repeat_count_hint=1`) | amplitude bitstring `00000` | candidate for `heldout_family` |
| `workloads/manifests/imported/ovh_inputs/ladder_brickwork_amplitude_medium.yaml` | `workloads/sources/openqasm/ladder_brickwork6.qasm` | `ladder_brickwork` | amplitude | medium (`repeat_count_hint=6`) | amplitude bitstring `010101` | candidate for `heldout_family` |
| `workloads/manifests/imported/ovh_inputs/parity_iqp_batched_medium.yaml` | `workloads/sources/openqasm/parity_iqp5.qasm` | `parity_iqp` | batched amplitudes | medium (`repeat_count_hint=6`) | batched amplitudes with fixed qubit `0=0` | candidate for `heldout_family` |
| `workloads/manifests/imported/ovh_inputs/spin_chain_phase_batched_high.yaml` | `workloads/sources/openqasm/spin_chain6.qasm` | `spin_chain_phase` | batched amplitudes | high (`repeat_count_hint=12`) | batched amplitudes with fixed qubit `0=0` | candidate for `heldout_family` |

## Notes

- These inputs are intentionally separate from the frozen `v1` OVH measured-validation corpus so the baseline glob remains stable.
- The next branch materializes heldout manifests from these inputs under a separate expanded-corpus namespace.
- This inventory is intake-only. It does not claim a planner retune anchor by itself.
- OVH smoke-execution check on April 4, 2026 used `execution_intent=require_real` with the current single-GPU validation manifest and succeeded for all four intake manifests:
  - `ladder_brickwork_amplitude_medium`: `success`, selected template `quick_turnaround`, measured TTFR `0.055842724 s`
  - `parity_iqp_batched_medium`: `success`, selected template `quick_turnaround`, measured TTFR `0.307859412 s`
  - `spin_chain_phase_batched_high`: `success`, selected template `quick_turnaround`, measured TTFR `0.337472151 s`
  - `star_graph_phase_amplitude_low`: `success`, selected template `quick_turnaround`, measured TTFR `0.062867916 s`
