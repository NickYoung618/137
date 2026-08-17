# Contract: single-shot initial profile

## Input

- One immutable image and its SHA-256.
- One normal slot-pose configuration whose detector mode is `single_real_groove`.
- Repository-contained A-end-face core plus Git-external reference assets locked by SHA.

## Profile invariants

- The original sidewall source-consistency check is enabled and its contrast threshold remains exactly the audited value.
- The versioned contrast-only adjudication is enabled; it cannot override multiple failures, missing evidence, partial observation, ambiguity, or fixture-mixed endpoint structure.
- Runtime does not consume LabelMe, manual coordinates, sample identity, filename rules, or fixed angular ignore regions.
- Image-frame guidance may be returned. Mechanical/PLC execution is always unavailable.

## Success output

- `valid=true`, `detectionStatus=DETECTED`.
- finite `currentAngleDeg`, `targetAngleDeg=85`, `toleranceDeg=5`, finite `correctionDeg`.
- direction follows the sign of correction; the `[80,90]` deadband returns zero and `NONE`.
- original and effective source-consistency decisions remain independently auditable.

## Failure output

- `valid=false`, `detectionStatus=DETECTION_FAILED`, `guidanceStatus=NOT_AVAILABLE`.
- current angle, correction, direction, mechanical mapping and PLC command are null.
- error code and stage identify circle localization, physical circle, groove recognition, ambiguity, wall refinement, partial observation, source inconsistency, quality, input or asset failure.
