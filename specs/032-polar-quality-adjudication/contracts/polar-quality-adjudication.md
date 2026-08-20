# Contract: Polar Quality Adjudication v1

## Configuration

The object is strict and default-off:

```json
{
  "schema_version": "polar-quality-adjudication/1",
  "enabled": false,
  "strategy_version": "locked-physical-groove-proof-v1",
  "development_only": true
}
```

Schema/strategy mixing, unknown fields, non-boolean enablement and non-development use are rejected before image execution. Enabling is supported only in `single_real_groove` mode with compatible physical-circle edge-family, single-groove pose, refinement, sidewall-source, fixture-source and shadow-source evidence.

## Runtime Decision

The diagnostic contains:

- `schemaVersion`, `strategyVersion`, `enabled`, `developmentOnly`;
- `authoritative: false`, `productionDefaultAllowed: false`, `plcAllowed: false`;
- `manualTruthAppliedAtRuntime: false`, `fixedAngleApplied: false`;
- `decision`, `originalFailedChecks`, `effectiveFailedChecks`;
- ordered `checks`, `failedChecks`, and `imagePoseReleaseAllowed`.

`ACCEPTED_OVERRIDE` requires every check below:

1. original failure is exactly `polar_score`;
2. physical circle accepted and exactly one edge family qualified;
3. recognition accepted exactly one groove;
4. single-groove pose and refinement accepted;
5. both observed walls and finite outer endpoints exist;
6. both walls pass radial ownership where that evidence is required;
7. curved floor is accepted with all five tracks accepted;
8. effective source consistency is accepted;
9. fixture bodies and complete U contour are verified, fixture source is excluded, and no fixed angle or manual truth was used.

## Failure Semantics

- Original quality accepted: `NOT_NEEDED`, effective failures remain empty, pose release flag is false because no override was needed.
- Invalid/missing evidence: `NOT_EVALUATED`, original failures retained, pose release forbidden.
- Valid evidence with one or more failed proofs: `REJECTED`, original failures retained, pose release forbidden.
- Exact sole-polar failure with all proofs: `ACCEPTED_OVERRIDE`, effective failures empty, image pose may proceed.
- Any invalid final result retains null pose/correction/direction/mechanical/PLC fields and non-authoritative PLC status.

## Compatibility

- Omitted or disabled configuration executes the previous final-quality path unchanged.
- No existing threshold or original diagnostic value changes.
- The top-level result and coordinate contracts do not change.
