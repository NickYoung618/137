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
show only the 019 final left/right walls and mouth endpoints plus 020 observed dark angular intervals. It does
not show fitted circles, localization rectangles, non-final raw rays or any generated truth box.
The title carries 019 valid and 020 error code; displaying a 020 fixture candidate never changes
the 020 validity state. `pairEvidence.selectedCandidateIds` is the only allowed identity selection;
NOT_MATCHED/PAIR_INCOMPLETE is never replaced by the nearest candidate. Each interval is an open
linestrip with `fixture_identity_confirmed=false`, `boundary_semantics=angular_profile_interval`,
`pixel_boundary_known=false`, match status, candidate id and failed checks. All LabelMe shapes remain
`human_verified=false` and runtime-forbidden.

## Local second-wall diagnostic

`detector.local_second_wall_diagnostic` is optional and absent by default. When present it validates
against `contracts/local-second-wall-diagnostic-config.schema.json`; `enabled=true` requires
single_real_groove, refinement v2 and enabled source consistency. It runs only after physical sidewall
refinement succeeded but source consistency rejected the pair.

The `local-second-wall-diagnostic/2` output validates against
`contracts/local-second-wall-diagnostic-result.schema.json`. It retains
all enumerated hypotheses and failed checks. `UNIQUE_DIAGNOSTIC` may carry an experimental candidate,
but `authoritative=false` and `posePromotionAllowed=false` are invariants. The surrounding slot result
remains `GROOVE_SOURCE_INCONSISTENT`, `valid=false`, with no pose promotion or PLC command.
Failure inventory distinguishes `CANDIDATE_MISSING`, `LOCAL_SECOND_WALL_NOT_FOUND`,
`MULTIPLE_LOCAL_OPENINGS` and `SOURCE_INCONSISTENT`. Every hypothesis check names its evidence layer
and whether it is a hard gate; a numerical score is diagnostic ranking only and cannot override a gate.

Version 2 adds no threshold or authority change. It exposes `anchorEvidence`, every seed's search window,
fit/rejection stage, line/finite segment and fit-to-seed delta; `sideSearchMergeClusters` accounts for every
accepted fit and its suppressed members. `rawHypotheses` and `hypothesisMergeClusters` similarly preserve
pre/post merge state. `searchOutcomeSummary` classifies each polarity as `NO_EDGE_SIGNAL`,
`SINGLE_EDGE_ATTRACTOR` or `MULTIPLE_EDGE_CLUSTERS`.

`local-second-wall-trace-export/1` is a path-free read-only projection of result JSONL. It includes basenames
and algorithm/config hashes but no pixels, absolute paths or human truth. It is root-cause evidence only and
sets `thresholdTuningAllowed=false`.
