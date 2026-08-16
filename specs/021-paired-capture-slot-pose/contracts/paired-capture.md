# Contract: paired capture slot pose v1

## Input manifest

`paired-capture-manifest/1` contains pairs, not independent images. Paths are relative to one A2 root. SHA-256 is authoritative. Rotation direction is CLOCKWISE or COUNTERCLOCKWISE in the image x-right/y-down convention; magnitude is non-negative.

CONFIRMED requires nominalRotationDeg, direction and rotationToleranceDeg. UNCONFIRMED permits nulls. A temporary numeric estimate does not become authoritative until status changes to CONFIRMED.

## Per-frame result input

The paired CLI consumes existing slot-pose result JSONL keyed by image SHA. It accepts successful and fail-closed single-frame results because diagnostics may still contain candidates. It requires `rawCandidates` or `candidates`; `grooveRecognition.assessments`, `grooveCandidates`, `grooveRefinement` and `grooveSourceConsistency` are retained when present.

## Angle transform

`signedRotation = +nominal` for CLOCKWISE and `-nominal` for COUNTERCLOCKWISE.

`secondInFirstPart = wrap360(secondImageProfile - signedRotation)`

`residual = abs(wrap180(secondInFirstPart - firstImageProfile))`

For the second-capture final posture, `currentProfile = wrap360(partRelative + signedRotation)` and `currentAngle = wrap180(currentProfile - 90)`.

## Authority

- EXPERIMENT_DISABLED: no matching.
- DIAGNOSTIC_ONLY: candidates and optional provisional hypotheses; valid=false.
- DETECTED: confirmed parameters, unique match, residual/shape gates pass, at least one usable measurement.
- FAILED: stable code and null guidance.

Even DETECTED never emits plcCommand or mechanicalCorrectionDeg in v1.

## Simplified manual review

`slot-pose-prefill-review/2` is a Git-external review index. Each entry references one raw image,
one full-resolution simplified image and one minimal AUTO_ LabelMe JSON. The simplified image may
show only the 019 final left/right walls and mouth endpoints plus 020 fixture candidates. It does
not show fitted circles, localization rectangles, non-final raw rays or any generated truth box.
The title carries 019 valid and 020 error code; displaying a 020 fixture candidate never changes
the 020 validity state. All LabelMe shapes remain `human_verified=false` and runtime-forbidden.
