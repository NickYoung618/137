# Runtime Contract: Physical Circle Family Consensus

## Configuration

The existing `physical-circle-edge-family-selection/1` object accepts two explicit strategies:

- `deterministic-three-point-global-circle-v1`: frozen compatibility behavior.
- `deterministic-family-consensus-circle-v2`: bounded intra-family consensus.

All existing numeric controls and final physical-circle thresholds retain their meanings and values. Version 2 has a fixed documented iteration bound; it does not expose an operational threshold that can be relaxed per sample.

## Version-2 decision

1. Generate and group bounded hypotheses using existing evidence.
2. Never combine different grouped families.
3. Compare the version-1 representative residual with the unchanged scaled authoritative residual gate.
4. If it passes, preserve its circle and observed assignments and report `not_needed`.
5. Otherwise derive an order-invariant finite seed from every member circle in one family.
6. Assign at most one already-observed candidate per ray.
7. Refit and reassign until assignment identity is unchanged or the fixed bound of 16 is reached.
8. Reject invalid, insufficient or non-convergent corrective consensus.
9. Apply existing family eligibility gates.
10. Require exactly one qualified family.
11. Run exactly one existing authoritative robust fit and unchanged final quality gates.

## Additive diagnostic fields

Each version-2 family summary includes a `consensus` object with:

- `schemaVersion = physical-circle-family-consensus/1`
- `status = not_needed | converged | rejected | invalid`
- `applied`
- `triggerResidualP95Px`
- `originalResidualP95Px`
- `memberHypothesisCount`
- `maxIterations`
- `iterationCount`
- `converged`
- `assignmentChangeCounts`
- `initialCircle`
- `finalCircle`
- `supportRayCount`
- `angularCoverage`
- `residualMedianPx`
- `residualP95Px`
- `failedChecks`

Lists are bounded by the fixed iteration count. No raw image path, manual truth or per-ray unbounded payload is emitted.

## Safety

- Zero qualified families: explicit no-family failure.
- More than one qualified family: explicit ambiguity.
- Non-convergent corrective consensus: family rejected.
- Already-passing representative: preserved exactly; no corrective iterations are run.
- Invalid/ambiguous root result: no angle, correction, direction, mechanical correction or PLC command; PLC authority false.
