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

The `local-second-wall-diagnostic/4` output validates against
`contracts/local-second-wall-diagnostic-result.schema.json`. It retains
all enumerated hypotheses and failed checks. `UNIQUE_DIAGNOSTIC` may carry an experimental candidate,
but `authoritative=false` and `posePromotionAllowed=false` are invariants. The surrounding slot result
remains `GROOVE_SOURCE_INCONSISTENT`, `valid=false`, with no pose promotion or PLC command.
Failure inventory distinguishes `CANDIDATE_MISSING`, `LOCAL_SECOND_WALL_NOT_FOUND`,
`PARTIALLY_OBSERVED`, `MULTIPLE_LOCAL_OPENINGS` and `SOURCE_INCONSISTENT`. `LOCAL_SECOND_WALL_NOT_FOUND`
means that no wall-like pixel cluster survived; `PARTIALLY_OBSERVED` means wall-like evidence exists but
no complete same-source unique opening was established. Every hypothesis check names its evidence layer
and whether it is a hard gate; a numerical score is diagnostic ranking only and cannot override a gate.

Version 2 added no threshold or authority change. It exposed `anchorEvidence`, every seed's search window,
fit/rejection stage, line/finite segment and fit-to-seed delta; `sideSearchMergeClusters` accounts for every
accepted fit and its suppressed members. `rawHypotheses` and `hypothesisMergeClusters` similarly preserve
pre/post merge state. `searchOutcomeSummary` classifies each polarity as `NO_EDGE_SIGNAL`,
`SINGLE_EDGE_ATTRACTOR` or `MULTIPLE_EDGE_CLUSTERS`.

Version 3 replaces the coarse-interval-only generator with four bounded search domains: start/end `INWARD`
and start/end `OUTWARD`. Search angles are wrap360-safe; inward domains stop no later than the coarse interval
midpoint and outward domains stop no later than the configured physical maximum groove width. The v2
`0.12` source-consistency and `0.5°` physical-wall merge gates are unchanged.

Every domain enumerates independent falling/rising wall fits. The start/end refinements are search origins
and audit anchors only; they are not inserted as confirmed walls. Accepted fits are clustered as physical
walls before pairing. A pair ID is the lexicographically sorted two wall-cluster IDs, so reversing anchor or
endpoint order cannot create a second hypothesis. A pair equivalent to the already rejected initial two
endpoints is hard-rejected as `reuses_rejected_initial_pair`. Width, straight/parallel walls, radial support,
outer-circle endpoints, dark opening continuity, endpoint structure and the unchanged source-consistency
checks remain hard gates. Zero or multiple passing canonical pairs remain fail-closed.

Each v3 trace includes search domain, direction, seed, fit/rejection, physical wall cluster and canonical pair.
Even a unique pair remains `authoritative=false`, `posePromotionAllowed=false`; the surrounding result and PLC
boundary are unchanged.

Version 4 adds `PARTIALLY_OBSERVED` and `partialObservation`. It is emitted only when wall-like pixel evidence
exists but no complete same-source unique opening can be established. It never identifies a true-groove wall,
never consumes human annotation, never carries an experimental complete opening, and never changes the outer
`GROOVE_SOURCE_INCONSISTENT`/`valid=false` result. A Git-external human review may confirm one listed wall cluster,
but that confirmation is evaluation evidence rather than runtime input.

## Complete-groove review queue

`complete-groove-review-queue/1` is generated outside Git from one or more frozen manifests and matching JSONL.
It audits every physical sample, records whether two-wall refinement/cluster evidence exists, applies explicit
human exclusions such as a known partial/mixed sample, and selects a bounded number of frames using only
`sha256(sampleId|sourceImageSha256)`. It must not rank by predicted angle, correction, confidence or threshold
distance. Queue entries are pending human review and contain no truth.

`local-second-wall-trace-export/1` is a path-free read-only projection of result JSONL. It includes basenames
and algorithm/config hashes but no pixels, absolute paths or human truth. It is root-cause evidence only and
sets `thresholdTuningAllowed=false`.

## Clean-groove semantic review and dormant contamination request

The definitive 145/147 human clarification is option A: both `AUTO_detected_groove_wall_left/right` lines
belong to the same real square groove and are correct and clean; both sides are complete and unoccluded; both
mouth endpoints lie on real outer-circle groove shoulders. Only other non-groove candidate marks fall on
fixture-shadow regions, and those regions are incompletely marked. This is semantic evidence, not independent
pixel-coordinate truth.

`fixture-contamination-review/1` and its already generated LabelMe files are historical artifacts from the
superseded wall-contamination interpretation. Their lifecycle is `DORMANT_INAPPLICABLE_AFTER_CLARIFICATION_A`.
They remain immutable for audit but MUST NOT be completed, imported, used for tuning, runtime input or PLC.
The legacy generator rejects every invocation before creating an output directory or file.

The next minimal pixel review contains no fixture-overlap shape. A reviewer independently places at least three
distributed support points on each clean groove wall plus the left and right mouth endpoints. No HUMAN point is
copied from AUTO geometry. This can audit wall and endpoint placement; an independent visible outer-circle arc
or circle-center truth is still required before groove-pose angle accuracy can be claimed.
