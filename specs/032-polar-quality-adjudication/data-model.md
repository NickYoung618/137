# Data Model: Physical-Groove Polar Quality Adjudication

## OriginalPolarQualityEvidence

- Finite polar score and finite unchanged threshold.
- Ordered original final-quality failure IDs.
- Validation: the score comparison agrees with presence or absence of `polar_score`; duplicate or unknown failure IDs invalidate adjudication evidence.

## PhysicalGrooveProof

- Physical-circle status and qualified edge-family count.
- Recognition status, accepted-candidate count and selected candidate identity.
- Single-groove pose and refinement status.
- Two observed sidewalls, radial-alignment results and finite outer-circle endpoints.
- Curved-floor status, track count and accepted-track count.
- Original/effective source-consistency status.
- Fixture-source-exclusion status, U-contour completeness, fixture-source exclusion and fixed-angle/manual-truth flags.
- Validation: every required field has the expected schema/version and finite/bounded value; missing or malformed evidence is a denial.

## PolarQualityAdjudication

- Schema and strategy version.
- Enabled, development-only, production-default and PLC flags.
- Decision: `NOT_NEEDED`, `ACCEPTED_OVERRIDE`, `REJECTED` or `NOT_EVALUATED`.
- Original and effective failure lists.
- Ordered proof checks with pass/fail state.
- Failed check IDs and image-pose-release permission.
- Validation: `ACCEPTED_OVERRIDE` has original failures exactly `['polar_score']`, effective failures empty, all checks passed and pose release allowed. Every other decision forbids pose release.

## EffectiveQualityState

- Immutable original evidence plus effective final failures.
- State transition:

```text
original failures empty
  -> NOT_NEEDED -> effective failures empty

original failures exactly polar_score + every physical proof passes
  -> ACCEPTED_OVERRIDE -> effective failures empty

missing/invalid proof or any other failure
  -> REJECTED | NOT_EVALUATED -> effective failures unchanged
```

No transition changes the polar score, threshold, refined groove pose, mechanical mapping or PLC authority.
