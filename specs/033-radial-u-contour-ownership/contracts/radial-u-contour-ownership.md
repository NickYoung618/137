# Contract: Position-Independent Radial U-Contour Ownership

## Compatibility

- Prior configs omit the feature or use source adjudication versions 1-4 and remain unchanged.
- New behavior requires `source-consistency-adjudication/5`, enabled explicitly in a material profile revision.
- Root result schema is unchanged because diagnostics are an open object.

## Fixture Ownership Diagnostic

When verified, the fixture-source payload uses `schemaVersion: fixture-groove-source-exclusion/4` and contains:

- prior fixture body and coarse overlap evidence;
- `twoSidewallsComplete: true`, `uContourComplete: true`;
- `radialUContourOwnershipVerified: true`;
- two ordered finite wall-to-radius alignments, measured opening half-width and derived radial envelope;
- ordered checks and an empty `failedChecks` list;
- `fixtureSourceExcluded: true`;
- `candidateSelectionUsedFixedAngle: false` and `manualTruthAppliedAtRuntime: false`.

Missing or malformed evidence never produces schema `/4` verified ownership.

## Source Adjudication Diagnostic

Version 5 records original/effective status separately. Its new radial-U `ACCEPTED_OVERRIDE` route requires:

- original rejection contains only raw contrast and/or gradient imbalance;
- normalized profile similarity/correlation, radial coverage and endpoint structure pass their unchanged checks;
- fixture-source evidence is verified schema `/4` with radial U-contour ownership true;
- manual truth and fixed-angle selection are false.

The diagnostic remains development-only, non-authoritative and PLC-disallowed.

Version 5 also preserves the unchanged version-4 complete-U and visible-boundary routes. This compatibility path does not use the new radial proof and changes no version-4 measurement or threshold.

## Failure Contract

For the new radial-U route, any missing proof, same-fixture endpoints, incomplete wall/floor, non-photometric failure, ambiguity or nonfinite value keeps the result invalid. Angle, correction, direction, mechanical command and PLC command remain null; PLC execution remains non-authoritative.
