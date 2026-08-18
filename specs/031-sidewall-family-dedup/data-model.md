# Data Model: Sidewall Family Deduplication

## WallHypothesis

- Stable hypothesis ID derived after canonical deterministic sorting.
- Canonical normalized line coefficients and direction.
- Selected observed points and row indices.
- Support count, residual P95, longitudinal coverage.
- Outer-circle intersection and clockwise image angle.
- Validation: all geometry finite; at least the existing minimum side support; existing residual/coverage/endpoint gates already passed.

## EquivalenceEvidence

- Left/right hypothesis IDs.
- Finite/degenerate status.
- Shared longitudinal interval, span and ratio of the shorter observed interval.
- Shared observed support count for each hypothesis.
- Direction delta.
- Signed separation at shared start, midpoint and end; absolute P95 and maximum.
- Outer endpoint chord and angle deltas.
- Versioned thresholds, margins, failed checks and equivalence decision.
- Validation: every required numeric field finite; insufficient evidence is explicitly non-equivalent.

## PhysicalWallSourceFamily

- Stable family ID.
- Sorted member hypothesis IDs.
- Representative hypothesis ID and rank evidence.
- Effective support, residual, coverage and endpoint inherited from the representative.
- Radial-alignment delta, threshold and pass/fail derived from the representative direction and its outer-circle endpoint radius.
- Validation: every member pair is equivalent (complete-link invariant); representative is one member; support is not summed.

## WallFamilyDecision

- Schema and strategy versions.
- Raw hypothesis count and physical family count.
- Hypothesis summaries, bounded pair comparisons and family summaries.
- Best/second family support and existing margin.
- Status: `selected`, `ambiguous`, `not_found`, or `invalid`.
- Failure check and selected representative/family IDs when applicable.

## State Transitions

```text
row candidates
  -> fitted qualified hypotheses
  -> finite pair evidence
  -> complete-link physical families
  -> deterministic observed representatives
  -> existing uniqueness gate
  -> selected | ambiguous | not_found | invalid
```

After family selection, a separate `FixtureGrooveSourceExclusionV2` proves verified fixture bodies, two radial walls and an accepted curved floor. `SourceConsistencyAdjudicationV3` may override only photometric magnitude failures when all normalized shape/profile checks and that fixture proof pass. Original source evidence is immutable. No transition may bypass final quality or null-on-failure output handling.
