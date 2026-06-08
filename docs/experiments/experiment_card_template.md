# Experiment Card Template

Use this template when a profiler-backed nomination needs a falsifiable follow-up experiment. The card should describe what evidence would change the current interpretation, not claim the change has already worked.

## Title

Name the bottleneck, workload slice, and proposed counterfactual in one sentence.

## Source Nomination

Record the originating workload, host, profiler, architecture output, `bottleneck_family`, and `nomination_source`.

## Evidence Tier

State the current tier and the target tier for the experiment. Keep pending lanes marked pending until artifacts are pinned.

## Observation

Summarize the measured behavior that motivated the nomination. Include the specific profile or phase signal that made the bottleneck visible.

## Hypothesis

Write one falsifiable statement about how a system change should improve the measured behavior.

## Counterfactual Knobs

List the smallest set of knobs needed to test the hypothesis. Avoid broad sweeps.

## Expected Measurements

List the metrics and artifact fields that must be captured for every arm.

## Success Criterion

Define the minimum evidence needed to say the counterfactual improved the bottleneck.

## Stop Criterion

Define conditions that end the experiment without promoting the claim.

## Risks And Confounders

List setup leakage, profiler distortion, caching artifacts, correctness drift, or workload-size effects that could make the result misleading.

## Required Artifacts

List execution payloads, profile summaries, raw profiler artifacts, artifact manifests, and any architecture-analysis reruns required for review.

## Acceptance Rule

State the exact rule for whether the result becomes accepted evidence, remains pending, or is rejected.
